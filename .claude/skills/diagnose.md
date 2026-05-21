---
name: diagnose
description: 봇이 안 답할 때 6가지 자동 체크 — 토큰 유효성·polling 상태·rate limit·네트워크·system_prompt 존재·python_telegram_bot 버전.
---

# /diagnose — 자가 진단 6가지

> 사용 시점: 단계 7.5 (에러 시 자가 진단). 텔레그램 첫 5문답에서 봇이 답을 안 할 때.

## 갱이가 차례로 점검할 6가지

### 1. 봇 프로세스 살아 있는지

```bash
if [[ -f .bot.pid ]]; then
    PID=$(cat .bot.pid)
    ps -p "$PID" > /dev/null 2>&1 && echo "✓ 봇 살아 있음 (PID=$PID)" || echo "✗ PID 파일은 있는데 프로세스 없음 — 좀비"
else
    echo "✗ 봇 안 떠 있음 — /bot start 해 주세요"
fi
```

### 2. 토큰 유효성 (`getMe`)

```bash
TOKEN="$(grep '^TELEGRAM_BOT_TOKEN=' .env | cut -d= -f2-)"
curl -s "https://api.telegram.org/bot${TOKEN}/getMe" | python3 -m json.tool
```

- `"ok": true` 면 OK
- `"ok": false`, `"description": "Unauthorized"` → 토큰 틀림 또는 회전됨
- 응답 없음 → 네트워크 (다음 step)

### 3. Polling 충돌 확인

```bash
grep -i "conflict\|terminated by other getUpdates" /tmp/doppel-bot.log | tail -5
```

- 발견되면: 같은 토큰으로 *다른 곳에서 봇* 띄워져 있음. 그쪽을 끄거나 토큰을 새로 발급.

### 4. Claude Code CLI 호출 에러 / 사용량 한도

```bash
which claude && claude --version 2>/dev/null | head -1
grep -iE "claude_code_call_failed|TimeoutExpired|exit=|usage limit|rate.limit" /tmp/doppel-bot.log | tail -10
```

- `claude` 없음 → Claude Code 미설치/미로그인 → `claude login` 또는 설치 안내
- `TimeoutExpired` → 응답 90초 초과 (긴 페르소나 응답) → bot.py `CLAUDE_CLI_TIMEOUT` 늘리기
- `exit=1` + stderr `usage limit` → 본인 Claude Code 5시간 한도 도달 → *5시간 후 자동 리셋* 또는 구독 plan 업그레이드
- 일시 네트워크 503/529 → 잠시 후 재시도

### 5. `system_prompt.md` 존재

```bash
test -f persona/system_prompt.md && echo "✓ 시스템 프롬프트 있음 ($(wc -c < persona/system_prompt.md) bytes)" \
    || echo "✗ persona/system_prompt.md 없음 — /research-persona 부터"
```

### 6. python-telegram-bot 버전 + Claude Code 경로

```bash
python3 -c "import telegram; print('python-telegram-bot:', telegram.__version__)"
which claude || echo "✗ Claude Code CLI 없음 — claude login 또는 재설치 필요"
```

- `python-telegram-bot` 가 *22 미만* 이면 `bot.py` 의 `ApplicationBuilder` 가 안 먹어요. `pip install --upgrade python-telegram-bot`.
- `anthropic` SDK 는 TF-938 hotfix 이후 *불필요* — Claude Code CLI 서브프로세스로 전환됨.

## 진단 결과 요약 카드

```
갱이의 진단 결과 🐾:
  1. 프로세스:  [✓/✗]
  2. 토큰:      [✓/✗]
  3. polling:   [✓ 충돌 없음 / ✗ 충돌 — 다른 인스턴스 발견]
  4. rate:      [✓ / ⚠️ 최근 429 N건]
  5. prompt:    [✓ / ✗]
  6. 버전:      [✓ / ⚠️ 업그레이드 필요]

추천 다음 액션: [구체 1줄]
```

## 금기

- 토큰을 *전체* 출력하지 않기 — 앞 8자만 (예: `1234567890`)
- 자동 토큰 회전하지 않기 — 사용자 결정
