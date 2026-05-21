---
name: bot
description: 봇 백그라운드 on/off/status. `/bot start` 로 띄우고, `/bot stop` 으로 내리고, `/bot status` 로 PID·로그를 확인한다.
---

# /bot — 봇 on/off/status

> 사용 시점: 단계 6 (백그라운드 on/off) 이후 항상.

## 갱이가 할 일

### `/bot start`

```bash
./scripts/start.sh
```

- 이미 떠 있으면 안내 (`.bot.pid` 가 살아 있는지 확인).
- 시작 후 *5초 기다리고* `/tmp/doppel-bot.log` 의 마지막 줄을 보여 줘서 부팅이 정상인지 확인.

### `/bot stop`

```bash
./scripts/stop.sh
```

- `.bot.pid` 의 프로세스를 종료.
- 종료 후 `.bot.pid` 가 정리됐는지 확인.

### `/bot status`

```bash
if [[ -f .bot.pid ]]; then
    PID=$(cat .bot.pid)
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "갱이: 봇 떠 있어요 (PID=$PID) 🐾"
        tail -n 5 /tmp/doppel-bot.log
    else
        echo "갱이: PID 파일은 있는데 프로세스가 없어요 (좀비 PID). ./scripts/stop.sh 로 정리해 주세요."
    fi
else
    echo "갱이: 봇이 꺼져 있어요."
fi
```

## 운영 메모

- 로그 위치: `/tmp/doppel-bot.log`
- PID 파일: `.bot.pid` (repo 루트)
- 재시작이 필요하면: `/bot stop` → `/bot start` (양쪽 다 idempotent)

## 금기

- 같은 토큰으로 *동시에 두 인스턴스* 띄우지 않기 (텔레그램 polling 충돌 — `Conflict: terminated by other getUpdates request` 발생)
- 사용자 동의 없이 `stop` 후 `start` 자동 재시작 하지 않기
