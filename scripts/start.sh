#!/usr/bin/env bash
# 도클갱어 W2 — 봇 백그라운드 시작
# 갱이가 nohup 으로 봇을 띄우고 PID 를 .bot.pid 에 저장해 둘게요 🐾

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOG_FILE="/tmp/doppel-bot.log"
PID_FILE="$REPO_ROOT/.bot.pid"

# 이미 떠 있는지 확인
if [[ -f "$PID_FILE" ]]; then
    OLD_PID="$(cat "$PID_FILE")"
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "갱이: 이미 봇이 떠 있어요 (PID=$OLD_PID). 먼저 ./scripts/stop.sh 해 주세요 🐾"
        exit 1
    else
        echo "갱이: 이전 PID 파일이 남아 있어서 정리해요 🐾"
        rm -f "$PID_FILE"
    fi
fi

# python 실행기 선택 — .venv 가 있으면 우선
if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    PYTHON="$REPO_ROOT/.venv/bin/python"
else
    PYTHON="$(command -v python3 || command -v python)"
fi

if [[ -z "${PYTHON:-}" ]]; then
    echo "갱이: python 실행기를 찾지 못했어요 🐾"
    exit 2
fi

echo "갱이: 봇을 백그라운드로 띄울게요 🐾"
echo "  python:  $PYTHON"
echo "  log:     $LOG_FILE"
echo "  pidfile: $PID_FILE"

nohup "$PYTHON" "$REPO_ROOT/bot.py" > "$LOG_FILE" 2>&1 &
BOT_PID=$!
echo "$BOT_PID" > "$PID_FILE"

sleep 1
if ps -p "$BOT_PID" > /dev/null 2>&1; then
    echo "갱이: 떴어요! (PID=$BOT_PID) 텔레그램에서 /start 보내 보세요."
    echo "      로그: tail -f $LOG_FILE"
else
    echo "갱이: 시작에 실패했어요... 로그 확인해 주세요 🐾"
    tail -n 20 "$LOG_FILE" || true
    rm -f "$PID_FILE"
    exit 3
fi
