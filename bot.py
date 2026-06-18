"""도클갱어 W2/W3 — 텔레그램 페르소나 챗봇 (Claude Code CLI 서브프로세스 방식).

PD-938 hotfix (2026-05-21):
- 이전 버전은 Anthropic API 직호출 (의뢰자 카드 과금).
- 의뢰자 의도 정합: Claude Code CLI 를 서브프로세스로 호출 → 참가자 본인 Claude Code
  구독 사용량 안에서 동작 → 추가 과금 0.
- 패턴은 Triforge `agents/services/persona_engine.py::_call_claude_code` 정합.

TF-958 W3 (2026-05-28):
- *기능 1개 추가* — 캘린더 아침 브리핑.
- 자연어 트리거 ("오늘 일정", "오늘 뭐 있어", "브리핑") + `/today` 명령 + JobQueue 자동 푸시.
- 인프라(텔레그램·CLI·페르소나)는 그대로. 페르소나는 system_prompt + briefing 지침 합성.

TF-981 W4 (2026-06-04):
- *기능 1개 추가* — 슬랙 멘션 답변 어시스턴트 (Socket Mode).
- `SLACK_APP_TOKEN` + `SLACK_BOT_TOKEN` 박혀 있으면 PTB post_init 훅에서
  백그라운드 task 로 Socket Mode WebSocket 가동. 미박혀 있으면 silent skip.
- 슬랙은 *outbound only* — 답신 X. 멘션 → Claude 답변 초안 → *본인 텔레그램*으로 push.
- 운영자 서버 의존 0. 참가자가 자기 슬랙 앱 manifest import → 자기 토큰 발급 → 자기 노트북.

TF-1040 W5 (2026-06-18):
- *기능 1개 추가* — 회의록 요약 어시스턴트.
- `/notes` 명령 + 자연어("회의록","회의 정리","정리해줘"…) 부분 매칭 + 긴 메모 자동 인식.
- 사용자가 회의 메모/대화 로그를 *붙여 넣으면* 페르소나가 구조화 회의록으로 변환.
  음성·STT 0 (의도적 단순화). 사실 보존 — 참석자·결정·숫자·날짜는 그대로, 톤만 입힘.
- 긴 회의록은 텔레그램 4096자 한도를 넘으니 *여러 메시지로 분할 발송*.

신경계 비유:
- 텔레그램·슬랙(감각기관 둘)이 입력을 받아 들이고,
- Claude Code CLI(뇌)가 페르소나 시스템 프롬프트로 응답을 만들어
- 텔레그램으로 *흘려 보내요* (슬랙으로는 안 보내요 — 본인 손에 맡김).

설계 원칙:
- 페르소나는 `persona/system_prompt.md` 한 파일에서만 흘러나온다 (Single Source).
- 1봇 = 1페르소나. chat_id 별 분리 없음 — W2 단순화.
- 로깅은 stdout/stderr 그대로, scripts/start.sh 가 /tmp/doppel-bot.log 로 redirect.
- *Claude API 키 불필요* — Claude Code 가 로그인 상태이기만 하면 OK.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from commands.briefing import generate_briefing, load_briefing_config
from commands.slack_mention import start_slack_socket_mode  # W4, TF-981
from commands.meeting_notes import (  # W5, TF-1040
    AUTO_NOTES_MIN_CHARS,
    generate_meeting_notes,
    load_meeting_config,
    looks_like_meeting_paste,
)

# ─────────────────────────────────────────────────────────────
# 설정 — 갱이가 미리 정해 둔 상수
# ─────────────────────────────────────────────────────────────

CLAUDE_MODEL = "sonnet"  # Claude Code CLI 의 --model 값 (sonnet/opus/haiku 또는 풀 모델명)
CLAUDE_CLI_TIMEOUT = 90  # 초 — Triforge persona_engine 정합 (긴 응답 안전 마진)
PERSONA_PATH = Path(__file__).parent / "persona" / "system_prompt.md"
MAX_REPLY_CHARS = 4000  # 텔레그램 단일 메시지 한도(4096) 미만으로 자름

# W3 (TF-958) — 자연어로 브리핑을 부르는 패턴.
# 한국어 + 영어 키워드. 정규식으로 *부분 매칭* → 메시지 어디든 들어 있으면 트리거.
BRIEFING_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"오늘\s*일정",
        r"오늘\s*뭐\s*있",        # "오늘 뭐 있어", "오늘 뭐 있지"
        r"오늘\s*스케",           # "오늘 스케줄"
        r"브리핑",
        r"briefing",
        r"today.*schedule",
    )
]

# W5 (TF-1040) — 자연어로 회의록을 부르는 패턴.
# 메시지에 부분 매칭 → 들어 있으면 회의록 모드로 라우팅.
# 단, *메모 본문 안에* 우연히 "정리해줘" 가 섞여 있을 수도 있으니, 회의록 트리거는
# message_handler 에서 *briefing 다음·긴 메모 자동인식 앞* 순서로 본다 (아래 우선순위 주석 참조).
MEETING_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"회의록",
        r"회의\s*정리",
        r"회의\s*내용",
        r"회의\s*요약",
        r"정리\s*해\s*줘",        # "정리해줘", "정리 해 줘"
        r"meeting\s*notes",
        r"minutes",
    )
]

KST = ZoneInfo("Asia/Seoul")

# 안내 메시지 — 갱이 톤
FRIENDLY_MISSING_TELEGRAM_MSG = (
    "갱이가 텔레그램 토큰을 못 찾았어요... 🐾\n"
    "→ `.env.example` 을 복사해서 `.env` 를 만들고\n"
    "  `TELEGRAM_BOT_TOKEN` 을 채워 주세요.\n"
    "  발급은 `docs/botfather-guide.md` 를 봐 주세요."
)

FRIENDLY_MISSING_CLAUDE_CLI_MSG = (
    "갱이가 Claude Code CLI 를 못 찾았어요... 🐾\n"
    "→ Claude Code 가 설치·로그인 되어 있는지 확인해 주세요.\n"
    "  `which claude` 로 경로가 나와야 해요.\n"
    "  설치는 https://docs.claude.com/claude-code/setup 참조."
)

FRIENDLY_MISSING_PROMPT_MSG = (
    "갱이가 페르소나 시스템 프롬프트를 못 찾았어요... 🐾\n"
    "→ `/research-persona` 스킬로 `persona/system_prompt.md` 를 먼저 작성해 주세요.\n"
    "  템플릿은 `persona/system_prompt.md.example` 에 있어요."
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("doklgaenger-w2")


# ─────────────────────────────────────────────────────────────
# 페르소나 — 시스템 프롬프트 한 파일에서 읽는다
# ─────────────────────────────────────────────────────────────

def load_system_prompt() -> str:
    """`persona/system_prompt.md` 를 읽어 시스템 프롬프트로 반환.

    파일이 없으면 FileNotFoundError 를 던져서 호출부가 사용자에게 안내하게 한다.
    봇 시작 시 한 번만 읽고 in-memory 보관 — 페르소나는 *성격* 같은 것.
    """
    if not PERSONA_PATH.exists():
        raise FileNotFoundError(PERSONA_PATH)
    return PERSONA_PATH.read_text(encoding="utf-8").strip()


# ─────────────────────────────────────────────────────────────
# Claude Code CLI 호출 — 뇌 (서브프로세스 패턴)
# ─────────────────────────────────────────────────────────────

def call_claude_code(system_prompt: str, user_text: str) -> str:
    """Claude Code CLI 를 서브프로세스로 호출. stdin 으로 user 메시지 전달.

    Triforge `agents/services/persona_engine.py::_call_claude_code` 정합.
    참가자 Claude Code 구독 사용량 안에서 동작 — 별도 API 키 불필요.

    옵션 의미:
    - `-p` (--print): 비대화형 단일 응답 모드.
    - `--system-prompt`: 페르소나 시스템 프롬프트 주입.
    - `--no-session-persistence`: 매 호출 독립 세션 (대화 컨텍스트 X — W2 단순화).
    - `--permission-mode bypassPermissions`: 봇 서브프로세스라 사용자 prompt 없이 진행.
    - `--model sonnet`: 기본 모델. 구독 한도 안에서.
    """
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
            input=user_text,
            capture_output=True,
            text=True,
            timeout=CLAUDE_CLI_TIMEOUT,
        )
    except FileNotFoundError:
        # main() 에서 사전 체크하지만 안전망.
        raise RuntimeError("Claude Code CLI 를 찾을 수 없어요 (which claude 확인).")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Claude Code 응답이 {CLAUDE_CLI_TIMEOUT}초를 넘었어요.")

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()[:300]
        raise RuntimeError(f"Claude Code 오류 (exit={result.returncode}): {stderr}")

    output = (result.stdout or "").strip()
    if not output:
        return "(빈 응답)"
    if len(output) > MAX_REPLY_CHARS:
        output = output[:MAX_REPLY_CHARS] + "\n\n…(텔레그램 길이 한도로 잘림)"
    return output


# ─────────────────────────────────────────────────────────────
# 텔레그램 핸들러 — 감각기관
# ─────────────────────────────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/start` — 페르소나 첫 인사 안내."""
    await update.message.reply_text(
        "안녕하세요 🐾\n"
        "이 봇은 도클갱어 페르소나 챗봇이에요.\n"
        "메시지를 보내 주시면 페르소나로 답변해 드려요.\n"
        "오늘 일정이 궁금하면 `/today` 또는 “오늘 일정”,\n"
        "회의 메모를 정리하려면 `/notes` 뒤에 메모를 붙이거나 “회의록” 이라고 보내 주세요."
    )


