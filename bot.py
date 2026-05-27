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

신경계 비유:
- 텔레그램(감각기관)이 입력을 받아 들이고,
- Claude Code CLI(뇌)가 페르소나 시스템 프롬프트로 응답을 만들어
- 다시 텔레그램으로 흘려 보내요.

설계 원칙:
- 페르소나는 `persona/system_prompt.md` 한 파일에서만 흘러나온다 (Single Source).
- 1봇 = 1페르소나. chat_id 별 분리 없음 — W2 단순화.
- 로깅은 stdout/stderr 그대로, scripts/start.sh 가 /tmp/doppel-bot.log 로 redirect.
- *Claude API 키 불필요* — Claude Code 가 로그인 상태이기만 하면 OK.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import time as dt_time
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
        "이 봇은 도클갱어 W2/W3 페르소나 챗봇이에요.\n"
        "메시지를 보내 주시면 페르소나로 답변해 드려요.\n"
        "오늘 일정이 궁금하면 `/today` 또는 “오늘 일정” 이라고 보내 주세요."
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
    """
    system_prompt = context.bot_data["system_prompt"]
    config = load_briefing_config()  # 매 호출 reload — 사용자가 yml 손대도 즉시 반영
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


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """일반 메시지 → Claude Code CLI 응답.

    PD-938 hotfix2 (2026-05-21): parse_mode=Markdown 활성화.
    LLM 응답의 `**bold**` `*italic*` `` `code` ``가 raw 텍스트로 노출되던 문제 봉합.
    Markdown 파싱 실패 시(escape 문제 등) plain text 로 fallback.

    TF-958 W3 (2026-05-28): "오늘 일정/브리핑" 등 자연어 매칭 시 briefing 로 라우팅.
    매칭 안 되면 기존 페르소나 응답 그대로.
    """
    user_text = update.message.text
    chat_id = update.message.chat_id
    logger.info("incoming chat_id=%s len=%s", chat_id, len(user_text or ""))

    if not user_text:
        await update.message.reply_text("(텍스트 메시지만 처리할 수 있어요)")
        return

    # W3 — 자연어 브리핑 트리거가 우선
    if _is_briefing_trigger(user_text):
        logger.info("briefing_trigger_matched chat_id=%s", chat_id)
        await _send_briefing(update, context)
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

    app = ApplicationBuilder().token(telegram_token).build()
    app.bot_data["system_prompt"] = system_prompt

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("today", today_handler))  # W3, TF-958
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # W3 (TF-958) — 자동 푸시 등록. yml 없거나 enabled=False 면 silent skip.
    _register_scheduled_briefing(app)

    logger.info("bot_starting model=%s timeout=%ss", CLAUDE_MODEL, CLAUDE_CLI_TIMEOUT)
    app.run_polling(allowed_updates=Update.ALL_TYPES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
