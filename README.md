# 도클갱어 W2/W3 — 본인 톤 첫 챗봇 + 캘린더 아침 브리핑 템플릿

> 안녕하세요, 갱이예요 🐾
> 갱이가 8주 도클갱어 스터디의 **W2(본인 톤 첫 챗봇) + W3(캘린더 아침 브리핑)**을 함께 만들어 드릴게요.

W2는 *임의의 영화/캐릭터 페르소나*를 골라서 텔레그램 봇으로 5문답까지 굴려 보는 한 주예요. W3는 그 봇에 *기능 1개*만 더해요 — 매일 아침 페르소나가 오늘 일정을 그려서 보내 주는 캘린더 브리핑. 본인 도플갱어 전환은 W7~W8에 할 거니까, W2~W3는 가볍게 즐기는 구간이에요.

repo 이름은 `doklgaenger-w2-template` 그대로 유지하지만 W3·W4 가 누적되며 진화하는 *템플릿*입니다.

---

## 갱이가 누구냐면

갱이는 *진짜 도클갱어가 태어나기 전까지의 임시 자리*예요. W8 데모데이 때는 옆 자리로 비켜 드릴 거고, 그때까지는 8단계 동안 옆에서 계속 따라다닐 거예요. 자기를 부를 땐 "갱이가", "갱이는"이라고 해요.

---

## W2 8단계 핵심 흐름

| # | 단계 | 갱이가 도와드리는 거 |
|---|------|-------------------|
| 0 | 사전 점검 | Claude Code 로그인 (`which claude`), BotFather 안내, Python 3.11+ |
| 1 | clone | `git clone` 후 폴더 진입 |
| 2 | 인사 + 흐름 설명 | `/welcome` — 갱이가 8단계 미리 보여 드려요 |
| 3 | 페르소나 선택 | `/pick-persona` — 취향 인터뷰 5문 → 후보 3개 추천 |
| 4 | 시스템 프롬프트 작성 | `/research-persona` — 정해진 페르소나 리서치 + 초안 |
| 4.5 | 시연 5문답 검증 | `/simulate` — 텔레그램 없이 미리 굴려 보기 → OK 시 lock |
| 5 | 인프라 셋업 | `/setup-telegram` — 토큰 받아 .env 저장 + getMe 검증 |
| 6 | 봇 on/off | `/bot start` / `/bot stop` / `/bot status` |
| 7 | 텔레그램 첫 5문답 본인 검증 | (직접 텔레그램 앱에서) |
| 7.5 | 자가 진단 | `/diagnose` — 막히면 6가지 자동 체크 |
| 8 | 페어 검증 | 페어가 봇에 직접 메시지 |
| 8.5 | 페르소나 조정 | `/tune-persona` — 응답 paste → 1~2줄 수정 제안 |
| 9 | 결승선 | 스크린샷 + 시스템 프롬프트 1줄 + on/off 메모 제출 |

## W3 8단계 — 캘린더 아침 브리핑 (TF-958)

| # | 단계 | 갱이가 도와드리는 거 |
|---|------|-------------------|
| 0 | W3 진입 점검 | `/welcome-w3` — W2 봇 살아있는지 + 의존성 갱신 안내 |
| 1 | iCal URL 받기 | `/setup-ical` — Google 비공개 iCal URL 1줄 + *주의 메시지* |
| 2 | .env 채우기 + 재시작 | `ICAL_URL=...` 박고 봇 재기동 |
| 3 | `/today` + 자연어 첫 시도 | "오늘 일정", "브리핑" 같은 메시지로 페르소나 톤 브리핑 받기 |
| 4 | 양식 결정 | `/setup-briefing-style` — 갱이와 대화로 format/length/show_empty |
| 5 | 시연 브리핑 → lock | 마음에 들면 다음, 아니면 다시 |
| 6 | 자동 푸시 시간 (선택) | `/setup-briefing-schedule` — 시간 + chat_id |
| 7 | 페어 시연 | *캡처만 공유*, iCal URL 절대 X |
| 8 | 결승선 | 브리핑 캡처 + W4 예고 |

---

## 시작하기 (3분)

```bash
git clone https://github.com/hanmariyang/doklgaenger-w2-template.git
cd doklgaenger-w2-template

# 갱이한테 인사받기 (Claude Code 안에서)
/welcome
```

`/welcome`이 환경을 점검하고 다음 단계를 안내해 드려요.

---

## 환경

- Python 3.11+
- **Claude Code CLI** (로그인 상태) — *별도 API 키 불필요*. `bot.py` 가 본인 Claude Code 구독 사용량으로 동작 (TF-938 hotfix).
- Telegram Bot 토큰 (BotFather → `docs/botfather-guide.md`)
- **W3 추가**: Google Calendar 비공개 iCal URL (선택, W3 부터). 발급은 `/setup-ical` 안내.

## W3 패치 누적 설치 (clone 직후 1회)

```bash
~/.local/bin/uv sync           # W3 의존성 (icalendar, python-dateutil, pyyaml, requests, PTB[job-queue])
./scripts/install-w3-skills.sh # W3 Skills 4개를 .claude/skills/ 에 복사
```

설치 후 Claude Code 안에서 `/welcome-w3` 호출하면 갱이가 안내해 드려요.

---

## 안 막히게 도와주는 파일들

- `docs/botfather-guide.md` — BotFather 3분 발급
- `docs/troubleshoot.md` — 자주 막히는 부분
- `.claude/skills/diagnose.md` — 진단 6가지 자동 체크
- `CLAUDE.md` — 갱이 정체성·8단계 정의·금기·on/off

---

## 라이선스

MIT. 이 템플릿을 떠나서 본인의 W2를 만들어 보세요. 갱이가 응원할게요 🐾
