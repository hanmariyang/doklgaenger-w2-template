---
name: setup-telegram
description: BotFather 에서 받은 텔레그램 봇 토큰을 `.env` 에 저장하고, `getMe` 로 토큰 유효성을 검증한다. Claude API 키 자리도 같이 채운다.
---

# /setup-telegram — 인프라 셋업

> 사용 시점: 단계 5 (인프라 셋업). `/simulate` 통과 후.

## 갱이가 할 일

### 1. `.env` 파일 준비

```bash
test -f .env || cp .env.example .env
```

### 2. BotFather 토큰 안내

`docs/botfather-guide.md` 의 3분 발급 가이드를 사용자에게 보여 준다.
*갱이가 대신 받지 않는다* — 사용자가 직접 BotFather 대화 후 토큰을 paste.

### 3. `.env` 채우기

사용자에게 두 값을 차례로 받아서 `.env` 에 적는다.

```bash
# 받은 토큰을 .env 에 박는 패턴
sed -i.bak "s|^CLAUDE_API_KEY=.*|CLAUDE_API_KEY=<사용자_입력>|" .env
sed -i.bak "s|^TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=<사용자_입력>|" .env
rm .env.bak
```

⚠️ **`.env` 가 git 에 들어가지 않는지 확인**: `git check-ignore .env` 가 `.env` 를 출력해야 함.

### 4. `getMe` 검증

토큰 유효성 확인 (텔레그램 API):

```bash
TOKEN="$(grep '^TELEGRAM_BOT_TOKEN=' .env | cut -d= -f2-)"
curl -s "https://api.telegram.org/bot${TOKEN}/getMe" | python3 -m json.tool
```

응답 JSON 의 `"ok": true` 와 `"username"` 을 확인하고 사용자에게 보여 준다.

### 5. Claude API 키 가벼운 검증

키 형식이 `sk-ant-...` 로 시작하는지만 grep. (실제 호출은 step 6 시작 시 자동 검증됨)

### 6. 다음 단계 안내

"인프라 OK 🐾  `/bot start` 로 봇 띄워 봐요."

## 금기

- 사용자 토큰을 갱이가 *임의로 회전*하지 않기
- 토큰을 *로그에 그대로 출력*하지 않기 (앞 6자만 보여 주기)
- `.env` 를 *git add 시도*하지 않기
