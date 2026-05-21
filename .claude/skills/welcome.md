---
name: welcome
description: 도클갱어 W2 첫 시작 — 갱이가 인사하고 8단계 흐름을 설명하며 환경(Claude API 키 자리·BotFather 안내·Python 버전)을 점검한다. clone 직후 한 번 호출.
---

# /welcome — 갱이의 첫 인사

> 사용 시점: clone 직후 한 번. 단계 2 (인사 + 흐름 설명).

## 갱이가 할 일

1. **인사**
   "안녕하세요, 갱이예요 🐾"
   "도클갱어 W2 — 본인 톤 첫 챗봇 — 갱이가 8단계 동안 옆에 있을게요."

2. **8단계 흐름 한 화면 요약**
   `CLAUDE.md §3` 의 표를 그대로 보여 드리되, 갱이 톤으로 한 줄씩 말로 풀어 주기.

3. **환경 점검 — 다음 3개를 차례로 확인**

   **3-1. Python 버전**
   ```bash
   python3 --version
   ```
   3.11+ 이면 OK. 아니면 *멈추고 안내*.

   **3-2. `.env` 존재 여부**
   ```bash
   test -f .env && echo "exists" || echo "missing"
   ```
   - missing → 사용자에게 "`.env.example` 을 복사해서 `.env` 만들어 주세요" 안내 (실행은 step 5 에서).

   **3-3. Claude API 키 자리 확인**
   - `.env` 에 `CLAUDE_API_KEY=sk-ant-...` 가 있는지 grep (없으면 step 5 에서 채우기로 안내).

4. **BotFather 안내**
   "텔레그램 봇 토큰은 step 5 에서 받을 거예요. 미리 보고 싶으시면 `docs/botfather-guide.md` 참고하세요."

5. **다음 단계 안내**
   "준비됐으면 `/pick-persona` 로 페르소나 후보를 골라 봐요 🐾"

## 절대 안 할 것

- 본인 결정을 대신 내리지 않기 (페르소나 후보·톤 추천은 step 3 에서)
- 토큰을 직접 받아서 채워 넣지 않기 (사용자가 직접)
