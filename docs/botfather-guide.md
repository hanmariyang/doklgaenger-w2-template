# BotFather 토큰 3분 발급 가이드

> 텔레그램에서 봇을 만드는 건 BotFather 라는 *공식 봇*과 대화하는 방식이에요.
> 갱이가 텍스트로만 또박또박 알려 드릴게요 🐾

---

## 0. 사전 준비

- 텔레그램 앱에 본인 계정으로 로그인된 상태
- 모바일 / 데스크탑 / 웹 어디든 OK

## 1. BotFather 찾기

텔레그램 검색창에 `@BotFather` 입력 → *파란 체크 마크*가 붙은 공식 계정을 선택.

⚠️ 가짜 BotFather 가 많아요. **반드시 파란 체크** 확인.

## 2. 봇 만들기 시작

BotFather 대화창에서:

```
/newbot
```

BotFather 가 두 가지를 물어봐요:

### 2-1. 봇 이름 (display name)

화면에 보일 이름. 한글·이모지 OK.
예: `갱이 챗봇 (테스트)`

### 2-2. 봇 username

`@xxx_bot` 형식. **반드시 `_bot` 또는 `bot` 으로 끝나야 함**.
예: `gangi_doppel_bot`, `dokl_w2_test_bot`

이미 사용 중인 username 이면 "Sorry, this username is already taken." 라고 답해 줘요. 다른 걸로 다시.

## 3. 토큰 받기

성공하면 BotFather 가 이렇게 답해요:

```
Done! Congratulations on your new bot. ...

Use this token to access the HTTP API:
1234567890:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA

Keep your token secure ...
```

→ **`1234567890:AAAA...` 이게 토큰**이에요. 갱이가 step 5 에서 받아 갈 거예요.

## 4. 토큰 보관 원칙

- ⚠️ **이 토큰은 비밀번호와 동급**이에요. 누군가가 알면 봇을 *원격에서 가로챌* 수 있어요.
- 갱이가 절대 안 하는 것: 이 토큰을 *git push* 하기.
- 채팅·이메일·노션에 *그대로 paste* 하지 마세요.
- 노출됐으면: BotFather `/revoke` → 같은 봇의 토큰을 새로 발급.

## 5. (선택) 봇 설정 더 다듬기

BotFather 에서:

| 명령 | 설명 |
|------|------|
| `/setdescription` | 봇 프로필에 보일 설명 |
| `/setabouttext` | 봇 정보 카드 텍스트 |
| `/setuserpic` | 봇 프로필 사진 |
| `/setcommands` | `/start` 외에 추가 명령 등록 |
| `/deletebot` | 더 안 쓰면 삭제 |

W2 학습용이면 *기본만* 두고 시작해도 충분해요 🐾

## 6. 다음 단계

토큰을 받았으면 Claude Code 에서:

```
/setup-telegram
```

갱이가 `.env` 에 박고 `getMe` 로 검증해 드려요.
