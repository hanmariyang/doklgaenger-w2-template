---
name: setup-sns
description: MBTI SNS 자동 게시(W6 부가기능) 셋업 — mbti.triforge.kr 가입 → API 키 발급 → .env 에 박기 → config/sns.yml 복사 + mbti_tag 설정 → 봇 재시작 → /sns 로 미리보기 확인. 키 안전·외부 격리 안내 포함.
---

# /setup-sns — SNS 자동 게시 셋업 🐾

> 사용 시점: W6 부가기능 시작. `/sns <내용>` 으로 *메모를 페르소나 톤 SNS 글로 바꿔 미리보기 → 확인 후 게시* 하는 기능을 켜는 단계예요.
>
> 의도: W2 인프라(텔레그램 봇 + 페르소나) **그대로** + *기능 1개 추가*. 게시는 **항상 미리보기 확인 후** — 공개되고 되돌리기 어려운 글이니까요.

## 갱이가 할 일

### 0. 한 줄 설명

> "갱이가 이번엔 *글쓰기*를 도와요 🐾 `/sns 오늘 있었던 일…` 처럼 메모를 던지면, 페르소나가 *본인 톤의 짧은 SNS 글*로 다듬어서 텔레그램에 미리보기로 보여줘요. 마음에 들면 [게시] 버튼, 아니면 [취소]. [게시] 눌러야 비로소 mbti.triforge.kr 에 올라가요."

### 1. mbti.triforge.kr 가입 + API 키 발급

사용자에게 안내:

> "1) https://mbti.triforge.kr/signup 에서 가입해 주세요 (본인 MBTI 유형 선택).
>  2) 로그인 후 *설정 / API 키* 메뉴에서 **API 키**를 발급받으세요.
>  3) 그 키 한 줄을 복사해 두세요 — 다음 단계에서 `.env` 에 박아요."

⚠️ 안내 한 줄: "이 키는 *공개 글을 올리는 쓰기 권한*이에요. 비밀번호처럼 다루세요 — 공유·캡처·git push 금지. 분실하면 mbti.triforge.kr 에서 재발급하면 돼요."

### 2. `.env` 에 키 박기

```bash
test -f .env || cp .env.example .env
grep -q '^MBTI_SNS_API_KEY=' .env || echo 'MBTI_SNS_API_KEY=' >> .env
```

사용자가 발급받은 키를 `.env` 의 `MBTI_SNS_API_KEY=` 뒤에 붙이도록 안내 (갱이가 *대신 키를 받아 적지 않기* — 본인 손으로).

> "`.env` 를 열어서 `MBTI_SNS_API_KEY=발급받은키` 처럼 채워 주세요.
>  `MBTI_SNS_MCP_URL` 은 기본값 그대로 두면 돼요 (비워둬도 자동으로 mbti-mcp.triforge.kr 써요)."

### 3. `config/sns.yml` 복사 + mbti_tag 설정

```bash
cp config/sns.yml.example config/sns.yml
```

갱이의 질문:

> "본인 MBTI 유형이 뭐예요? (예: ENFP, INTJ) — 게시 글에 태그로 붙어요. 안 붙이고 싶으면 비워둬도 돼요."

사용자 답 → yml `mbti_tag` 에 박기 (python3 로 안전하게):

```bash
python3 - <<PY
import yaml, pathlib
p = pathlib.Path("config/sns.yml")
data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
data["mbti_tag"] = "ENFP"   # 사용자 답으로 교체. 비우려면 ""
p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
print("saved mbti_tag")
PY
```

(선택) 길이(`max_len`)·톤 힌트(`style`)·즉시 ack(`ack.converting`) 도 본인 취향대로. 기본값으로 둬도 OK.

### 4. 봇 재시작 (`/sns` 명령 등록을 위해)

W6 코드(`/sns` 명령)가 봇에 *반영*되려면 한 번 재시작이 필요해요:

```bash
./scripts/stop.sh && ./scripts/start.sh
# 또는: /bot stop → /bot start
```

(yml *양식* 변경은 매 `/sns` 마다 자동 reload 라 재시작 불필요. 단 *코드*가 갱신됐으니 이번 한 번은 재시작.)

### 5. 첫 시연 — 미리보기 확인

> "텔레그램에서 봇에게 이렇게 보내 보세요:
>   `/sns 오늘 도클갱어 W6 마무리. 봇이 내 톤으로 SNS 글까지 써준다니 신기하다`
>
>  몇 초 뒤 *미리보기* 와 [✅ 게시] [✖ 취소] 버튼이 와요.
>  - 마음에 들면 [게시] → mbti.triforge.kr 에 올라가고 post 번호 + 링크가 와요.
>  - 아쉬우면 [취소] → 폐기. 다시 `/sns` 로 시도.
>
>  *반드시 미리보기를 눈으로 확인하고* 게시하세요 — 한 번 올라가면 공개돼요."

### 6. **여기까지 됐나요?** — 페이스 멈춤

> "미리보기 → [게시] → post 번호·링크까지 왔나요? 됐으면 `/test-sns` 로 한 번 더 굴려보고 피드(mbti.triforge.kr)에서 본인 글을 확인해 봐요 🐾  안 됐으면 막힌 지점 알려 주세요."

## 절대 안 할 것

- API 키를 갱이가 *대신 받아 적거나* 로그·채팅에 노출하지 않기 — 본인 손으로 `.env` 에만.
- 사용자 의향 묻지 않고 봇을 *대신* 재시작하지 않기 (명령 보여주기까지, 실행은 본인).
- **mbti.triforge.kr 는 *원탁(외부) 시스템*이에요** — 우리는 *연결만* 해요. 그쪽 코드·파일을 건드리거나, 거기에 원탁 격리 대상·민감정보(회사 코드명·제3자 실명·내부 정보)를 게시하지 않기. 학습용 가벼운 글만.
- 자연어로 *자동 게시* 만들자고 제안하지 않기 — `/sns` 명령 + 미리보기 확인은 *의도적*. 사적 채팅이 멋대로 SNS 에 올라가는 사고를 막는 안전장치예요.

## FAQ

**Q. 미리보기 없이 바로 올리게 할 수 없나요?**
A. 안 돼요 — 의도적이에요. 공개되고 되돌리기 어려운 게시라 *항상 확인 게이트*. (W4 의 "봇이 멋대로 슬랙에 답신 안 함" 안전 원칙과 같은 철학.)

**Q. 키가 만료되면요?**
A. 게시할 때 "인증 실패 (401)" 안내가 와요. mbti.triforge.kr 에서 재발급 → `.env` 의 `MBTI_SNS_API_KEY` 갱신 → 봇 재시작.

**Q. mbti_tag 를 바꾸면 재시작해야 하나요?**
A. 아니요. `config/sns.yml` 은 매 `/sns` 마다 reload 라 다음 글부터 바로 적용돼요. (코드가 바뀌었을 때만 재시작.)
