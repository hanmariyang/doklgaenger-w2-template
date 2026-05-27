---
name: welcome-w3
description: 도클갱어 W3 첫 인사 — 갱이가 캘린더 아침 브리핑 흐름을 8단계로 안내하고 W2 봇이 살아있는지 점검한다. W3 진입 직후 한 번 호출.
---

# /welcome-w3 — 갱이가 돌아왔어요 🐾

> 사용 시점: W3 진입 직후 한 번. step 0 (W3 사전 점검).
>
> W3 의도: W2 인프라(텔레그램 봇 + Claude Code CLI + 페르소나) **그대로** + *기능 1개 추가* — 캘린더 아침 브리핑.

## 갱이가 할 일

### 1. 인사

"갱이가 돌아왔어요 🐾 W3 — 오늘 일정 받기 시작해 볼까요?"

W3 의도 한 줄: *적은 인풋, 높은 아웃풋*. iCal URL 1줄만 받으면 오늘 일정을 페르소나 톤으로 매일 받을 수 있어요.

### 2. W3 8단계 흐름 한 줄씩

0. 갱이 인사 (`/welcome-w3`) — *지금 이 단계*
1. iCal URL 받기 (`/setup-ical`) — 주의 메시지 포함
2. `.env` 채우기 + 봇 재시작
3. `/today` + 자연어 첫 시도 — 페르소나 톤으로 브리핑 받아 보기
4. `/setup-briefing-style` — 갱이와 대화로 양식 결정
5. 시연 브리핑 — 양식 lock
6. `/setup-briefing-schedule` — 자동 푸시 시간 설정 (선택)
7. 페어 시연 — 각자 본인 브리핑 캡처 공유, *iCal URL 교환 금지*
8. 결승선 — 브리핑 캡처 + W4 예고

### 3. 환경 점검 — W2 봇이 살아있는지

```bash
# W2 봇 PID 확인
cat .bot.pid 2>/dev/null && echo "(pid 파일 있음)" || echo "(pid 파일 없음)"

# 실제 프로세스 살아있는지
ps -p $(cat .bot.pid 2>/dev/null) 2>/dev/null && echo "running" || echo "stopped"
```

- 둘 다 OK → W3 진입 가능. 다음 단계 `/setup-ical`.
- stopped → W2 마무리 먼저: `./scripts/start.sh` 또는 `/bot start`.
- W2 자체를 안 끝낸 분 → "갱이가 W2 부터 도와 드릴게요" — `/welcome` 으로 돌아가기.

### 4. 의존성 한 번 점검 — W3 새 패키지

```bash
~/.local/bin/uv sync  # icalendar / python-dateutil / pyyaml / requests 추가됨
# 또는 venv: pip install -e .
```

`uv` 가 없으면 `pip install icalendar python-dateutil pyyaml requests` 도 OK.

### 5. 다음 단계 안내

"준비됐어요 🐾  `/setup-ical` 로 Google Calendar URL 받아 봐요."

## 절대 안 할 것

- 본인 의향 묻지 않고 iCal URL 을 *대신* 받아 채워 넣지 않기
- W2 봇을 임의로 종료·재시작하지 않기 (사용자 승인 후)
- "회사 캘린더는 안 됩니다" 같이 *차단성 안내* 하지 않기 — W3 는 학습용이라 회사 캘린더도 허용. 단 *주의 메시지*는 `/setup-ical` 에서 명확히.
