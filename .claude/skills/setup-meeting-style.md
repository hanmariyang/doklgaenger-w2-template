---
name: setup-meeting-style
description: 회의록 양식(섹션 on/off · 길이 · 액션아이템 형식 · ack 메시지)을 갱이와 대화로 결정해 config/meeting_notes.yml 에 박는다. W5 첫 시연 후 양식 lock 단계.
---

# /setup-meeting-style — 회의록 양식 정하기

> 사용 시점: W5 step 4. `/test-meeting-notes` 로 첫 회의록 받아 본 직후.
> yml 변경은 매 회의록마다 자동 reload — **재시작 불필요**.

## 갱이가 할 일

### 1. config 준비 + 현재 상태 보여 주기

```bash
test -f config/meeting_notes.yml || cp config/meeting_notes.yml.example config/meeting_notes.yml
grep -E 'summary|discussion|decisions|action_items|open_questions|length|action_item_format' config/meeting_notes.yml
```

기본은 *5개 섹션 모두 켜짐 + medium 길이 + checkbox 형식*.

### 2. 갱이의 질문 1 — 어떤 섹션을 넣을까요

사용자에게 묻기:

> "회의록에 넣을 섹션을 골라 주세요. 안 쓰는 건 꺼도 돼요:
>
>  ① 한 줄 요약        — 이 회의가 무엇이었는지 한 문장
>  ② 핵심 논의          — 오간 논점 항목별
>  ③ 결정사항          — 확정된 결정만
>  ④ 액션아이템        — 할 일 + 담당자 + 기한
>  ⑤ 미해결 질문        — 결론 못 낸 질문·보류
>
>  예: '나는 ①③④만' 처럼 답해 주세요. 전부 OK 면 그대로 둘게요."

사용자 답 → yml `sections` 에 박기 (python3 로 안전하게):

```bash
python3 - <<PY
import yaml, pathlib
p = pathlib.Path("config/meeting_notes.yml")
data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
data.setdefault("sections", {})
# 사용자가 끈 섹션만 False 로. 예: 핵심 논의·미해결 질문 끄기
data["sections"]["discussion"] = False     # 사용자 답으로 교체
data["sections"]["open_questions"] = False  # 사용자 답으로 교체
p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
print("saved sections")
PY
```

### 3. 갱이의 질문 2 — 길이

사용자에게 묻기:

> "회의록 길이를 어떻게 할까요?
>
>  short  → 각 항목 1줄. 군더더기 0.
>  medium → 각 항목 1~2줄. (기본)
>  long   → 각 항목에 맥락 한 줄 더 (단 *메모에 있는 사실 안에서만*).
>
>  회의가 짧고 결정 위주면 short, 논의가 많으면 medium~long 권장."

사용자 답 → yml `length` 에 박기 (위와 같은 python3 패턴, `data["length"]="short"`).

### 4. 갱이의 질문 3 — 액션아이템 형식

사용자에게 묻기:

> "액션아이템(할 일)을 어떻게 적을까요?
>
>  checkbox → - [ ] 할 일 — 담당자 · 기한   (노션·텔레그램에 그대로 체크리스트, 기본)
>  numbered → 1. 할 일 — 담당자 · 기한
>  plain    → - 할 일 (담당자, 기한)
>
>  노션에 그대로 옮길 거면 checkbox 가 편해요."

사용자 답 → yml `action_item_format` 에 박기.

### 5. (선택) 갱이의 질문 4 — 즉시 ack 메시지

> "회의 메모를 받으면 *바로* 보낼 페르소나 톤 한 줄이 있으면 좋아요. 회의록 만드는 몇 초 동안 '정리 중' 신호예요.
>
>  예) 토니 스타크: '회의록? JARVIS, 핵심만 추려.'
>      셜록: '흥미롭군. 뼈대를 추려 보겠네.'
>
>  비워두면 ack 없이 회의록만 와요. 본인 취향대로."

사용자 답 → yml `ack_message` 에 박기.

### 6. 적용 — yml reload 자동

봇 재시작 *불필요*. 다음 회의록부터 즉시 반영돼요 (`load_meeting_config` 가 매 회의록마다 reload).

### 7. **여기까지 됐나요?** — 페이스 멈춤

사용자에게 묻기:

> "양식 정했으면 `/test-meeting-notes` 로 한 번 더 굴려서 마음에 드는지 보세요. 마음에 들면 그게 본인 회의록 양식 lock 이에요 🐾"

## 절대 안 할 것

- 모든 섹션을 *끄도록* 권하지 않기 — 최소 한 줄 요약은 남아요(코드가 강제). 그래도 한두 개는 권장.
- yml 의 *다른 항목*(enabled 등)을 임의로 끄지 않기.
- 사용자에게 기본값 그대로 넘기라고만 하지 않기 — 본인 회의 스타일에 맞춰 한 번은 조정 권장.

## FAQ

**Q. 섹션 순서를 바꾸고 싶어요.**
A. 회의록 섹션 순서는 *고정*이에요(요약→논의→결정→액션→질문). 가독성 위해 의도적으로 고정했어요. on/off 만 조정돼요.

**Q. 양식을 또 바꾸면 재시작해야 하나요?**
A. 아니요. yml 은 매 회의록마다 reload 라 *다음 메모부터 바로* 적용돼요. (코드가 바뀌었을 때만 재시작.)
