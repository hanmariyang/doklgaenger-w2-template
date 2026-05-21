#!/usr/bin/env bash
# 도클갱어 W2 — 봇 정지
# 갱이가 .bot.pid 의 프로세스를 종료할게요 🐾

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$REPO_ROOT/.bot.pid"

if [[ ! -f "$PID_FILE" ]]; then
    echo "갱이: PID 파일이 없어요. 봇이 안 떠 있는 것 같아요 🐾"
    exit 0
fi

BOT_PID="$(cat "$PID_FILE")"

if ps -p "$BOT_PID" > /dev/null 2>&1; then
    echo "갱이: PID=$BOT_PID 종료할게요 🐾"
    kill "$BOT_PID"
    sleep 1
    if ps -p "$BOT_PID" > /dev/null 2>&1; then
        echo "갱이: 한 번에 안 죽어서 SIGKILL 으로 마저 정리해요"
        kill -9 "$BOT_PID" || true
    fi
    echo "갱이: 봇 멈췄어요"
else
    echo "갱이: PID=$BOT_PID 가 이미 죽어 있었어요"
fi

rm -f "$PID_FILE"
