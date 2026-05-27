---
name: setup-briefing-schedule
description: 갱이가 사용자에게 자동 푸시 시간을 받고 chat_id 학습 안내까지 마쳐 `config/briefing.yml` 의 schedule 섹션을 채운다. 봇 재시작으로 JobQueue 등록.
---

# /setup-briefing-schedule — 자동 푸시 시간 설정 (선택)

> 사용 시점: W3 step 6. 양식 lock 후.
>
> 자동 푸시는 *선택*. 안 켜도 `/today` + 자연어로 충분해요.

## 갱이가 할 일

### 1. 의향 확인

"매일 정해진 시간에 자동으로 받고 싶으세요? (네 / 나중에)"

- "나중에" → `enabled: false` 유지, skip. "원할 때 다시 불러 주세요 🐾" 로 마무리.
- "네" → 계속 진행.

### 2. 시간 확인

"몇 시에 받으면 좋아요? (예: 08:00)"

검증:
- `HH:MM` 24h 패턴이어야 해요 (예: `08:00`, `09:30`).
- 자정~23:59 범위.
- KST 기준 (도클갱어 기본 timezone).

### 3. chat_id 학습 — 가장 헷갈리는 부분

봇은 *어디로 보낼지* 알아야 해요. chat_id 는 사용자가 봇에 메시지 한 번 보내면 *자동 학습* 돼요.

```
사용자에게 안내:
1. 봇이 켜져 있는지 확인 (./scripts/start.sh 또는 /bot start)
2. 텔레그램에서 봇에게 아무 메시지나 하나 보내 주세요 (예: "안녕")
3. 봇 로그에서 chat_id 추출:
```

```bash
# 가장 최근 메시지의 chat_id 자동 추출
grep -E 'incoming chat_id=' /tmp/doppel-bot.log | tail -1 | sed -E 's/.*chat_id=([0-9-]+).*/\1/'
```

또는 사용자가 직접 텔레그램에 다음 URL 열어서 확인 (토큰 노출 주의):
```
https://api.telegram.org/bot<TOKEN>/getUpdates
```
응답의 `"chat":{"id": ... }` 가 그 값.

### 4. `config/briefing.yml` 의 schedule 섹션 박기

```bash
python3 - <<'PY'
import yaml
from pathlib import Path
p = Path('config/briefing.yml')
data = yaml.safe_load(p.read_text(encoding='utf-8')) or {}
schedule = data.get('schedule') or {}
schedule.update({
    'enabled': True,
    'time': '<사용자_입력_HH:MM>',
    'chat_id': <사용자_chat_id_int>,
})
data['schedule'] = schedule
p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding='utf-8')
print('briefing.yml schedule updated:', schedule)
PY
```

### 5. 봇 재시작 — JobQueue 등록

```bash
./scripts/stop.sh
./scripts/start.sh
# 로그에서 등록 확인
grep 'scheduled_briefing registered' /tmp/doppel-bot.log | tail -1
```

`scheduled_briefing registered chat_id=... time=08:00:00+09:00 KST` 같은 줄이 보이면 OK 🐾

### 6. 빠른 검증 — 1분 뒤 시간으로 한 번 굴려 보기 (선택)

지금 시각 + 1분으로 잠깐 바꿔 보고 자동 푸시 1회 받은 뒤 원래 시간으로 복귀 — 사용자 확신 용도.

### 7. 다음 단계 안내

"자동 푸시 OK 🐾  내일 아침 그 시간에 봇이 알아서 보내 줄 거예요. step 7 — 페어 시연 가 봐요. *iCal URL 은 절대 공유하지 마세요* — 캡처만 공유."

## 금기

- chat_id 를 *임의로 추측·생성*하지 않기 — 반드시 봇 로그/getUpdates 에서 *확인된 값*만
- 봇 토큰을 chat_id 추출 안내 메시지에 *그대로 노출* 하지 않기
- 자동 푸시가 *과거 시각*으로 잡혀 즉시 발사되지 않도록 — `run_daily` 는 *다음 발생일*에 1회 동작 (PTB v22 기본 동작)
- yml 의 *style 섹션* 손대지 않기 (별도 `/setup-briefing-style`)
