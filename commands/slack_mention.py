"""도클갱어 W4 — 슬랙 멘션 답변 어시스턴트 (Socket Mode).

신경계 비유:
- 슬랙(또 다른 감각기관)이 *멘션* 을 길어 올리면,
- 페르소나(뇌)가 그 자리에서 답변 초안을 그려서
- 텔레그램(목소리)으로 본인에게만 흘려 보내요.

설계 원칙 (TF-981 — 운영자 부담 0, 참가자 노트북 100% 완결):
- *Slack 외부 endpoint 0*. Socket Mode 만 사용 — outbound WebSocket 하나면 끝.
- *Triforge 서버 의존 0*. 운영자가 만든 manifest YAML 을 참가자가 각자 자기 슬랙에 import.
- *자동 답신 X*. 슬랙에 답변을 보내지 않아요 — 텔레그램으로 *초안*만 흘려 보내요.
  사용자가 검토·수정 후 본인 손으로 슬랙에 붙여 넣는 흐름.
- 1봇 = 1페르소나. W2/W3 그대로 — 같은 `persona/system_prompt.md`.
- *채널·키워드 필터*는 로컬 yml. 운영자가 손댈 일 없음.

연결 구조:
    [Slack 워크스페이스]
         │ outbound WebSocket
         ▼
    [참가자 노트북 — bot.py + slack_mention.py]
         │ (멘션 감지 → Claude Code CLI subprocess → 본인 텔레그램 봇 push)
         ▼
    [본인 텔레그램]

차용 출처:
- bot.py::call_claude_code — Claude CLI 서브프로세스 패턴 그대로
- bot.py::MAX_REPLY_CHARS — 텔레그램 길이 한도 그대로

토큰 2개 (모두 자기 슬랙 앱):
- `SLACK_APP_TOKEN` (xapp-...) — App-Level Token (Socket Mode WebSocket 연결용)
- `SLACK_BOT_TOKEN` (xoxb-...) — Bot Token (Web API 호출 — 컨텍스트 조회·user info)
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger("doklgaenger-w4-slack")

# ─────────────────────────────────────────────────────────────
# 상수 — bot.py 정합
# ─────────────────────────────────────────────────────────────

CLAUDE_MODEL = "sonnet"          # bot.py 와 동일
CLAUDE_CLI_TIMEOUT = 90          # 초 — bot.py 정합
MAX_REPLY_CHARS = 4000           # 텔레그램 단일 메시지 한도 (bot.py 정합)
SLACK_CONTEXT_FETCH_LIMIT = 20   # 직전 메시지 N+α 받아서 N 개 사용 (안전 마진)


# ─────────────────────────────────────────────────────────────
# 설정 로드 — config/slack_mention.yml
# ─────────────────────────────────────────────────────────────

DEFAULT_SLACK_CFG = {
    "enabled": True,
    "slack_user_id": "",        # OAuth 후 첫 멘션에서 자동 학습 가능
    "channel_allowlist": [],    # 빈 list = 전체 채널
    "keyword_filter": [],       # 빈 list = 전체 메시지
    "context_messages": 3,      # 멘션 직전 N 개 메시지
    "ack_message": "",          # 빈 문자열이면 ack 없음
}


def load_slack_config(path: Optional[Path] = None) -> dict:
    """`config/slack_mention.yml` 읽어 dict 반환. 없거나 깨졌으면 기본값.

    Skill (`/setup-slack-filter`) 이 사용자 대화로 채움.
    매 멘션 처리 시 reload — 사용자가 yml 손대도 다음 멘션부터 즉시 반영.
    """
    if path is None:
        path = Path(__file__).resolve().parent.parent / "config" / "slack_mention.yml"
    if not path.exists():
        return dict(DEFAULT_SLACK_CFG)
    try:
        import yaml
    except ImportError:
        logger.warning("pyyaml 미설치 — 기본값 사용")
        return dict(DEFAULT_SLACK_CFG)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("slack_mention.yml parse fail: %s", exc)
        return dict(DEFAULT_SLACK_CFG)
    merged = {**DEFAULT_SLACK_CFG, **data}
    # 타입 안전망
    if not isinstance(merged.get("channel_allowlist"), list):
        merged["channel_allowlist"] = []
    if not isinstance(merged.get("keyword_filter"), list):
        merged["keyword_filter"] = []
    try:
        merged["context_messages"] = int(merged.get("context_messages") or 3)
    except (TypeError, ValueError):
        merged["context_messages"] = 3
    return merged


def save_slack_user_id(user_id: str, path: Optional[Path] = None) -> None:
    """`config/slack_mention.yml` 의 `slack_user_id` 자동 학습 저장.

    Socket Mode 연결 직후 `auth.test` 로 자기 user_id 를 받아 박아 둠.
    참가자가 본인 user_id 를 *수동으로 알 필요 없음*.
    """
    if path is None:
        path = Path(__file__).resolve().parent.parent / "config" / "slack_mention.yml"
    cfg = load_slack_config(path)
    if cfg.get("slack_user_id") == user_id:
        return  # 이미 같음 — 쓰기 생략
    cfg["slack_user_id"] = user_id
    try:
        import yaml
    except ImportError:
        logger.warning("pyyaml 미설치 — slack_user_id 저장 생략")
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        logger.info("slack_user_id_learned user=%s", user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("slack_user_id save fail: %s", exc)


# ─────────────────────────────────────────────────────────────
# 채널·키워드 필터
# ─────────────────────────────────────────────────────────────

def _channel_matches(channel_id: str, channel_name: Optional[str], allowlist: list) -> bool:
    """채널 allowlist 매칭. 빈 list = 전체 허용.

    allowlist 항목은 채널 ID(C...) 또는 채널 이름(#general 또는 general) 둘 다 OK.
    """
    if not allowlist:
        return True
    norm_allow = []
    for item in allowlist:
        s = str(item).strip().lstrip("#")
        if s:
            norm_allow.append(s)
    if channel_id in norm_allow:
        return True
    if channel_name and channel_name in norm_allow:
        return True
    return False


def _keyword_matches(text: str, keywords: list) -> bool:
    """키워드 필터. 빈 list = 전체 허용. 대소문자 무시 부분 매칭."""
    if not keywords:
        return True
    if not text:
        return False
    low = text.lower()
    for kw in keywords:
        s = str(kw).strip().lower()
        if s and s in low:
            return True
    return False


def _mention_stripped(text: str, self_user_id: str) -> str:
    """`<@UXXXX>` 멘션 토큰을 제거한 *본문* 반환. 앞뒤 공백 정리."""
    if not text:
        return ""
    if self_user_id:
        text = re.sub(rf"<@{re.escape(self_user_id)}>", "", text)
    # 다른 멘션은 그대로 두되, 가독성 위해 공백 정리
    return re.sub(r"\s+", " ", text).strip()


# ─────────────────────────────────────────────────────────────
# 페르소나 답변 초안 생성 — Claude Code CLI
# ─────────────────────────────────────────────────────────────

DRAFT_ADDENDUM = (
    "\n\n---\n\n"
    "## 슬랙 멘션 답변 초안 지침 (W4)\n\n"
    "사용자가 아래 형식의 *슬랙 메시지 컨텍스트* 를 보낼 거예요.\n"
    "당신은 페르소나 톤을 유지하면서, 그 메시지에 *어떻게 답하면 좋을지 초안*을 작성해요.\n\n"
    "- 답변은 **짧고 명확하게** — 슬랙에 그대로 붙여 넣을 수 있을 정도.\n"
    "- 단정하지 말고, 모르는 사실은 \"확인 필요\" 로 명시.\n"
    "- 사실 관계가 *모호한 부분*은 답하지 말고 \"여기는 본인 확인이 필요해요\" 한 줄로.\n"
    "- 마크다운 코드 블록은 코드일 때만. 일반 대화면 평문.\n"
    "- 페르소나의 인사·자기 호칭은 평소대로.\n"
    "- *답변 초안*만 작성하세요. 메타 코멘트(예: \"이렇게 답하시면 좋겠어요\") 없이 바로 답변 본문.\n"
)


def build_draft_system_prompt(persona_prompt: str) -> str:
    """페르소나 + 답변 초안 지침 합성. briefing.py 정합."""
    return (persona_prompt.strip() + DRAFT_ADDENDUM).strip()


def format_slack_context_plain(
    main_text: str,
    sender_name: str,
    channel_name: str,
    history: list,
) -> str:
    """슬랙 컨텍스트 → plain text (페르소나 paste 입력 용).

    history: 직전 메시지 list [{user_name, text}], 시간순 오름차순.
    """
    lines: list[str] = [f"== 슬랙 멘션 컨텍스트 (#{channel_name or 'unknown'}) =="]
    if history:
        lines.append("--- 직전 대화 흐름 ---")
        for h in history:
            uname = h.get("user_name") or "(누군가)"
            t = (h.get("text") or "").strip()
            if t:
                lines.append(f"{uname}: {t}")
    lines.append("--- 본인에게 온 멘션 ---")
    lines.append(f"{sender_name or '(누군가)'}: {main_text}")
    lines.append("--- 위 흐름에 대한 답변 초안을 페르소나 톤으로 작성해 주세요. ---")
    return "\n".join(lines)


def generate_draft(persona_prompt: str, context_plain: str) -> str:
    """페르소나 답변 초안 생성. bot.py::call_claude_code 정합 패턴.

    실패 시 plain fallback — *원문 그대로* 텔레그램에 흘려 보내서 사용자가 손으로 처리.
    """
    if shutil.which("claude") is None:
        logger.warning("claude CLI not found — fallback to plain context")
        return f"(Claude CLI 없음 — 원문만 전달)\n\n{context_plain}"

    system_prompt = build_draft_system_prompt(persona_prompt)
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
            input=context_plain,
            capture_output=True,
            text=True,
            timeout=CLAUDE_CLI_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return f"(Claude 응답이 {CLAUDE_CLI_TIMEOUT}초를 넘었어요 — 원문만 전달)\n\n{context_plain}"
    except FileNotFoundError:
        return f"(Claude CLI 없음 — 원문만 전달)\n\n{context_plain}"

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()[:200]
        logger.warning("claude exit=%s stderr=%s", result.returncode, stderr)
        return f"(Claude 오류 exit={result.returncode} — 원문만 전달)\n\n{context_plain}"
    output = (result.stdout or "").strip()
    if not output:
        return f"(빈 응답 — 원문만 전달)\n\n{context_plain}"
    if len(output) > MAX_REPLY_CHARS:
        output = output[:MAX_REPLY_CHARS] + "\n\n…(텔레그램 길이 한도로 잘림)"
    return output


# ─────────────────────────────────────────────────────────────
# Slack Bolt App — Socket Mode 핸들러
# ─────────────────────────────────────────────────────────────

def _resolve_channel_name(client, channel_id: str) -> str:
    """채널 ID → 채널 이름. 실패 시 빈 문자열. DM 은 'dm'."""
    if not channel_id:
        return ""
    try:
        resp = client.conversations_info(channel=channel_id)
        ch = resp.get("channel") or {}
        if ch.get("is_im"):
            return "dm"
        return ch.get("name") or ""
    except Exception as exc:  # noqa: BLE001
        logger.debug("conversations_info fail %s: %s", channel_id, exc)
        return ""


def _resolve_user_name(client, user_id: str) -> str:
    """user_id → display_name. 실패 시 빈 문자열."""
    if not user_id:
        return ""
    try:
        resp = client.users_info(user=user_id)
        u = resp.get("user") or {}
        prof = u.get("profile") or {}
        return prof.get("display_name") or prof.get("real_name") or u.get("name") or ""
    except Exception as exc:  # noqa: BLE001
        logger.debug("users_info fail %s: %s", user_id, exc)
        return ""


def _fetch_history(client, channel_id: str, before_ts: str, limit: int) -> list:
    """멘션 *직전* N 개 메시지. 시간순(오래된 → 최근) 오름차순.

    Slack `conversations.history` 는 newest-first 반환 — 뒤집어서 반환.
    실패 시 [].
    """
    if not channel_id or not before_ts or limit <= 0:
        return []
    try:
        resp = client.conversations_history(
            channel=channel_id,
            latest=before_ts,
            inclusive=False,
            limit=min(limit, SLACK_CONTEXT_FETCH_LIMIT),
        )
        msgs = resp.get("messages") or []
    except Exception as exc:  # noqa: BLE001
        logger.debug("conversations_history fail %s: %s", channel_id, exc)
        return []

    # newest-first → 뒤집고 user_name 채움
    user_name_cache: dict = {}
    out = []
    for m in reversed(msgs):
        # bot/subtype 메시지도 일단 포함 — 컨텍스트로 도움될 수 있음
        uid = m.get("user") or m.get("bot_id") or ""
        if uid and uid not in user_name_cache:
            user_name_cache[uid] = _resolve_user_name(client, uid) if not uid.startswith("B") else "(bot)"
        out.append({
            "user_name": user_name_cache.get(uid) or "(누군가)",
            "text": m.get("text") or "",
        })
    return out


def build_slack_app(persona_prompt: str, telegram_push_fn):
    """slack_bolt.App 생성 + 핸들러 등록.

    Args:
        persona_prompt: 페르소나 시스템 프롬프트 (bot.py 가 로드한 그것).
        telegram_push_fn: async callable(text: str) -> None — 텔레그램으로 push.
            bot.py 가 PTB Application 의 bot 인스턴스를 클로저로 묶어 전달.

    Returns:
        (app, handler) — slack_bolt.async_app.AsyncApp + AsyncSocketModeHandler
    """
    try:
        from slack_bolt.async_app import AsyncApp
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    except ImportError as exc:
        raise RuntimeError(
            "slack-bolt 미설치 — `uv sync` 또는 `pip install slack-bolt` 후 재시작해 주세요. "
            f"(원인: {exc})"
        )

    bot_token = os.getenv("SLACK_BOT_TOKEN", "").strip()
    app_token = os.getenv("SLACK_APP_TOKEN", "").strip()
    if not bot_token or not app_token:
        raise RuntimeError(
            "SLACK_BOT_TOKEN / SLACK_APP_TOKEN 가 .env 에 없어요. "
            "`/setup-slack-mention` 스킬을 먼저 호출해 주세요."
        )

    app = AsyncApp(token=bot_token, signing_secret=None)

    @app.event("app_mention")
    async def on_app_mention(event, client, logger=logger):  # noqa: ARG001
        """본인 봇이 직접 멘션 받은 이벤트.

        주의: bot user 가 멘션된 것. 본 W4 는 *사용자 본인 user_id* 가 멘션된 메시지를 잡는 게 목적이라
        app_mention 은 부수 케이스. message 이벤트에서 본인 user_id 멘션을 잡는 게 메인.
        그래도 봇이 직접 멘션됐을 때 로그 + 텔레그램 안내.
        """
        try:
            cfg = load_slack_config()
            if not cfg.get("enabled"):
                return
            channel_id = event.get("channel") or ""
            user_id = event.get("user") or ""
            text = event.get("text") or ""
            ch_name = _resolve_channel_name(client, channel_id)
            sender_name = _resolve_user_name(client, user_id)
            cleaned = _mention_stripped(text, "")  # bot 자기 멘션은 그대로 둠
            await _process_and_push(
                client=client,
                cfg=cfg,
                channel_id=channel_id,
                channel_name=ch_name,
                sender_name=sender_name,
                event_ts=event.get("ts") or "",
                main_text=cleaned,
                persona_prompt=persona_prompt,
                telegram_push_fn=telegram_push_fn,
                trigger_label="bot 멘션",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("on_app_mention failed: %s", exc)

    @app.event("message")
    async def on_message(event, client, logger=logger):  # noqa: ARG001
        """일반 메시지 — *본인(사용자) user_id 멘션* 매칭이 메인 목적.

        Slack 의 `message` 이벤트는 *모든* 채널 메시지를 받음 (scope 범위 안). 본 봇이 직접 답신하는 게
        아니라 *본인 텔레그램으로 초안 push* 만 하므로 답신 무한 루프 위험 0.
        """
        try:
            # subtype 필터: bot_message·message_changed·channel_join 등 잡음 제외
            subtype = event.get("subtype")
            if subtype:
                return
            if event.get("bot_id"):
                return  # 다른 봇 메시지는 무시

            cfg = load_slack_config()
            if not cfg.get("enabled"):
                return

            self_user_id = (cfg.get("slack_user_id") or "").strip()
            if not self_user_id:
                # 아직 user_id 미학습 — 본 핸들러는 skip. _on_open 에서 학습 시도.
                return

            text = event.get("text") or ""
            mention_token = f"<@{self_user_id}>"
            if mention_token not in text:
                return  # 본인 멘션 아니면 무시

            channel_id = event.get("channel") or ""
            sender_id = event.get("user") or ""
            if sender_id == self_user_id:
                # 본인이 본인을 멘션 — 테스트 케이스라 허용. 다만 로그.
                logger.info("self_mention_test channel=%s", channel_id)

            ch_name = _resolve_channel_name(client, channel_id)

            # 채널 필터
            if not _channel_matches(channel_id, ch_name, cfg.get("channel_allowlist") or []):
                logger.info("channel_filter_skip channel=%s/%s", channel_id, ch_name)
                return

            cleaned = _mention_stripped(text, self_user_id)

            # 키워드 필터
            if not _keyword_matches(cleaned, cfg.get("keyword_filter") or []):
                logger.info("keyword_filter_skip channel=%s/%s", channel_id, ch_name)
                return

            sender_name = _resolve_user_name(client, sender_id)
            await _process_and_push(
                client=client,
                cfg=cfg,
                channel_id=channel_id,
                channel_name=ch_name,
                sender_name=sender_name,
                event_ts=event.get("ts") or "",
                main_text=cleaned,
                persona_prompt=persona_prompt,
                telegram_push_fn=telegram_push_fn,
                trigger_label="본인 멘션",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("on_message failed: %s", exc)

    handler = AsyncSocketModeHandler(app, app_token)
    return app, handler


async def _process_and_push(
    *,
    client,
    cfg: dict,
    channel_id: str,
    channel_name: str,
    sender_name: str,
    event_ts: str,
    main_text: str,
    persona_prompt: str,
    telegram_push_fn,
    trigger_label: str,
) -> None:
    """멘션 → 컨텍스트 fetch → Claude 호출 → 텔레그램 push 공통 흐름.

    Claude 호출은 blocking subprocess — `asyncio.to_thread` 로 감싸서 이벤트 루프 안 막음.
    """
    logger.info(
        "slack_mention_hit trigger=%s channel=%s/%s sender=%s ts=%s",
        trigger_label, channel_id, channel_name, sender_name, event_ts,
    )

    # 즉시 ack — yml 에서 읽음
    ack = (cfg.get("ack_message") or "").strip()
    if ack:
        try:
            header = (
                f"🐾 슬랙 멘션 도착 (#{channel_name or 'unknown'} · {sender_name or '(누군가)'})\n"
                f"{ack}"
            )
            await telegram_push_fn(header)
        except Exception as exc:  # noqa: BLE001
            logger.warning("telegram_ack_push_fail: %s", exc)

    # 컨텍스트 fetch
    n = int(cfg.get("context_messages") or 3)
    history = []
    if n > 0:
        history = await asyncio.to_thread(_fetch_history, client, channel_id, event_ts, n)

    context_plain = format_slack_context_plain(
        main_text=main_text,
        sender_name=sender_name,
        channel_name=channel_name,
        history=history,
    )

    # Claude 호출 (blocking — to_thread)
    try:
        draft = await asyncio.to_thread(generate_draft, persona_prompt, context_plain)
    except Exception as exc:  # noqa: BLE001
        logger.exception("draft_generate_fail")
        draft = (
            f"(답변 초안 생성 중 막힘 — 원문만 전달)\n"
            f"에러: {type(exc).__name__}: {str(exc)[:200]}\n\n"
            f"{context_plain}"
        )

    body = (
        f"🐾 슬랙 답변 초안 (#{channel_name or 'unknown'} · {sender_name or '(누군가)'})\n\n"
        f"{draft}\n\n"
        f"---\n"
        f"_검토·수정 후 본인이 직접 슬랙에 붙여 넣으세요. 봇이 슬랙에 답하지 않아요._"
    )
    if len(body) > MAX_REPLY_CHARS:
        body = body[: MAX_REPLY_CHARS - 50] + "\n\n…(길이 한도로 잘림)"

    try:
        await telegram_push_fn(body)
    except Exception as exc:  # noqa: BLE001
        logger.exception("telegram_push_fail: %s", exc)


# ─────────────────────────────────────────────────────────────
# Startup — slack_user_id 자동 학습
# ─────────────────────────────────────────────────────────────

async def learn_self_user_id(app) -> Optional[str]:
    """Socket Mode 연결 직후 `auth.test` 호출로 자기 bot user_id 받음.

    주의: bot user_id 는 *봇 자체* — 사용자 본인의 user_id 와 다름.
    본 함수는 *bot 자체 user_id* 만 자동 학습. 사용자 본인 user_id 는
    `/setup-slack-mention` 스킬에서 본인이 한 번 paste 하는 흐름.

    Returns: bot 의 user_id (UXXX) 또는 None.
    """
    try:
        resp = await app.client.auth_test()
        bot_uid = resp.get("user_id") or ""
        logger.info("slack_bot_auth_test ok user=%s team=%s", bot_uid, resp.get("team"))
        return bot_uid
    except Exception as exc:  # noqa: BLE001
        logger.warning("slack_auth_test_fail: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────
# bot.py 통합 진입점
# ─────────────────────────────────────────────────────────────

async def start_slack_socket_mode(persona_prompt: str, telegram_push_fn) -> None:
    """bot.py 가 asyncio 컨텍스트에서 호출하는 진입점.

    SLACK_APP_TOKEN/SLACK_BOT_TOKEN 미설정이면 silent skip (W2/W3 만 쓰는 사람 영향 0).
    """
    if not (os.getenv("SLACK_APP_TOKEN") and os.getenv("SLACK_BOT_TOKEN")):
        logger.info("slack_socket_mode_skipped — SLACK_*_TOKEN 미설정 (W2/W3 만 운영 중)")
        return

    cfg = load_slack_config()
    if not cfg.get("enabled"):
        logger.info("slack_socket_mode_skipped — yml enabled=False")
        return

    try:
        app, handler = build_slack_app(persona_prompt, telegram_push_fn)
    except RuntimeError as exc:
        logger.error("slack_app_build_failed: %s", exc)
        return

    await learn_self_user_id(app)

    logger.info("slack_socket_mode_starting…")
    try:
        await handler.start_async()
    except asyncio.CancelledError:
        logger.info("slack_socket_mode_cancelled (bot 종료)")
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("slack_socket_mode_crashed: %s", exc)
