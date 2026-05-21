"""도클갱어 W2 — 텔레그램 페르소나 챗봇.

이것은 마치 신경계예요. 텔레그램(감각기관)이 입력을 받아 들이고,
Claude API(뇌)가 페르소나 시스템 프롬프트로 응답을 만들어 다시 텔레그램으로 흘려 보내요.

설계 원칙:
- 페르소나는 `persona/system_prompt.md` 한 파일에서만 흘러나온다 (Single Source).
- 1봇 = 1페르소나. chat_id 별 분리 없음 — W2 단순화.
- 로깅은 stdout/stderr 그대로, scripts/start.sh 가 /tmp/doppel-bot.log 로 redirect.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ─────────────────────────────────────────────────────────────
# 설정 — 갱이가 미리 정해 둔 상수
# ─────────────────────────────────────────────────────────────

CLAUDE_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024
PERSONA_PATH = Path(__file__).parent / "persona" / "system_prompt.md"

# 토큰을 못 찾았을 때 갱이가 보내는 메시지
FRIENDLY_MISSING_TOKEN_MSG = (
    "갱이가 토큰을 못 찾았어요... 🐾\n"
    "→ `.env.example` 을 복사해서 `.env` 를 만들고,\n"
    "  `CLAUDE_API_KEY` 와 `TELEGRAM_BOT_TOKEN` 을 채워 주세요.\n"
    "  자세한 방법은 `docs/botfather-guide.md` 와 README 를 봐 주세요."
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
    이것은 마치 인간의 *성격* 같은 거예요 — 매번 새로 읽지 않고 봇 시작 시 한 번만.
    """
    if not PERSONA_PATH.exists():
        raise FileNotFoundError(PERSONA_PATH)
    return PERSONA_PATH.read_text(encoding="utf-8").strip()


# ─────────────────────────────────────────────────────────────
# Claude 호출 — 뇌
# ─────────────────────────────────────────────────────────────

def call_claude(client: Anthropic, system_prompt: str, user_text: str) -> str:
    """Claude API messages.create 호출. 단일 turn (대화 컨텍스트 미보관 — W2 단순화).

    멀티 turn 컨텍스트는 W3+ 에서 메시지 히스토리로 확장 예정.
    """
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_text}],
    )
    # response.content 는 list[ContentBlock]. text 블록만 추려 합친다.
    parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    return "\n".join(parts).strip() or "(빈 응답)"


# ─────────────────────────────────────────────────────────────
# 텔레그램 핸들러 — 감각기관
# ─────────────────────────────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/start` — 페르소나 첫 인사 안내."""
    await update.message.reply_text(
        "안녕하세요 🐾\n"
        "이 봇은 도클갱어 W2 페르소나 챗봇이에요.\n"
        "메시지를 보내 주시면 페르소나로 답변해 드려요."
    )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """일반 메시지 → Claude 응답."""
    user_text = update.message.text
    chat_id = update.message.chat_id
    logger.info("incoming chat_id=%s len=%s", chat_id, len(user_text or ""))

    if not user_text:
        await update.message.reply_text("(텍스트 메시지만 처리할 수 있어요)")
        return

    try:
        system_prompt = context.bot_data["system_prompt"]
        client: Anthropic = context.bot_data["claude_client"]
        reply = call_claude(client, system_prompt, user_text)
    except Exception as exc:  # noqa: BLE001 — 사용자에게 노출해야 하므로 광범위 캐치 의도
        logger.exception("claude_call_failed")
        reply = f"갱이가 응답 생성 중에 막혔어요... 🐾\n로그 확인: `tail -f /tmp/doppel-bot.log`\n에러: {type(exc).__name__}"

    await update.message.reply_text(reply)


# ─────────────────────────────────────────────────────────────
# 부팅
# ─────────────────────────────────────────────────────────────

def main() -> int:
    """봇 부팅. 로딩 실패 시 exit code 로 사용자에게 신호를 준다."""
    load_dotenv()

    claude_key = os.getenv("CLAUDE_API_KEY")
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not claude_key or not telegram_token:
        print(FRIENDLY_MISSING_TOKEN_MSG, file=sys.stderr)
        return 2

    try:
        system_prompt = load_system_prompt()
    except FileNotFoundError:
        print(FRIENDLY_MISSING_PROMPT_MSG, file=sys.stderr)
        return 3

    logger.info("persona_loaded chars=%s", len(system_prompt))

    claude_client = Anthropic(api_key=claude_key)
    app = ApplicationBuilder().token(telegram_token).build()

    # bot_data 에 공용 자원 박아 두기 — 핸들러가 공유
    app.bot_data["system_prompt"] = system_prompt
    app.bot_data["claude_client"] = claude_client

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("bot_starting model=%s", CLAUDE_MODEL)
    app.run_polling(allowed_updates=Update.ALL_TYPES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
