"""도클갱어 W5 — 회의록 요약 어시스턴트.

신경계 비유:
- 텔레그램에 *붙여 넣은 회의 메모*(원재료)가 들어오면,
- 페르소나(뇌·언어 피질)가 그 메모를 *자기 톤*으로 다시 적되 *사실은 그대로 보존*해서
- 텔레그램(목소리)으로 *구조화된 회의록*을 흘려 보내요.

설계 원칙 (TF-1040 — 가장 단순·로컬완결):
- 입력 = *텍스트 붙여넣기* 한 가지. 음성·STT·파일 0 (의도적 단순화).
- 출력 = 한 줄 요약 / 핵심 논의 / 결정사항 / 액션아이템(담당·기한) / 미해결 질문.
  섹션 on/off 와 길이는 `config/meeting_notes.yml` 로 조정.
- *사실 보존*: 페르소나는 회의록에 *톤만* 입히고 참석자·결정·숫자·날짜 같은
  *사실은 절대 바꾸지 못한다*. W3 briefing 의 사실보존 지침 정합 — 시스템 프롬프트에 명시.
- 새 외부 의존성 0 — 순수 텍스트라 pyyaml(이미 보유)만 재사용.

차용 출처:
- bot.py::call_claude_code — Claude CLI 서브프로세스 패턴 그대로
- briefing.py::build_briefing_system_prompt — 페르소나 + 지침 *합성* 패턴 정합
- briefing.py::load_briefing_config — yml reload·기본값 머지 패턴 정합

W3 와의 차이 (한 문장):
- W3 = iCal 에서 일정을 *길어 와* 페르소나가 그림. W5 = 사용자가 *직접 붙여 넣은* 회의
  메모를 페르소나가 *구조화*. 즉 W5 는 fetch 단계가 없고 *paste 가 곧 입력*.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger("doklgaenger-w5-meeting-notes")

# ─────────────────────────────────────────────────────────────
# 상수 — bot.py 정합
# ─────────────────────────────────────────────────────────────

CLAUDE_MODEL = "sonnet"          # bot.py 와 동일
CLAUDE_CLI_TIMEOUT = 90          # 초 — bot.py 정합 (긴 회의록도 안전 마진)
MAX_REPLY_CHARS = 4000           # 텔레그램 단일 메시지 한도 (bot.py 정합)

# 이 길이 이상의 *일반 메시지*는 "회의 메모를 붙여 넣은 것"으로 간주하는 휴리스틱.
# bot.py 가 /notes·자연어 트리거에 안 걸린 긴 메시지를 회의록 모드로 자동 인식할 때 사용.
# 너무 낮으면 평범한 장문 수다까지 회의록으로 처리됨 — 600자는 *대화 로그/메모* 분량 기준.
AUTO_NOTES_MIN_CHARS = 600


# ─────────────────────────────────────────────────────────────
# 설정 로드 — config/meeting_notes.yml
# ─────────────────────────────────────────────────────────────

# 섹션 on/off — 어떤 항목을 회의록에 포함할지. 모두 끄면 한 줄 요약만.
DEFAULT_SECTIONS = {
    "summary": True,         # 한 줄 요약
    "discussion": True,      # 핵심 논의
    "decisions": True,       # 결정사항
    "action_items": True,    # 액션아이템 (담당·기한)
    "open_questions": True,  # 미해결 질문
}

DEFAULT_MEETING_CFG = {
    "enabled": True,
    "sections": dict(DEFAULT_SECTIONS),
    "length": "medium",                 # short | medium | long
    "action_item_format": "checkbox",   # checkbox | numbered | plain
    "ack_message": "",                  # 빈 문자열이면 ack 없음
}


def load_meeting_config(path: Optional[Path] = None) -> dict:
    """`config/meeting_notes.yml` 읽어 dict 반환. 없거나 깨졌으면 기본값.

    Skill (`/setup-meeting-style`·`/tune-meeting-notes`) 이 사용자 대화로 채움.
    매 회의록 생성 시 reload — 사용자가 yml 손대도 다음 회의록부터 즉시 반영
    (briefing.py::load_briefing_config 패턴 정합 — 재시작 불필요).
    """
    if path is None:
        path = Path(__file__).resolve().parent.parent / "config" / "meeting_notes.yml"
    if not path.exists():
        return _with_defaults({})
    try:
        import yaml
    except ImportError:
        logger.warning("pyyaml 미설치 — 기본값 사용")
        return _with_defaults({})
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("meeting_notes.yml parse fail: %s", exc)
        return _with_defaults({})
    return _with_defaults(data)


def _with_defaults(data: dict) -> dict:
    """사용자 yml + 기본값 머지 (타입 안전망 포함)."""
    sections = {**DEFAULT_SECTIONS, **(data.get("sections") or {})}
    # 타입 안전망 — sections 값은 bool 로 강제
    for k in DEFAULT_SECTIONS:
        sections[k] = bool(sections.get(k))
    merged = {
        "enabled": bool(data.get("enabled", DEFAULT_MEETING_CFG["enabled"])),
        "sections": sections,
        "length": str(data.get("length") or DEFAULT_MEETING_CFG["length"]),
        "action_item_format": str(
            data.get("action_item_format") or DEFAULT_MEETING_CFG["action_item_format"]
        ),
        "ack_message": str(data.get("ack_message") or ""),
    }
    return merged


# ─────────────────────────────────────────────────────────────
# 사실 보존 시스템 프롬프트 합성 — W3 briefing 지침 정합
# ─────────────────────────────────────────────────────────────

SECTION_HINTS = {
    "summary": "**한 줄 요약** — 이 회의가 무엇이었는지 한 문장으로.",
    "discussion": "**핵심 논의** — 오간 논점을 항목별로 (사실 그대로, 살붙이기 금지).",
    "decisions": "**결정사항** — 확정된 결정만. 결정되지 않은 것은 여기 넣지 마세요.",
    "action_items": "**액션아이템** — 할 일 + *담당자* + *기한*. 메모에 담당/기한이 없으면 '(미정)' 으로 표기, 임의로 지어내지 마세요.",
    "open_questions": "**미해결 질문** — 회의에서 결론 못 낸 질문·보류 사항.",
}

ACTION_ITEM_FORMAT_HINTS = {
    "checkbox": "액션아이템은 `- [ ] 할 일 — 담당자 · 기한` 체크박스 형식으로.",
    "numbered": "액션아이템은 `1. 할 일 — 담당자 · 기한` 번호 매김 형식으로.",
    "plain": "액션아이템은 `- 할 일 (담당자, 기한)` 단순 리스트 형식으로.",
}

LENGTH_HINTS = {
    "short": "전체를 짧게 — 각 항목 1줄. 군더더기 0.",
    "medium": "각 항목 1~2줄. 핵심만 명료하게.",
    "long": "각 항목에 맥락을 한 줄 더 — 단 *메모에 있는 사실 범위 안에서만*.",
}


def build_meeting_notes_system_prompt(persona_prompt: str, config: dict) -> str:
    """페르소나 시스템 프롬프트 + 회의록 구조화 지침 합성.

    페르소나 톤은 그대로 두고, *회의 메모를 어떻게 구조화할지*만 덧붙여요.
    briefing.py::build_briefing_system_prompt 의 *합성 패턴* 과 *사실 보존 지침* 정합.

    핵심: **사실 보존** — 참석자·결정·숫자·날짜는 메모에 적힌 그대로. 페르소나는 톤만 입혀요.
    """
    sections = config.get("sections") or DEFAULT_SECTIONS
    length = config.get("length") or DEFAULT_MEETING_CFG["length"]
    ai_fmt = config.get("action_item_format") or DEFAULT_MEETING_CFG["action_item_format"]

    # 켜진 섹션만, yml 순서가 아니라 *고정 논리 순서*로 — 회의록 가독성.
    ordered = ["summary", "discussion", "decisions", "action_items", "open_questions"]
    enabled_lines = [
        f"- {SECTION_HINTS[name]}" for name in ordered if sections.get(name)
    ]
    if not enabled_lines:
        # 모든 섹션 off → 최소한 한 줄 요약은 강제 (빈 회의록 방지)
        enabled_lines = [f"- {SECTION_HINTS['summary']}"]

    length_hint = LENGTH_HINTS.get(length, LENGTH_HINTS["medium"])
    ai_hint = ACTION_ITEM_FORMAT_HINTS.get(ai_fmt, ACTION_ITEM_FORMAT_HINTS["checkbox"])

    addendum = (
        "\n\n---\n\n"
        "## 회의록 구조화 지침 (W5)\n\n"
        "사용자가 *회의 메모 또는 대화 로그*를 붙여 넣을 거예요.\n"
        "당신은 페르소나의 톤을 *그대로* 유지하면서 그 메모를 아래 구조의 회의록으로 정리해 주세요.\n\n"
        "### 포함할 섹션 (이 순서대로, 켜진 것만)\n"
        + "\n".join(enabled_lines)
        + "\n\n"
        "### 작성 규칙\n"
        f"- 길이: {length_hint}\n"
        f"- {ai_hint}\n"
        "- **사실 보존 (가장 중요)**: 참석자 이름·결정 내용·숫자·날짜·기한은 메모에 적힌 *그대로* 옮기세요.\n"
        "  바꾸거나 반올림하거나 추측하지 마세요. 회의록은 *재확인용*이에요.\n"
        "- **메모에 없는 사실을 만들지 마세요** — 빠진 정보는 '(메모에 없음)' 또는 '(미정)' 으로 표기.\n"
        "- 한 섹션에 내용이 없으면 그 섹션 제목 아래 '(해당 없음)' 한 줄.\n"
        "- 메타 코멘트(예: '이렇게 정리해 봤어요') 없이 *회의록 본문*만. 단, 페르소나의 짧은 인사·마무리 한 줄은 평소대로 OK.\n"
        "- 출력은 그대로 텔레그램·노션에 붙여 넣을 수 있게 마크다운 헤딩(`##`)으로 섹션을 구분하세요.\n"
    )
    return (persona_prompt.strip() + addendum).strip()


# ─────────────────────────────────────────────────────────────
# 회의록 생성 — Claude Code CLI 서브프로세스
# ─────────────────────────────────────────────────────────────

def generate_meeting_notes(
    persona_prompt: str,
    raw_text: str,
    config: Optional[dict] = None,
) -> str:
    """회의 메모(raw_text) → 페르소나 톤 구조화 회의록.

    bot.py::call_claude_code 정합 패턴 — Claude Code CLI 서브프로세스.
    참가자 본인 Claude Code 구독 사용량 안에서 동작 — 별도 API 키 0.

    Args:
        persona_prompt: 페르소나 시스템 프롬프트 (bot.py 가 보유).
        raw_text: 사용자가 붙여 넣은 회의 메모/대화 로그.
        config: load_meeting_config() 결과. None 이면 즉시 로드.

    Returns:
        텔레그램에 흘려 보낼 회의록 텍스트 (Markdown). 길이 자르기는 *호출부*(bot.py
        의 분할 발송)가 담당 — 여기서는 자르지 않아요 (긴 회의록을 통째로 반환).

    실패 시: 사용자에게 보일 친절한 에러 한 줄 (페르소나 0).
    """
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return (
            "갱이가 정리할 회의 메모를 못 받았어요... 🐾\n"
            "→ 회의 메모나 대화 로그를 텍스트로 붙여 넣고 다시 시도해 주세요.\n"
            "  예: `/notes` 뒤에 메모를 붙이거나, 긴 메모를 한 메시지로 보내 주세요."
        )

    config = config or load_meeting_config()
    system_prompt = build_meeting_notes_system_prompt(persona_prompt, config)

    if shutil.which("claude") is None:
        logger.warning("claude CLI not found — 회의록 생성 불가")
        return (
            "갱이가 Claude Code CLI 를 못 찾았어요... 🐾\n"
            "→ `which claude` 로 경로가 나오는지 확인해 주세요.\n"
            "  설치·로그인은 https://docs.claude.com/claude-code/setup 참조."
        )

    cmd = [
        "claude", "-p",
        "--system-prompt", system_prompt,
        "--no-session-persistence",
        "--permission-mode", "bypassPermissions",
        "--model", CLAUDE_MODEL,
    ]
    try:
        result = subprocess.run(
            cmd,
            input=raw_text,
            capture_output=True,
            text=True,
            timeout=CLAUDE_CLI_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        logger.warning("claude timeout — 회의록 생성 중단")
        return (
            f"갱이가 회의록 만드는 데 {CLAUDE_CLI_TIMEOUT}초를 넘겼어요... 🐾\n"
            "→ 회의 메모가 아주 길면 *두세 덩어리로 나눠서* 각각 정리해 보세요."
        )
    except FileNotFoundError:
        return "갱이가 Claude Code CLI 를 못 찾았어요... 🐾 (which claude 확인)"

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()[:200]
        logger.warning("claude exit=%s stderr=%s", result.returncode, stderr)
        return (
            f"갱이가 회의록 만들다 막혔어요 (exit={result.returncode})... 🐾\n"
            f"로그 확인: `tail -f /tmp/doppel-bot.log`\n"
            f"에러: {stderr}"
        )

    output = (result.stdout or "").strip()
    if not output:
        return "갱이가 빈 회의록을 받았어요... 🐾 메모를 다시 붙여 넣어 주세요."
    return output


# ─────────────────────────────────────────────────────────────
# 회의록 모드 휴리스틱 — bot.py 가 *긴 일반 메시지* 자동 인식에 사용
# ─────────────────────────────────────────────────────────────

def looks_like_meeting_paste(text: str) -> bool:
    """`/notes`·자연어 트리거에 안 걸린 *일반 메시지*가 회의 메모처럼 보이는지.

    W5 단순 휴리스틱 (과설계 금지):
    - 충분히 긴 텍스트(AUTO_NOTES_MIN_CHARS 이상)이고,
    - 여러 줄로 되어 있으면 (회의 메모·대화 로그는 보통 줄바꿈이 많음)
    회의 메모 붙여넣기로 간주.

    이 함수가 True 라도 bot.py 는 *바로 회의록을 만들지 않고* 짧게 물어볼 수 있어요
    ("회의록으로 정리할까요?") — 오탐 시 사용자가 거절 가능. (분기는 bot.py 정책.)
    """
    if not text:
        return False
    stripped = text.strip()
    if len(stripped) < AUTO_NOTES_MIN_CHARS:
        return False
    # 줄바꿈 2개 이상 = 여러 줄 메모/로그로 추정
    return stripped.count("\n") >= 2
