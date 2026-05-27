---
name: setup-ical
description: Google Calendar 의 비공개 iCal URL 을 받아 `.env` 의 `ICAL_URL` 에 저장한다. URL 의 비밀 등급(캘린더 전체 read)을 명확히 안내하고 가벼운 fetch 검증을 수행한다.
---

# /setup-ical — iCal URL 받기

> 사용 시점: W3 step 1. `/welcome-w3` 통과 후.
>
> W3 핵심: iCal URL **1줄**만 받으면 셋업 끝. OAuth · Google Cloud Console 0건.

## 갱이가 할 일

### 1. 비공개 iCal URL 발급 안내

사용자에게 *직접* 받아 오게 안내해요 (갱이가 대신 못 받아요):

```
Google Calendar 웹에서:
1. 좌측 "내 캘린더" 에서 사용할 캘린더의 ⋮ 메뉴 → "설정 및 공유"
2. 페이지 하단의 *캘린더 통합* 섹션으로 스크롤
3. "캘린더의 비공개 주소 (iCal 형식)" — 자물쇠 아이콘 클릭하여 표시
4. `https://calendar.google.com/calendar/ical/.../private-.../basic.ics` 복사
```

복사한 URL 을 채팅에 paste 받아요.

### 2. **주의 메시지 — 반드시 표시**

```
🐾 잠깐만요!

이 iCal URL 은 1줄짜리 비밀번호 같은 거예요:
- *캘린더 전체 read 권한* 이 들어 있어요.
- 무분별한 공유 위험해요 — 누구든 이 URL 만 있으면 모든 일정 볼 수 있어요.
- *개인 일정만 관리하는 캘린더* 권장해요.
- 회사 일정이면 본인이 책임지고 사용하세요.
- 노출 시 회전: Google Calendar 설정 → "비공개 주소 재설정".
```

```
🔍 Anthropic 서버 전송 안내 (TF-958 DVA 권고 — 의뢰자 인지 필수)

이 봇은 매일 아침 *오늘 일정 리스트*를 Claude Code CLI 로 보내요.
Claude Code 는 그 정보를 *Anthropic 서버*에서 처리해서 페르소나 톤으로 그려서 돌려줘요.

→ 회의명·참석자·고객명 같은 *캘린더 텍스트가 Anthropic 으로 전송*돼요.

회사 보안 정책 · GDPR · 내부 정보보호 규정이 적용되는 환경이면:
- Anthropic 데이터 사용 opt-out 미리 설정 권장 (https://privacy.anthropic.com/)
- 또는 회사 캘린더 대신 *개인 캘린더*로 시작
```

회사 캘린더 차단은 안 해요 (학습용). 단 *주의 메시지 2건*(URL 보호 + Anthropic 전송)을 반드시 함께 보여 드려야 해요.

### 3. `.env` 에 박기

```bash
# .env 가 없으면 만들기
test -f .env || cp .env.example .env

# 받은 URL 을 .env 에 박는 패턴 (사용자가 paste 한 값으로)
URL='<사용자_입력_URL>'
# macOS sed 호환 — 슬래시가 많으니 구분자는 |
sed -i.bak "s|^ICAL_URL=.*|ICAL_URL=${URL}|" .env
rm .env.bak
```

`.env` 가 git 에 push 되지 않는지 한 번 더:

```bash
git check-ignore .env  # ".env" 가 출력되어야 OK
```

### 4. 가벼운 fetch 검증

```bash
URL="$(grep '^ICAL_URL=' .env | cut -d= -f2-)"
curl -sS -A "Doklgaenger-W3/1.0" --max-time 20 "$URL" | head -3
```

응답 첫 줄에 `BEGIN:VCALENDAR` 가 보이면 OK 🐾  안 보이면:
- 404/403 → URL 재발급. 또는 캘린더 권한 확인.
- 빈 응답 → 네트워크 또는 Google 일시 장애. 다시.

URL 전체를 로그·메시지에 그대로 노출하지 않아요 — 앞뒤만 짧게 (`...`/basic.ics).

### 5. 봇 재시작 안내

```bash
./scripts/stop.sh
./scripts/start.sh
# 또는: /bot stop  →  /bot start
```

재시작 후 봇이 `ICAL_URL` 을 읽어요. `.env` 는 부팅 시 1회 load.

### 6. 다음 단계 안내

"iCal OK 🐾  `/today` 라고 보내거나 텔레그램에서 \"오늘 일정\" 이라고 메시지 보내 봐요."

## 금기

- 사용자 URL 을 *임의로 회전·삭제* 하지 않기
- URL 전문을 *로그·터미널 출력에 노출* 하지 않기 (앞 60자만)
- `.env` 를 *git add* 시도 하지 않기
- "회사 캘린더 차단" — 도클갱어는 학습용이라 차단 X. 주의 메시지로 충분.
