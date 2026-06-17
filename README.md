# 도클갱어 W2/W3/W4/W5 — 본인 톤 첫 챗봇 + 캘린더 아침 브리핑 + 슬랙 멘션 답변 + 회의록 요약

> 안녕하세요, 갱이예요 🐾
> 갱이가 8주 도클갱어 스터디의 **W2(본인 톤 첫 챗봇) + W3(캘린더 아침 브리핑) + W4(슬랙 멘션 답변 어시스턴트) + W5(회의록 요약 어시스턴트)**을 함께 만들어 드릴게요.

W2는 *임의의 영화/캐릭터 페르소나*를 골라서 텔레그램 봇으로 5문답까지 굴려 보는 한 주예요. W3는 그 봇에 *기능 1개*만 더해요 — 매일 아침 페르소나가 오늘 일정을 그려서 보내 주는 캘린더 브리핑. W4는 또 *기능 1개* — 본인이 슬랙에서 멘션받으면 페르소나가 답변 초안을 만들어서 본인 텔레그램으로 흘려 줘요 (슬랙에는 답신 안 함, 본인 손으로). W5는 *가장 단순한* 기능 1개 — 회의 메모를 텔레그램에 붙여 넣으면 페르소나가 구조화 회의록(요약·논의·결정·액션·질문)으로 정리해 줘요 (음성·STT 없이 텍스트 한 가지). 본인 도플갱어 전환은 W7~W8에 할 거니까, W2~W5는 가볍게 즐기는 구간이에요.

repo 이름은 `doklgaenger-w2-template` 그대로 유지하지만 W3·W4·W5 가 누적되며 진화하는 *템플릿*입니다.

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

## W4 7단계 — 슬랙 멘션 답변 어시스턴트 (TF-981, Socket Mode)

| # | 단계 | 갱이가 도와드리는 거 |
|---|------|-------------------|
| 0 | W4 진입 점검 | `/welcome-w4` — W2 봇 살아있는지 + 의존성 (`slack-bolt`) 갱신 |
| 1 | 슬랙 앱 만들기 | `/setup-slack-app` — manifest import + Bot Token + App-Level Token |
| 2 | `.env` 채우기 + 봇 재시작 | `/setup-slack-mention` — 토큰 2개 + 본인 user_id + ack 메시지 |
| 3 | 본인 셀프 멘션 시연 | 본인 텔레그램에 답변 초안 도착 확인 |
| 4 | 필터 조정 (선택) | `/setup-slack-filter` — 채널 allowlist + 키워드 + context 개수 |
| 5 | 페어 시연 | `/test-slack-mention` — 5+5분, 봇은 슬랙에 답하지 않음 |
| 6 | 결승선 | 멘션 답변 캡처 + 양식 1줄 메모 + W5 예고 |

W4 핵심: *Triforge 서버 의존 0, 운영자 서버 의존 0*. 슬랙 outbound WebSocket 하나 + 본인 노트북에서 100% 완결.

## W5 7단계 — 회의록 요약 어시스턴트 (TF-1040)

| # | 단계 | 갱이가 도와드리는 거 |
|---|------|-------------------|
| 0 | W5 진입 점검 | `/welcome-w5` — W2 봇 살아있는지 + 새 패키지 0 확인 + 봇 재시작 |
| 1 | config 만들기 | `cp config/meeting_notes.yml.example config/meeting_notes.yml` |
| 2 | 샘플 메모 첫 시연 | `/test-meeting-notes` — `docs/sample-meeting-notes-ko.txt` 붙여넣기 |
| 3 | 사실 보존 확인 | 회의록의 이름·날짜·결정이 원본 메모와 일치하는지 대조 |
| 4 | 양식 결정 | `/setup-meeting-style` — 섹션 on/off + 길이 + 액션아이템 형식 |
| 5 | 본인 메모로 시연 | 진짜 회의 메모로 한 번 → 양식 lock |
| 6 | 페어 시연 | 회의록 캡처만 공유 (회의 본문은 절대 공유 X) |
| 7 | 결승선 | 회의록 캡처 + 양식 1줄 메모 + W6 예고 |

W5 핵심: *적은 인풋(텍스트 붙여넣기 하나), 높은 아웃풋(구조화 회의록)*. 음성·STT·파일 0, 새 외부 의존성 0, 본인 노트북 100% 완결. **사실 보존** — 페르소나는 톤만 입히고 참석자·결정·숫자·날짜는 그대로.

- `/notes` 뒤에 메모를 붙이거나, "회의록"·"정리해줘" 같은 자연어, 또는 긴 메모(600자·여러 줄)를 그냥 보내면 자동 인식.
- 긴 회의록은 텔레그램 4096자 한도 때문에 *여러 메시지로 분할 발송* — (1/3),(2/3) 처럼 표시.

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
- **W4 추가**: 슬랙 워크스페이스 1개 + manifest 로 생성한 본인 슬랙 앱 (Bot Token + App-Level Token). 발급은 `/setup-slack-app` 안내. manifest 본문은 `docs/slack-app-manifest.yml`.
- **W5 추가**: *추가 준비물 없음*. 회의 메모(텍스트)만 있으면 돼요. 토큰·URL·새 패키지 0.

## W3/W4/W5 의존성 (clone 직후 1회)

```bash
~/.local/bin/uv sync           # icalendar, python-dateutil, pyyaml, requests, PTB[job-queue], slack-bolt
                               # W5 는 새 패키지 0 — "Nothing to install" 이면 정상
```

설치 후 Claude Code 안에서 `/welcome-w3` · `/welcome-w4` · `/welcome-w5` 호출하면 갱이가 안내해 드려요. W3·W4·W5 Skill 은 모두 `.claude/skills/` 에 박혀 있어요.

---

## 안 막히게 도와주는 파일들

- `docs/botfather-guide.md` — BotFather 3분 발급
- `docs/troubleshoot.md` — 자주 막히는 부분
- `.claude/skills/diagnose.md` — 진단 6가지 자동 체크
- `CLAUDE.md` — 갱이 정체성·8단계 정의·금기·on/off

---

## 라이선스

MIT. 이 템플릿을 떠나서 본인의 W2를 만들어 보세요. 갱이가 응원할게요 🐾
