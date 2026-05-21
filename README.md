# 도클갱어 W2 — 본인 톤 첫 챗봇 템플릿

> 안녕하세요, 갱이예요 🐾
> 갱이가 8주 도클갱어 스터디의 W2 — "본인 톤 첫 챗봇"을 함께 만들어 드릴게요.

W2는 *임의의 영화/캐릭터 페르소나*를 골라서 텔레그램 봇으로 5문답까지 굴려 보는 한 주예요. 본인 도클갱어 전환은 W7~W8에 할 거니까, W2는 가볍게 즐기는 워밍업이라고 생각해 주세요.

---

## 갱이가 누구냐면

갱이는 *진짜 도클갱어가 태어나기 전까지의 임시 자리*예요. W8 데모데이 때는 옆 자리로 비켜 드릴 거고, 그때까지는 8단계 동안 옆에서 계속 따라다닐 거예요. 자기를 부를 땐 "갱이가", "갱이는"이라고 해요.

---

## 8단계 핵심 흐름

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

---

## 안 막히게 도와주는 파일들

- `docs/botfather-guide.md` — BotFather 3분 발급
- `docs/troubleshoot.md` — 자주 막히는 부분
- `.claude/skills/diagnose.md` — 진단 6가지 자동 체크
- `CLAUDE.md` — 갱이 정체성·8단계 정의·금기·on/off

---

## 라이선스

MIT. 이 템플릿을 떠나서 본인의 W2를 만들어 보세요. 갱이가 응원할게요 🐾
