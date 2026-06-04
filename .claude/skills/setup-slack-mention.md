---
name: setup-slack-mention
description: 발급받은 슬랙 토큰 2개를 `.env` 에 박고, config/slack_mention.yml 을 만들고, 본인 slack_user_id 를 학습시키고, 봇을 재시작한다. 첫 멘션 시연 직전 단계.
---

# /setup-slack-mention — `.env` 채우기 + 봇 재시작

> 사용 시점: W4 step 2. `/setup-slack-app` 에서 두 토큰 받은 직후.

## 갱이가 할 일

### 1. config 파일 만들기

```bash
test -f config/slack_mention.yml || cp config/slack_mention.yml.example config/slack_mention.yml
```

`.gitignore` 에 박혀 있어서 안심하고 채워도 OK.

### 2. `.env` 에 토큰 박기

사용자에게 두 토큰을 *한 번에 한 줄씩* 받습니다 (대화 paste OK — 본인 단말):

```bash
# 사용자가 paste 한 Bot Token (xoxb-...) 을 받아서:
BOT_TOKEN='<사용자_입력_xoxb-...>'
sed -i.bak "s|^SLACK_BOT_TOKEN=.*|SLACK_BOT_TOKEN=${BOT_TOKEN}|" .env
rm .env.bak

# 사용자가 paste 한 App-Level Token (xapp-...) 을 받아서:
APP_TOKEN='<사용자_입력_xapp-...>'
sed -i.bak "s|^SLACK_APP_TOKEN=.*|SLACK_APP_TOKEN=${APP_TOKEN}|" .env
rm .env.bak
```

⚠️ `.env` 가 git 에 들어가지 않는지 한 번 더:

```bash
git check-ignore .env  # ".env" 가 출력되어야 OK
```

### 3. 본인 slack user_id 받기 + yml 에 박기

본인 슬랙 user_id (UXXXXXXXX) 가 필요해요. 본인이 멘션받는 메시지를 잡으려고요.

사용자에게 보여 줄 흐름:

```
슬랙에서:
1. 좌측 상단 본인 프로필 사진 클릭 → 프로필 보기
2. 프로필 화면에서 "더 보기" (⋯) → "멤버 ID 복사"
3. 복사된 ID 가 UXXXXXXXX 형태
```

사용자가 paste 한 ID 를 받아서:

```bash
USER_ID='<사용자_입력_UXXXXXXXX>'
# yq 가 있으면 yq 로, 없으면 python 으로 안전하게 박기
python3 - <<PY
import yaml, pathlib
p = pathlib.Path("config/slack_mention.yml")
data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
data["slack_user_id"] = "${USER_ID}"
p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
print("saved slack_user_id =", "${USER_ID}")
PY
```

### 4. **여기까지 됐나요?** — 첫 페이스 멈춤

사용자에게 묻기:

> ".env 에 토큰 2개, config/slack_mention.yml 에 본인 user_id, 다 박혔나요? 됐으면 다음으로 🐾"

### 5. (선택) 즉시 ack 메시지 박기

페르소나 톤으로 *즉시* 텔레그램에 보내는 한 줄. 페르소나 톤 살아있다는 신호.

사용자에게 본인 페르소나에 어울리는 한 줄 받기 → yml `ack_message` 에 박기:

```bash
ACK='<사용자_입력_한_줄>'
python3 - <<PY
import yaml, pathlib
p = pathlib.Path("config/slack_mention.yml")
data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
data["ack_message"] = "${ACK}"
p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
PY
```

비워두면 ack 안 보내요 — Claude 응답만 와요. 본인 취향에 따라 선택.

### 6. (선택) TELEGRAM_PUSH_CHAT_ID 설정 안내

봇이 슬랙 멘션 답변 초안을 본인 텔레그램으로 push 할 때 사용할 chat_id 예요.

```
이미 W3 에서 본 봇에 메시지를 한 번 보내신 분은:
   /tmp/doppel-last-chat-id 가 자동 학습된 값을 가지고 있어요.
   .env 의 TELEGRAM_PUSH_CHAT_ID 는 *비워둬도* 자동 사용돼요.

아직 한 번도 메시지 안 보낸 분은:
   1) 텔레그램에서 본인 봇에 아무 메시지 1회 보내기
   2) 봇 로그 (tail -f /tmp/doppel-bot.log) 에서 `incoming chat_id=NNN` 확인
   3) 그 NNN 을 .env 의 TELEGRAM_PUSH_CHAT_ID 에 박기 (확실히 하고 싶을 때만)
```

### 7. 봇 재시작

```bash
./scripts/stop.sh
./scripts/start.sh
# 또는: /bot stop → /bot start
```

재시작 직후 로그에서 슬랙 연결 확인:

```bash
tail -n 30 /tmp/doppel-bot.log | grep -E 'slack|bot_starting'
```

`slack_socket_mode_starting…` + `slack_bot_auth_test ok` 가 보이면 OK 🐾

### 8. **여기까지 됐나요?** — 두 번째 페이스 멈춤 (재시작 후)

사용자에게 묻기:

> "로그에 `slack_bot_auth_test ok` 줄 보이나요? `slack_app_build_failed` 가 보이면 토큰 두 개 정확한지 다시 확인. 됐으면 첫 시연으로 🐾"

### 9. **첫 시연** — 본인이 자기를 멘션

사용자에게 안내:

> "본인 슬랙의 아무 채널 (혹은 #random 같이 부담 적은 곳) 에서 본인을 멘션 (@본인이름) 해보세요. 메시지: \"@본인 안녕\".
>
> 5~30 초 안에 본인 텔레그램에 두 메시지 도착해야 해요:
>   1) 즉시 ack (yml 에 박았다면)
>   2) Claude 가 만든 답변 초안 본문
>
> 도착했으면 결승선 🐾  안 도착했으면 `/diagnose` 6가지 체크."

## 절대 안 할 것

- 사용자 토큰을 *별도 저장* — `.env` 에만 박고 다른 곳 X.
- 토큰을 *터미널에 echo* (앞 12자만 OK).
- 봇을 사용자 승인 없이 stop/start 하지 않기 — 명령 *보여주기* 까지만, 실행은 사용자 손.

## FAQ

**Q. `slack_app_build_failed` 가 떠요.**
A. `.env` 의 두 토큰 줄에 따옴표·공백·줄바꿈 없는지 확인. `cat .env | grep SLACK_` 로 출력값이 정확히 한 줄씩이어야 OK.

**Q. 멘션을 보냈는데 텔레그램에 아무것도 안 와요.**
A. 세 가지 체크:
   1) 봇이 그 채널에 *초대*되어 있나요? (#채널에서 `/invite @도클갱어 답변봇`)
   2) slack_user_id 가 본인 ID 맞나요? (`grep slack_user_id config/slack_mention.yml`)
   3) `tail -f /tmp/doppel-bot.log` 에서 `slack_mention_hit` 나옴? 안 나오면 이벤트 자체가 안 와요 (scope·channel 초대 문제).