async def _reply_safe(update: Update, text: str) -> None:
    """Markdown → 파싱 실패 시 plain text fallback. (재사용 헬퍼)"""
    try:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except BadRequest as exc:
        logger.warning("markdown_parse_failed fallback_to_plain: %s", exc)
        await update.message.reply_text(text)


def _is_briefing_trigger(text: str) -> bool:
    """메시지 텍스트가 *오늘 일정 브리핑* 자연어 트리거에 매칭되는지.

    W3 (TF-958) — 패턴 리스트는 모듈 상단 BRIEFING_PATTERNS 참조.
    """
    if not text:
        return False
    return any(p.search(text) for p in BRIEFING_PATTERNS)


async def _send_briefing(update_or_chat, context: ContextTypes.DEFAULT_TYPE) -> None:
    """브리핑 생성·발송 — `/today`·자연어·자동 푸시가 공통 사용.

    update_or_chat: Update 객체이거나 chat_id (int). 자동 푸시 시 chat_id 만 전달.

    TF-958 hotfix2: 즉시 ack 메시지 — yml `style.ack_message` 가 비어있지 않으면
    *Claude 호출 전*에 페르소나 톤 1줄 발송. 사용자가 처리 중인지 즉시 인지.
    """
    system_prompt = context.bot_data["system_prompt"]
    config = load_briefing_config()  # 매 호출 reload — 사용자가 yml 손대도 즉시 반영

    # ── 즉시 ack 발송 (페르소나 톤, yml 에서 읽음) ──
    ack = (config.get("style") or {}).get("ack_message") or ""
    if ack and ack.strip():
        chat_id_for_ack = (
            update_or_chat.message.chat_id if isinstance(update_or_chat, Update)
            else update_or_chat
        )
        try:
            await context.bot.send_message(chat_id=chat_id_for_ack, text=ack.strip())
        except Exception as exc:  # noqa: BLE001
            logger.warning("ack_send_failed: %s", exc)

    try:
        text = generate_briefing(system_prompt, config=config)
    except Exception as exc:  # noqa: BLE001
        logger.exception("briefing_failed")
        text = (
            f"갱이가 오늘 일정을 가져오다 막혔어요... 🐾\n"
            f"로그 확인: `tail -f /tmp/doppel-bot.log`\n"
            f"에러: {type(exc).__name__}: {str(exc)[:200]}"
        )
    if len(text) > MAX_REPLY_CHARS:
        text = text[:MAX_REPLY_CHARS] + "\n\n…(텔레그램 길이 한도로 잘림)"

    if isinstance(update_or_chat, Update):
        await _reply_safe(update_or_chat, text)
    else:
        # 자동 푸시 — chat_id 직접 발송
        chat_id = update_or_chat
        try:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
        except BadRequest:
            await context.bot.send_message(chat_id=chat_id, text=text)


