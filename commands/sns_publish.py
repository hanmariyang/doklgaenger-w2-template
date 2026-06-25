"""도클갱어 W6 부가기능 — 텔레그램 글 → 페르소나 톤 변환 → MBTI SNS 자동 게시.

신경계 비유:
- 텔레그램에 *던진 메모 한 줄*(원재료)이 들어오면,
- 페르소나(뇌·언어 피질)가 그 메모를 *자기 톤의 짧은 SNS 글*로 다시 적되 *사실은 보존*하고,
- 사용자가 *미리보기를 눈으로 확인*한 뒤 [게시] 버튼을 누르면 그제서야
- MBTI SNS(외부 세계 — 원탁 시스템)로 *손을 뻗어* 글을 흘려 보내요.

설계 원칙 (TF-1060 — W2 인프라 그대로 + 기능 1개, 미리보기→확인 게이트):
- 입력 = 텍스트 한 가지. `/sns <내용>` *명령 전용* — 자연어 자동 인식 X (사적 채팅 보호).
- 변환 = 페르소나 톤 짧은 SNS 글. *사실 보존* — 숫자·고유명사 임의 생성 금지 (W3/W5 정합).
- 게시 = *항상 미리보기 후 확인*. 공개·되돌리기 어려운 게시라 확인 게이트 필수
  (W4 의 "봇이 멋대로 공개 발송 안 함" 안전 원칙 정합).
- 출력 = 게시 성공 시 post id + URL.
- 새 외부 의존성 0 — requests(이미 보유) 재사용. outbound HTTP 1종(MCP)뿐.
- 미설정(MBTI_SNS_API_KEY 없음) 시 자동 OFF — W2~W5 정상 동작.

차용 출처:
- commands/meeting_notes.py — Claude CLI 서브프로세스 + 사실보존 시스템 프롬프트 합성 패턴
- commands/briefing.py::fetch_ical_bytes — requests 사용 패턴 (새 dep 금지)
- commands/meeting_notes.py::load_meeting_config — yml reload·기본값 머지 패턴

mbti.triforge.kr 은 *원탁(외부) 시스템*이에요 — 우리는 *연결만* 하고, 그쪽 파일은
건드리지 않아요 (격리 원칙). 게시(쓰기)는 *MCP HTTP 전용* — REST 쓰기 없음.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger("doklgaenger-w6-sns")

# ─────────────────────────────────────────────────────────────
# 상수 — bot.py / meeting_notes.py 정합
# ─────────────────────────────────────────────────────────────

CLAUDE_MODEL = "sonnet"          # bot.py 와 동일
CLAUDE_CLI_TIMEOUT = 90          # 초 — bot.py 정합 (긴 응답 안전 마진)
HTTP_TIMEOUT = 30                # 초 — MCP 핸드셰이크 (의뢰자 명시)

DEFAULT_MCP_URL = "https://mbti-mcp.triforge.kr/mcp"
DEFAULT_MAX_LEN = 280            # SNS 글 권장 길이 (트위터 등급)
MBTI_POST_URL_TMPL = "https://mbti.triforge.kr/post/{id}/"

# MCP 툴 이름 — 게시. (댓글 mbti_write_comment 는 이번 범위 밖 — 만들지 않음.)
MCP_CREATE_POST_TOOL = "mbti_create_post"


# ─────────────────────────────────────────────────────────────
# 설정 로드 — config/sns.yml
# ─────────────────────────────────────────────────────────────

DEFAULT_SNS_CFG = {
    "enabled": True,
    "mbti_tag": "",          # 본인 MBTI 유형 (예: "ENFP"). 빈 문자열이면 태그 없이 게시.
    "max_len": DEFAULT_MAX_LEN,
    "style": "짧고 캐주얼하게, 솔직한 한두 문장",  # 변환 톤 힌트
    "ack": {
        "converting": "",    # 변환 시작 시 텔레그램 ack 한 줄 (비우면 안 보냄)
    },
}


def load_sns_config(path: Optional[Path] = None) -> dict:
    """`config/sns.yml` 읽어 dict 반환. 없거나 깨졌으면 기본값.

    Skill (`/setup-sns`) 이 사용자 대화로 채움.
    매 `/sns` 호출 시 reload — 사용자가 yml 손대도 다음 글부터 즉시 반영
    (meeting_notes.py::load_meeting_config 패턴 정합 — 재시작 불필요).
    """
    if path is None:
        path = Path(__file__).resolve().parent.parent / "config" / "sns.yml"
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
        logger.warning("sns.yml parse fail: %s", exc)
        return _with_defaults({})
    return _with_defaults(data)


def _with_defaults(data: dict) -> dict:
    """사용자 yml + 기본값 머지 (타입 안전망 포함)."""
    try:
        max_len = int(data.get("max_len") or DEFAULT_MAX_LEN)
    except (TypeError, ValueError):
        max_len = DEFAULT_MAX_LEN
    if max_len <= 0:
        max_len = DEFAULT_MAX_LEN
    ack_data = data.get("ack") or {}
    if not isinstance(ack_data, dict):
        ack_data = {}
    return {
        "enabled": bool(data.get("enabled", DEFAULT_SNS_CFG["enabled"])),
        "mbti_tag": str(data.get("mbti_tag") or "").strip().upper(),
        "max_len": max_len,
        "style": str(data.get("style") or DEFAULT_SNS_CFG["style"]),
        "ack": {
            "converting": str(ack_data.get("converting") or ""),
        },
    }


# ─────────────────────────────────────────────────────────────
# 사실 보존 시스템 프롬프트 합성 — meeting_notes 사실보존 지침 정합
# ─────────────────────────────────────────────────────────────

def build_sns_system_prompt(persona_prompt: str, config: dict) -> str:
    """페르소나 시스템 프롬프트 + SNS 글 변환 지침 합성.

    페르소나 톤은 그대로 두고, *사용자 메모를 어떻게 짧은 SNS 글로 다시 쓸지*만 덧붙여요.
    meeting_notes.py::build_meeting_notes_system_prompt 의 *합성 패턴* 과 *사실 보존 지침* 정합.

    핵심: **사실 보존** — 숫자·고유명사는 메모에 적힌 그대로. 페르소나는 톤만 입혀요.
    """
    max_len = config.get("max_len") or DEFAULT_MAX_LEN
    style = config.get("style") or DEFAULT_SNS_CFG["style"]

    addendum = (
        "\n\n---\n\n"
        "## SNS 게시글 변환 지침 (W6)\n\n"
        "사용자가 *짧은 메모/생각*을 보낼 거예요.\n"
        "당신은 페르소나의 톤을 *그대로* 유지하면서 그 메모를 *본인 톤의 짧은 SNS 게시글*로 다시 써 주세요.\n\n"
        "### 작성 규칙\n"
        f"- 길이: **{max_len}자 이내**. 짧을수록 좋아요 (SNS 글은 한눈에 읽혀야 해요).\n"
        f"- 톤 힌트: {style}\n"
        "- **사실 보존 (가장 중요)**: 메모에 있는 숫자·고유명사·날짜는 *그대로*. "
        "메모에 없는 사실·수치·인용을 *지어내지 마세요*.\n"
        "- **압축보다 보존**: 길이를 줄이려고 메모의 *핵심 숫자·고유명사를 지우지 마세요* "
        "(DVA — 공개 게시라 손실 영구). 줄일 게 마땅찮으면 원문을 거의 그대로 두세요.\n"
        "- 해시태그는 자제 (붙여도 1개 이내). 과한 이모지 자제.\n"
        "- 메타 코멘트(예: '이렇게 써 봤어요', '게시할까요?') 없이 **게시글 본문만** 출력하세요.\n"
        "- 따옴표·마크다운 헤딩으로 감싸지 말고, 그대로 SNS 에 올릴 *순수 본문 텍스트*로.\n"
    )
    return (persona_prompt.strip() + addendum).strip()


# ─────────────────────────────────────────────────────────────
# SNS 글 생성 — Claude Code CLI 서브프로세스
# ─────────────────────────────────────────────────────────────

def generate_sns_post(
    persona_system_prompt: str,
    raw_text: str,
    config: Optional[dict] = None,
) -> str:
    """사용자 메모(raw_text) → 페르소나 톤 짧은 SNS 글.

    meeting_notes.py::generate_meeting_notes 정합 패턴 — Claude Code CLI 서브프로세스.
    참가자 본인 Claude Code 구독 사용량 안에서 동작 — 별도 API 키 0.

    Args:
        persona_system_prompt: build_sns_system_prompt 로 *이미 합성된* 시스템 프롬프트.
        raw_text: 사용자가 `/sns` 뒤에 붙인 메모.
        config: load_sns_config() 결과 (max_len fallback 자르기에 사용). None 이면 즉시 로드.

    Returns:
        변환된 SNS 글 초안 텍스트. 실패 시 RuntimeError (호출부가 사용자에게 안내).
    """
    raw_text = (raw_text or "").strip()
    if not raw_text:
        raise RuntimeError("변환할 메모가 비어 있어요.")

    config = config or load_sns_config()

    if shutil.which("claude") is None:
        raise RuntimeError(
            "Claude Code CLI 를 못 찾았어요 (which claude 확인). "
            "설치·로그인은 https://docs.claude.com/claude-code/setup 참조."
        )

    cmd = [
        "claude", "-p",
        "--system-prompt", persona_system_prompt,
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
        raise RuntimeError(f"Claude Code 응답이 {CLAUDE_CLI_TIMEOUT}초를 넘었어요.")
    except FileNotFoundError:
        raise RuntimeError("Claude Code CLI 를 찾을 수 없어요 (which claude 확인).")

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()[:200]
        raise RuntimeError(f"Claude Code 오류 (exit={result.returncode}): {stderr}")

    output = (result.stdout or "").strip()
    if not output:
        raise RuntimeError("Claude Code 가 빈 응답을 줬어요. 메모를 다시 보내 주세요.")

    # 안전망 — 모델이 max_len 을 넘기면 부드럽게 자른다 (게시 전 미리보기에서 사용자가 본다).
    max_len = config.get("max_len") or DEFAULT_MAX_LEN
    if len(output) > max_len:
        output = output[:max_len].rstrip()
    return output


# ─────────────────────────────────────────────────────────────
# MBTI SNS 게시 — MCP HTTP 3-스텝 핸드셰이크 (쓰기는 MCP 전용)
# ─────────────────────────────────────────────────────────────

def _mcp_headers(api_key: str, session_id: Optional[str] = None) -> dict:
    """MCP 공통 헤더. session_id 주어지면 Mcp-Session-Id 추가."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    return headers


