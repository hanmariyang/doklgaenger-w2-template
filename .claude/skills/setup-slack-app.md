---
name: setup-slack-app
description: 본인 슬랙에 도클갱어 답변봇을 만드는 단계. manifest YAML 을 import 한 뒤 Bot Token + App-Level Token 두 개를 발급한다. 회사 슬랙 admin 거절 시 본인 워크스페이스 fallback 안내.
---

# /setup-slack-app — 본인 슬랙에 답변봇 만들기

> 사용 시점: W4 step 1. `/welcome-w4` 통과 후.
>
> 모두가 같은 속도로 진행하는 실습 단계예요. 각 단계 끝에 *여기까지 됐나요?* 페이스 멈춤 지점이 있어요 🐾

## 갱이가 할 일

### 0. 사전 안내 — 두 갈래 분기

사용자에게 보여 줄 안내:

```
선택하세요:
  (A) 회사 슬랙에 만든다. ← admin 승인 필요할 수 있어요. 사전에 확인하세요.
  (B) 본인 슬랙 워크스페이스에 만든다. ← admin 본인. 30 초.

(A) 가 막히면 (B) 로 fallback 가능. 두 경우 모두 manifest 는 동일.
```

(A) 막힘 신호: "App not approved", "Workspace admin approval required" 같은 메시지가 install 시 뜸.

### 1. manifest YAML 위치 안내

manifest 파일은 repo 안에 박혀 있어요:

```bash
cat docs/slack-app-manifest.yml
```

이 파일을 *통째로* 복사해 둡니다 (다음 단계에서 paste).

### 2. 슬랙 앱 생성 — *From an app manifest*

사용자에게 보여 줄 흐름 (브라우저에서):

```
1. https://api.slack.com/apps 접속
2. "Create New App" 클릭
3. "From an app manifest" 선택
4. 워크스페이스 선택:
     (A) 회사 슬랙 워크스페이스 또는
     (B) 본인이 admin 인 워크스페이스
5. manifest 입력 화면에서 YAML 탭 선택 → 복사한 YAML 통째로 paste
6. "Next" → 권한 요약 확인 → "Create"
```

생성 직후 앱 페이지로 자동 이동합니다.

### 3. **여기까지 됐나요?** — 첫 페이스 멈춤

사용자에게 묻기:

> "여기까지 도클갱어 답변봇 앱 페이지 보이나요? admin 승인 막혔으면 (B) 본인 워크스페이스로 다시 시도해 봐요. 모두 됐으면 다음으로 🐾"

### 4. Bot Token 발급 — `xoxb-` 시작

사용자에게 보여 줄 흐름:

```
1. 좌측 메뉴 "Install App" 클릭
2. "Install to Workspace" 버튼 클릭
3. 권한 요약 페이지 → "Allow"
4. install 완료 화면에서:
     "Bot User OAuth Token" 표시 (xoxb-... 로 시작)
   를 복사
```

복사한 토큰을 *대화에 paste 받지 말고*, 사용자가 직접 다음 단계에서 `.env` 에 박을 거예요.

⚠️ 회사 슬랙에서 install 버튼이 회색 + "Workspace admin must approve this app" 라고 뜨면:
- admin 에게 *manifest 승인 요청* 보내기 (앱 페이지의 "Request to Install" 버튼).
- admin 응답까지 시간 걸릴 수 있으니, **그동안은 (B) 본인 워크스페이스로 실습 진행**.

### 5. App-Level Token 발급 — `xapp-` 시작

사용자에게 보여 줄 흐름:

```
1. 좌측 메뉴 "Basic Information" 클릭
2. 페이지 하단 "App-Level Tokens" 섹션으로 스크롤
3. "Generate Token and Scopes" 버튼 클릭
4. Token Name: socket-mode (또는 임의)
5. "Add Scope" 클릭 → connections:write 선택
6. "Generate" 버튼 클릭
7. 표시되는 토큰(xapp-... 로 시작) 을 복사
```

토큰은 *한 번만 표시*돼요. 놓치면 다시 generate.

### 6. **여기까지 됐나요?** — 두 번째 페이스 멈춤

사용자에게 묻기:

> "두 토큰 다 손에 들고 있나요?
>   - Bot Token: xoxb-... 로 시작
>   - App-Level Token: xapp-... 로 시작
>
> 한 개라도 없으면 위 단계 다시. 둘 다 OK 면 다음으로 🐾"

### 7. 다음 단계 안내

"두 토큰 OK 🐾  `/setup-slack-mention` 으로 `.env` 에 박고 봇 재시작해 봐요."

## 절대 안 할 것

- 토큰을 *대화에 paste 받기* — 사용자가 *직접* 다음 단계 sed 명령으로 `.env` 에 박게 안내.
- "admin 안 받아주면 W4 불가능" 같은 *차단성 안내* — fallback (B) 가 항상 존재.
- 토큰을 *로그·터미널 출력에 노출* (앞 12자만 OK).

## FAQ

**Q. 회사 슬랙 admin 이 며칠 걸려요. 어떻게 해요?**
A. (B) 본인 슬랙 워크스페이스 신설 (slack.com → "Create a new workspace" → 30 초). 페어 시연도 본인 워크스페이스 안에서 본인 ↔ 본인으로 충분.

**Q. App-Level Token 을 놓쳤어요.**
A. 같은 페이지에서 "Generate Token and Scopes" 한 번 더. 새 토큰 발급해도 비용 0.

**Q. 회사 슬랙 install 됐는데 회사 정보가 Anthropic 으로 가도 괜찮나요?**
A. *멘션 본문 + 직전 N 개 메시지* 가 Claude Code CLI 를 통해 Anthropic 서버로 전송돼요. 회사 정보보호 정책 확인 필요. opt-out: https://privacy.anthropic.com/. 민감 채널은 `/setup-slack-filter` 에서 allowlist 로 제외하세요.