async def today_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/today` — 오늘 일정 브리핑 즉시 발송 (W3, TF-958)."""
    chat_id = update.message.chat_id
    logger.info("today_command chat_id=%s", chat_id)
    await _send_briefing(update, context)


# ─────────────────────────────────────────────────────────────
# W5 (TF-1040) — 회의록 요약 어시스턴트
# ─────────────────────────────────────────────────────────────

def _split_for_telegram(text: str, limit: int = MAX_REPLY_CHARS) -> list[str]:
    """긴 텍스트를 텔레그램 4096자 한도에 맞춰 *여러 조각*으로 나눈다.

    회의록은 브리핑·답변 초안과 달리 길어질 수 있어요 (여러 섹션). W2~W4 처럼 잘라 버리면
    뒤쪽 결정사항·액션아이템이 사라지므로, W5 는 *자르지 않고 분할 발송* 합니다.

    경계 우선순위 — 가독성을 위해 *문단(빈 줄) → 줄 → 강제 슬라이스* 순으로 끊어요:
    1) 빈 줄(`\\n\\n`) 단위로 묶어 limit 안에서 채운다.
    2) 한 문단이 단독으로 limit 보다 길면 줄(`\\n`) 단위로 쪼갠다.
    3) 한 줄이 단독으로 limit 보다 길면 limit 길이로 강제 슬라이스.
    """
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    buf = ""

    def _flush() -> None:
        nonlocal buf
        if buf.strip():
            chunks.append(buf.strip())
        buf = ""

    for para in text.split("\n\n"):
        block = para if not buf else "\n\n" + para
        if len(buf) + len(block) <= limit:
            buf += block
            continue
        # 현재 버퍼를 비우고 새 문단을 단독 처리
        _flush()
        if len(para) <= limit:
            buf = para
            continue
        # 문단이 단독으로도 limit 초과 → 줄 단위로 쪼갬
        for line in para.split("\n"):
            line_block = line if not buf else "\n" + line
            if len(buf) + len(line_block) <= limit:
                buf += line_block
                continue
            _flush()
            if len(line) <= limit:
                buf = line
                continue
            # 한 줄이 단독으로도 limit 초과 → 강제 슬라이스
            for k in range(0, len(line), limit):
                chunks.append(line[k:k + limit])
    _flush()
    return chunks


def _is_meeting_trigger(text: str) -> bool:
    """메시지 텍스트가 *회의록* 자연어 트리거에 매칭되는지.

    W5 (TF-1040) — 패턴 리스트는 모듈 상단 MEETING_PATTERNS 참조.
    """
    if not text:
        return False
    return any(p.search(text) for p in MEETING_PATTERNS)


async def _send_meeting_notes(update: Update, raw_text: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """회의록 생성·발송 — `/notes`·자연어·긴 메모 자동인식이 공통 사용.

    raw_text: 회의록으로 정리할 *메모 본문* (트리거 키워드는 호출부에서 제거 후 전달).

    W3 _send_briefing 패턴 정합:
    - yml `ack_message` 가 비어있지 않으면 *Claude 호출 전* 페르소나 톤 ack 한 줄.
    - 긴 회의록은 _split_for_telegram 으로 *여러 메시지 분할 발송*.
    """
    system_prompt = context.bot_data["system_prompt"]
    config = load_meeting_config()  # 매 호출 reload — 사용자가 yml 손대도 즉시 반영

    if not config.get("enabled", True):
        await _reply_safe(update, "갱이가 회의록 기능이 꺼져 있는 걸 봤어요 🐾 (config/meeting_notes.yml 의 enabled)")
        return

    # ── 즉시 ack 발송 (페르소나 톤, yml 에서 읽음) ──
    ack = (config.get("ack_message") or "").strip()
    if ack:
        try:
            await context.bot.send_message(chat_id=update.message.chat_id, text=ack)
        except Exception as exc:  # noqa: BLE001
            logger.warning("meeting_ack_send_failed: %s", exc)

    notes_ok = False
    try:
        notes = await asyncio.to_thread(
            generate_meeting_notes, system_prompt, raw_text, config
        )
        notes_ok = True
    except Exception as exc:  # noqa: BLE001
        logger.exception("meeting_notes_failed")
        notes = (
            f"갱이가 회의록 만들다 막혔어요... 🐾\n"
            f"로그 확인: `tail -f /tmp/doppel-bot.log`\n"
            f"에러: {type(exc).__name__}: {str(exc)[:200]}"
        )

    # ── 자유 실습 (선택, W5 TF-1040) — 회의록 DB 저장 훅 ───────────────
    # config 의 store.enabled: true 이고 생성이 성공했을 때만 시도.
    # commands/notes_store.py 의 save_meeting_notes 는 *기본 미구현* — 참가자가
    # 본인 DB 로 직접 채우는 자유 실습. 저장 실패·미구현은 회의록 발송을 절대 막지 않음.
    # 가이드: Claude Code 안에서 /save-notes-db
    if notes_ok and (config.get("store") or {}).get("enabled"):
        try:
            from commands.notes_store import save_meeting_notes
            record = {
                "created_at": datetime.now(KST).isoformat(timespec="seconds"),
                "chat_id": update.message.chat_id,
                "raw_text": raw_text,
                "notes": notes,
            }
            if await asyncio.to_thread(save_meeting_notes, record):
                logger.info("meeting_notes_saved chat_id=%s", update.message.chat_id)
        except NotImplementedError:
            logger.info(
                "meeting_notes_store: store.enabled 인데 save_meeting_notes 가 아직 비어 있어요 — "
                "자유 실습: commands/notes_store.py 를 본인 DB 로 채워 보세요 (/save-notes-db)."
            )
        except Exception as exc:  # noqa: BLE001 — 저장 실패가 회의록 발송을 막지 않게
            logger.warning("meeting_notes_store_failed: %s", exc)

    # 긴 회의록 → 분할 발송. 한 조각이면 markdown fallback 까지 _reply_safe 재사용.
    parts = _split_for_telegram(notes)
    if not parts:
        await update.message.reply_text("(빈 회의록을 받았어요 — 메모를 다시 붙여 주세요)")
        return
    if len(parts) == 1:
        await _reply_safe(update, parts[0])
        return
    logger.info("meeting_notes_split parts=%s chat_id=%s", len(parts), update.message.chat_id)
    for idx, part in enumerate(parts, start=1):
        labeled = f"({idx}/{len(parts)})\n\n{part}"
        try:
            await update.message.reply_text(labeled, parse_mode=ParseMode.MARKDOWN)
        except BadRequest:
            await update.message.reply_text(labeled)


async def notes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/notes` — 회의록 즉시 생성 (W5, TF-1040).

    `/notes` 뒤에 메모를 같이 붙이면 그 메모를 정리. 명령만 보내면 붙여넣기 안내.
    """
    chat_id = update.message.chat_id
    # `/notes ...메모...` 형태에서 명령 토큰 뒤 본문만 추출
    full = (update.message.text or "")
    raw = full.split(maxsplit=1)
    body = raw[1].strip() if len(raw) > 1 else ""
    logger.info("notes_command chat_id=%s body_len=%s", chat_id, len(body))
    if not body:
        await update.message.reply_text(
            "갱이가 회의록으로 정리해 드릴게요 🐾\n"
            "→ 회의 메모나 대화 로그를 *한 메시지로* 붙여 넣어 주세요.\n"
            "  `/notes` 뒤에 바로 붙여도 되고, 그냥 긴 메모를 보내셔도 인식해요."
        )
        return
    await _send_meeting_notes(update, body, context)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """일반 메시지 → Claude Code CLI 응답.

    PD-938 hotfix2 (2026-05-21): parse_mode=Markdown 활성화.
    LLM 응답의 `**bold**` `*italic*` `` `code` ``가 raw 텍스트로 노출되던 문제 봉합.
    Markdown 파싱 실패 시(escape 문제 등) plain text 로 fallback.

    TF-958 W3 (2026-05-28): "오늘 일정/브리핑" 등 자연어 매칭 시 briefing 로 라우팅.
    매칭 안 되면 기존 페르소나 응답 그대로.

    TF-1040 W5 (2026-06-18): 라우팅 우선순위 — (1) 브리핑 자연어 → (2) 회의록 자연어
    또는 긴 메모 자동 인식 → (3) 일반 페르소나 응답. 회의록 자동 인식은 *긴 여러 줄
    메모*(looks_like_meeting_paste) 일 때만 — 짧은 잡담은 평소처럼 페르소나가 답함.
    """
    user_text = update.message.text
    chat_id = update.message.chat_id
    logger.info("incoming chat_id=%s len=%s", chat_id, len(user_text or ""))

    # TF-958 hotfix (DVA 조건 3): 들어온 chat_id 를 파일에 박는다.
    # `/setup-briefing-schedule` Skill 이 이 파일 read → yml schedule.chat_id 자동 채움.
    # 사용자가 본인 chat_id 를 *수동으로 알 필요 없음*.
    try:
        Path("/tmp/doppel-last-chat-id").write_text(str(chat_id), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass  # 파일 못 박아도 봇 진행에 영향 0

    if not user_text:
        await update.message.reply_text("(텍스트 메시지만 처리할 수 있어요)")
        return

    # W3 — 자연어 브리핑 트리거가 우선
    if _is_briefing_trigger(user_text):
        logger.info("briefing_trigger_matched chat_id=%s", chat_id)
        await _send_briefing(update, context)
        return

    # W5 — 회의록 트리거. (a) 자연어 키워드 매칭 또는 (b) 긴 여러 줄 메모 자동 인식.
    # 둘 중 하나면 회의록 모드. 트리거 키워드만 있고 본문이 거의 없으면(짧은 한 줄)
    # 붙여넣기 안내로 흘려 보냄 — 정리할 본문이 없으니까.
    meeting_kw = _is_meeting_trigger(user_text)
    long_paste = looks_like_meeting_paste(user_text)
    if meeting_kw or long_paste:
        # 트리거 키워드만 있고 본문이 짧으면(예: "회의록 정리해줘") → 안내
        if meeting_kw and not long_paste and len(user_text.strip()) < AUTO_NOTES_MIN_CHARS:
            logger.info("meeting_trigger_no_body chat_id=%s", chat_id)
            await update.message.reply_text(
                "갱이가 회의록으로 정리해 드릴게요 🐾\n"
                "→ 회의 메모나 대화 로그를 *한 메시지로* 붙여 넣어 주세요.\n"
                "  (긴 메모는 그냥 보내면 자동으로 회의록 모드로 인식해요.)"
            )
            return
        logger.info("meeting_trigger_matched chat_id=%s kw=%s long=%s", chat_id, meeting_kw, long_paste)
        await _send_meeting_notes(update, user_text, context)
        return

    try:
        system_prompt = context.bot_data["system_prompt"]
        reply = call_claude_code(system_prompt, user_text)
    except Exception as exc:  # noqa: BLE001 — 사용자에게 안내해야 하므로 의도적 광범위 캐치
        logger.exception("claude_code_call_failed")
        reply = (
            f"갱이가 응답 생성 중에 막혔어요... 🐾\n"
            f"로그 확인: `tail -f /tmp/doppel-bot.log`\n"
            f"에러: {type(exc).__name__}: {str(exc)[:200]}"
        )

    await _reply_safe(update, reply)


# ─────────────────────────────────────────────────────────────
# JobQueue — 자동 푸시 (W3, TF-958)
# ─────────────────────────────────────────────────────────────

async def _scheduled_briefing_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue 가 매일 정해진 시각에 호출하는 callback.

    context.job.chat_id 를 사용해 자동 발송. config 는 매번 reload.
    """
    chat_id = context.job.chat_id
    logger.info("scheduled_briefing_fire chat_id=%s", chat_id)
    await _send_briefing(chat_id, context)


