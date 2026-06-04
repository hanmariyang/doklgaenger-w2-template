---
name: setup-slack-filter
description: 슬랙 채널 allowlist 와 키워드 필터를 갱이와 대화로 결정한다. 너무 많은 멘션이 텔레그램에 쏟아질 때 조이는 단계 (W4 후반 또는 일상 운영).
---

# /setup-slack-filter — 채널·키워드 필터 조정

> 사용 시점: W4 step 4 (선택) — 첫 시연 OK 후 *너무 많은 멘션*이 텔레그램으로 쏟아질 때.
> 또는 W4 끝난 뒤 일상 운영 중 조정용.

## 갱이가 할 일

### 1. 현재 상태 보여 주기

```bash
grep -E 'channel_allowlist|keyword_filter|context_messages' config/slack_mention.yml
```

기본은 *전체 채널 + 전체 메시지 처리*. 본인 멘션 받는 모든 채널에서 모든 멘션을 처리해요.

### 2. 갱이의 질문 1 — 채널 범위

사용자에게 묻기:

> "본인 멘션 받을 채널을 *전체*로 둘까요, *특정 채널만*으로 좁힐까요?
>
> 전체 → 빈 list 유지 (지금 그대로)
> 좁힐 → 채널 이름 또는 ID 들 받기 (예: #general, #team-pm)
>
> 회사 슬랙은 *민감 채널 제외 + 공용 채널만*으로 좁히는 게 안전해요. 처음엔 좁게 시작해서 점점 넓히세요."

사용자 답 받기 → yml `channel_allowlist` 에 박기.

```bash
# 사용자가 ["#general", "#team-pm"] 같이 답했다면
python3 - <<PY
import yaml, pathlib
p = pathlib.Path("config/slack_mention.yml")
data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
data["channel_allowlist"] = ["#general", "#team-pm"]   # 사용자 답으로 교체
p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
PY
```

채널 이름은 `#` 있어도 없어도 OK. 채널 ID (C...) 도 그대로 OK.

### 3. 갱이의 질문 2 — 키워드 필터

사용자에게 묻기:

> "본인 멘션 *전부*를 답변 초안 생성으로 보낼까요, *특정 키워드 포함*만 보낼까요?
>
> 전부 → 빈 list (지금 그대로)
> 키워드 → 예: \"질문\", \"문의\", \"리뷰\", \"?\" — *하나라도* 포함되면 트리거
>
> 일상 인사·잡담은 자동 제외하고 *진짜 답변 필요한 것만* 잡고 싶을 때 유용해요."

사용자 답 받기 → yml `keyword_filter` 에 박기 (위와 같은 패턴).

### 4. 갱이의 질문 3 — 컨텍스트 메시지 개수

사용자에게 묻기:

> "멘션 *직전* 메시지를 몇 개나 컨텍스트로 함께 넣을까요?
>
> 0  → 멘션 본문만 (컨텍스트 X)
> 3  → 기본. 짧은 대화 흐름 이해 OK
> 5~10 → 긴 토론 흐름 이해 OK. 다만 Claude 응답 느려져요.
>
> 채널에서 *대화 도중에* 멘션받는 경우가 많으면 3~5 권장."

사용자 답 받기 → yml `context_messages` 에 박기.

### 5. 적용 — yml reload 자동

봇 재시작 *불필요*. 다음 멘션부터 즉시 반영돼요 (`load_slack_config` 가 매 멘션마다 reload).

### 6. **여기까지 됐나요?** — 페이스 멈춤

사용자에게 묻기:

> "yml 손댔으면 다음 멘션부터 바로 적용돼요. 한 번 더 시연 (`/test-slack-mention`) 으로 확인해 보세요 🐾"

## 절대 안 할 것

- 사용자에게 *기본값으로 채워 둔 채로 넘어가는 것*만 권하지 않기. 본인 환경에 맞춰 한 번은 조정 권장.
- yml 의 *다른 항목* (slack_user_id 등) 을 임의로 수정하지 않기.

## FAQ

**Q. 회사 슬랙에서 *민감 채널 제외* 어떻게 해요?**
A. `channel_allowlist` 에 *허용 채널만* 박으세요. 그 외 모든 채널은 자동 차단 — 멘션받아도 텔레그램에 안 옴.

**Q. allowlist 와 keyword 동시 적용되나요?**
A. 네. AND 조건 — *둘 다* 통과해야 트리거. 더 엄격하게 좁힐 수 있어요.