# requests 의 응답 헤더는 대소문자 무관(CaseInsensitiveDict)이라 한 번의 .get 으로 충분하다.
# (DVA 니체 지적 — 둘째 .get 은 죽은 코드였음. 단일 키로 정리.)
_MCP_SESSION_HEADER = "mcp-session-id"


def _parse_sse_json(text: str) -> list[dict]:
    """SSE 본문(`event: message\\ndata: {json}` 줄들)에서 data: 줄의 JSON 만 모아 반환.

    응답은 SSE 형식이라 `data:` 로 시작하는 줄을 줄 단위로 훑어 json.loads.
    파싱 실패한 줄은 조용히 건너뜀.
    """
    out: list[dict] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            out.append(json.loads(payload))
        except (json.JSONDecodeError, ValueError):
            continue
    return out


def _first_result_message(messages: list[dict]) -> Optional[dict]:
    """SSE data: JSON 들 중 `id`/`result` 가 있는 JSON-RPC 응답을 취한다."""
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if "result" in msg or ("id" in msg and "error" in msg):
            return msg
    return None


def publish_post(
    content: str,
    *,
    api_key: str,
    mcp_url: str = DEFAULT_MCP_URL,
    mbti_tag: str = "",
) -> dict:
    """변환된 글을 MBTI SNS 에 게시. 성공 시 post dict 반환.

    의뢰자 실측 검증 시퀀스 — 3-스텝 MCP 핸드셰이크 (동기 / requests):
      (1) initialize     → 응답 헤더 'mcp-session-id' 확보
      (2) notifications/initialized (헤더에 Mcp-Session-Id) → 202
      (3) tools/call mbti_create_post (헤더에 Mcp-Session-Id) → result

    bot.py 에선 blocking 이라 asyncio.to_thread 로 감싼다.

    Args:
        content: 게시할 본문 (이미 변환·확인된 글).
        api_key: MBTI_SNS_API_KEY (공개 글 쓰기 권한).
        mcp_url: MBTI_SNS_MCP_URL (기본 mbti-mcp.triforge.kr/mcp).
        mbti_tag: 본인 MBTI 유형 또는 "".

    Returns:
        post dict {id, author, author_mbti, content, mbti_tag, ...}.

    Raises:
        RuntimeError: 키 만료(401)·네트워크 실패·MCP 오류 등 — 친절한 메시지 동봉.
    """
    content = (content or "").strip()
    if not content:
        raise RuntimeError("게시할 본문이 비어 있어요.")
    if not api_key:
        raise RuntimeError("MBTI_SNS_API_KEY 가 없어요. `/setup-sns` 로 키를 먼저 박아 주세요.")
    if not mcp_url:
        mcp_url = DEFAULT_MCP_URL

    try:
        import requests
    except ImportError:
        raise RuntimeError("requests 미설치 — `uv sync` 또는 `pip install requests`.")

    def _post(body: dict, session_id: Optional[str] = None, *, write: bool = False):
        """write=True 면 *게시 단계*(tools/call) — 타임아웃이 '실패'가 아니라 '불확실'이다.

        DVA 니체 지적(시나리오 D): 네트워크 타임아웃은 "안 됨"이 아니라 "*모름*"이다.
        게시 요청이 타임아웃나면 서버가 *이미 글을 만들었을 수* 있다. 이 경우 사용자에게
        "실패"가 아니라 "올라갔는지 불확실 — 피드를 먼저 확인하고 재시도"라고 정직하게 전한다.
        """
        try:
            return requests.post(
                mcp_url,
                headers=_mcp_headers(api_key, session_id),
                json=body,
                timeout=HTTP_TIMEOUT,
            )
        except requests.Timeout:
            if write:
                raise RuntimeError(
                    f"MBTI SNS 응답이 {HTTP_TIMEOUT}초를 넘었어요 — *글이 올라갔는지 불확실*해요. "
                    "다시 시도하기 전에 mbti.triforge.kr 피드를 먼저 확인해 주세요 (중복 게시 방지)."
                )
            raise RuntimeError(f"MBTI SNS 응답이 {HTTP_TIMEOUT}초를 넘었어요 (네트워크 확인).")
        except requests.RequestException as exc:
            raise RuntimeError(f"MBTI SNS 연결 실패: {type(exc).__name__}: {str(exc)[:150]}")

    def _check_auth(resp) -> None:
        if resp.status_code == 401:
            raise RuntimeError(
                "MBTI SNS 인증 실패 (401) — API 키가 만료됐거나 잘못됐어요. "
                "mbti.triforge.kr 에서 재발급 후 `.env` 의 MBTI_SNS_API_KEY 를 갱신하고 봇을 재시작해 주세요."
            )

    # ── (1) initialize — 세션 ID 확보 ──
    init_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "doklgaenger-bot", "version": "1.0"},
        },
    }
    resp = _post(init_body)
    _check_auth(resp)
    if resp.status_code >= 400:
        raise RuntimeError(
            f"MBTI SNS initialize 실패 (HTTP {resp.status_code}): {(resp.text or '')[:200]}"
        )
    session_id = resp.headers.get(_MCP_SESSION_HEADER)
    if not session_id:
        raise RuntimeError("MBTI SNS 가 세션 ID(mcp-session-id) 를 주지 않았어요. 엔드포인트를 확인해 주세요.")

    # ── (2) notifications/initialized → 202 (헤더에 세션 ID) ──
    initialized_body = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    }
    resp2 = _post(initialized_body, session_id=session_id)
    _check_auth(resp2)
    # 202(Accepted) 가 정상. 그 외라도 일단 진행 — 서버 구현 편차 흡수.
    if resp2.status_code >= 400:
        logger.warning("mcp initialized non-2xx: %s %s", resp2.status_code, (resp2.text or "")[:120])

    # ── (3) tools/call mbti_create_post (헤더에 세션 ID) ──
    call_body = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": MCP_CREATE_POST_TOOL,
            "arguments": {
                "content": content,
                "mbti_tag": (mbti_tag or "").strip().upper(),
            },
        },
    }
    resp3 = _post(call_body, session_id=session_id, write=True)  # write — 타임아웃=불확실
    _check_auth(resp3)
    if resp3.status_code >= 400:
        raise RuntimeError(
            f"MBTI SNS 게시 실패 (HTTP {resp3.status_code}): {(resp3.text or '')[:200]}"
        )

    messages = _parse_sse_json(resp3.text)
    result_msg = _first_result_message(messages)
    if result_msg is None:
        raise RuntimeError(
            f"MBTI SNS 응답에서 결과를 못 찾았어요: {(resp3.text or '')[:200]}"
        )
    if "error" in result_msg and result_msg.get("error"):
        err = result_msg["error"]
        msg = err.get("message") if isinstance(err, dict) else str(err)
        raise RuntimeError(f"MBTI SNS 도구 오류: {msg}")

    result = result_msg.get("result") or {}
    # result.structuredContent.post = {id, author, author_mbti, content, mbti_tag, ...}
    structured = result.get("structuredContent") or {}
    post = structured.get("post")
    if not post:
        # 일부 서버는 content[].text 안에 JSON 을 담기도 함 — best-effort fallback.
        for item in (result.get("content") or []):
            if isinstance(item, dict) and item.get("type") == "text":
                try:
                    parsed = json.loads(item.get("text") or "")
                except (json.JSONDecodeError, ValueError):
                    continue
                if isinstance(parsed, dict):
                    post = parsed.get("post") or parsed
                    break
    if not post or not isinstance(post, dict):
        raise RuntimeError(
            f"MBTI SNS 가 post 정보를 주지 않았어요: {json.dumps(result)[:200]}"
        )
    return post


def post_url(post: dict) -> str:
    """post dict → 게시글 URL. id 없으면 빈 문자열."""
    pid = post.get("id") if isinstance(post, dict) else None
    if pid is None:
        return ""
    return MBTI_POST_URL_TMPL.format(id=pid)