def _register_scheduled_briefing(app) -> None:
    """`config/briefing.yml` 의 schedule 을 읽어 JobQueue 등록.

    enabled=False 또는 chat_id=0 이면 skip. 부팅 시 1회 호출.
    yml 변경 후 적용은 봇 재시작 필요 (W3 단순화).
    """
    config = load_briefing_config()
    schedule = config.get("schedule") or {}
    if not schedule.get("enabled"):
        logger.info("scheduled_briefing skipped (enabled=False)")
        return
    chat_id = int(schedule.get("chat_id") or 0)
    if not chat_id:
        logger.info("scheduled_briefing skipped (chat_id=0 — 사용자 메시지 받은 후 yml 채워 주세요)")
        return
    time_str = str(schedule.get("time") or "08:00")
    try:
        hour_str, minute_str = time_str.split(":")
        hour, minute = int(hour_str), int(minute_str)
    except Exception:  # noqa: BLE001
        logger.warning("scheduled_briefing invalid time=%s — fallback 08:00", time_str)
        hour, minute = 8, 0

    job_queue = app.job_queue
    if job_queue is None:
        logger.warning("scheduled_briefing skipped — JobQueue 없음. "
                       "`uv sync` 시 'python-telegram-bot[job-queue]' 가 설치됐는지 확인.")
        return

    run_at = dt_time(hour=hour, minute=minute, tzinfo=KST)
    job_queue.run_daily(_scheduled_briefing_job, time=run_at, chat_id=chat_id, name="briefing")
    logger.info("scheduled_briefing registered chat_id=%s time=%s KST", chat_id, run_at)


