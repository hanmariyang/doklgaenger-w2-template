"""도클갱어 W2 — 텔레그램 페르소나 챗봇 (Claude Code CLI 서브프로세스 방식).

PD-938 hotfix (2026-05-21):
- 이전 버전은 Anthropic API 직호출 (의뢰자 카드 과금).
- 의뢰자 의도 정합: Claude Code CLI 를 서브프로세스로 호출 → 참가자 본인 Claude Code
  구독 사용량 안에서 동작 → 추가 과금 0.
- 패턴은 Triforge `agents/services/persona_engine.py::_call_claude_code` 정합.

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
import shutil
import subprocess
import sys
from pathlib import Path

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

CLAUDE_MODEL = "sonnet"  # Claude Code CLI 의 --model 값 (sonnet/opus/haiku 또는 풀 모델명)
CLAUDE_CLI_TIMEOUT = 90  # 초 — Triforge persona_engine 정합 (긴 응답 안전 마진)
PERSONA_PATH = Path(__file__).parent / "persona" / "system_prompt.md"
MAX_REPLY_CHARS = 4000  # 텔레그램 단일 메시지 한도(4096) 미만으로 자름

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
        "이 봇은 도클갱어 W2 페르소나 챗봇이에요.\n"
        "메시지를 보내 주시면 페르소나로 답변해 드려요."
    )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """일반 메시지 → Claude Code CLI 응답."""
    user_text = update.message.text
    chat_id = update.message.chat_id
    logger.info("incoming chat_id=%s len=%s", chat_id, len(user_text or ""))

    if not user_text:
        await update.message.reply_text("(텍스트 메시지만 처리할 수 있어요)")
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

    await update.message.reply_text(reply)


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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("bot_starting model=%s timeout=%ss", CLAUDE_MODEL, CLAUDE_CLI_TIMEOUT)
    app.run_polling(allowed_updates=Update.ALL_TYPES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