# ─────────────────────────────────────────────────────────────
# 부팅
# ─────────────────────────────────────────────────────────────

def main() -> int:
    """봇 부팅. 로딩 실패 시 exit code 로 사용자에게 신호를 준다.

    - exit 2: 텔레그램 토큰 없음
    - exit 3: 페르소나 시스템 프롬프트 없음
    - exit 4: Claude Code CLI 없음
    """
    load_dotenv()

    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        print(FRIENDLY_MISSING_TELEGRAM_MSG, file=sys.stderr)
        return 2

    if shutil.which("claude") is None:
        print(FRIENDLY_MISSING_CLAUDE_CLI_MSG, file=sys.stderr)
        return 4

    try:
        system_prompt = load_system_prompt()
    except FileNotFoundError:
        print(FRIENDLY_MISSING_PROMPT_MSG, file=sys.stderr)
        return 3

    logger.info("persona_loaded chars=%s", len(system_prompt))
    logger.info("claude_cli_path=%s", shutil.which("claude"))

    # ── W4 (TF-981) — 슬랙 Socket Mode 백그라운드 가동 헬퍼 ──
    # post_init 훅에서 호출 — PTB 의 이벤트 루프 안에서 background task 로 등록.
    # SLACK_APP_TOKEN / SLACK_BOT_TOKEN 없으면 silent skip — W2/W3 만 쓰는 사람 영향 0.
    async def _post_init(application):
        # 텔레그램 push 클로저 — bot.py 가 슬랙 모듈에 PTB bot 인스턴스를 넘김.
        # slack_user_id 는 yml 에서 사용자 본인이 박은 값. 환경변수 `TELEGRAM_PUSH_CHAT_ID` 가 있으면 우선.
        # 미설정이면 /tmp/doppel-last-chat-id 에서 학습된 값 사용 (W3 패턴 정합).
        async def _telegram_push(text: str) -> None:
            chat_id_env = os.getenv("TELEGRAM_PUSH_CHAT_ID")
            chat_id: int = 0
            if chat_id_env:
                try:
                    chat_id = int(chat_id_env)
                except ValueError:
                    pass
            if not chat_id:
                try:
                    learned = Path("/tmp/doppel-last-chat-id").read_text(encoding="utf-8").strip()
                    chat_id = int(learned) if learned else 0
                except Exception:  # noqa: BLE001
                    chat_id = 0
            if not chat_id:
                logger.warning(
                    "slack_push_skipped — chat_id 없음. "
                    "텔레그램에서 본 봇에 메시지 1회 보내거나 .env 의 TELEGRAM_PUSH_CHAT_ID 채워 주세요.",
                )
                return
            try:
                await application.bot.send_message(chat_id=chat_id, text=text)
            except Exception as exc:  # noqa: BLE001
                logger.warning("telegram_push_send_fail: %s", exc)

        # 백그라운드 task 로 슬랙 Socket Mode 가동. bot 종료 시 cancel.
        slack_task = asyncio.create_task(
            start_slack_socket_mode(system_prompt, _telegram_push),
            name="slack-socket-mode",
        )
        application.bot_data["slack_task"] = slack_task
        logger.info("slack_socket_mode_task_scheduled")

    app = ApplicationBuilder().token(telegram_token).post_init(_post_init).build()
    app.bot_data["system_prompt"] = system_prompt

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("today", today_handler))  # W3, TF-958
    app.add_handler(CommandHandler("notes", notes_handler))  # W5, TF-1040
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # W3 (TF-958) — 자동 푸시 등록. yml 없거나 enabled=False 면 silent skip.
    _register_scheduled_briefing(app)

    logger.info("bot_starting model=%s timeout=%ss", CLAUDE_MODEL, CLAUDE_CLI_TIMEOUT)
    app.run_polling(allowed_updates=Update.ALL_TYPES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
