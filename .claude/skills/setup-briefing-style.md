---
name: setup-briefing-style
description: 갱이가 사용자에게 3가지 질문을 던져 브리핑 양식(format·length·show_empty)을 사용자와 *대화로* 결정하고 `config/briefing.yml` 에 박는다. 마지막에 시연 브리핑 1회로 lock.
---

# /setup-briefing-style — 양식·페르소나 톤 결정

> 사용 시점: W3 step 4. `/today` 첫 시도 후.
>
> 의뢰자 결정 정합 — 브리핑 양식은 **갱이와 대화로 결정**해요. 갱이가 임의로 추천 1건 박지 않아요.

## 갱이가 할 일

### 0. 사전 준비

```bash
test -f config/briefing.yml || cp config/briefing.yml.example config/briefing.yml
```

### 1. 질문 3개 — 한 번에 묻지 말고 하나씩

**Q1. 형식 — 오늘 일정이 5개 있을 때 어떻게 보여드릴까요?**

```
(a) 시간순 리스트 + 페르소나 한 줄 코멘트
(b) 핵심 1줄 요약 + 페르소나 한 줄 코멘트
(c) 상세 (장소·메모 포함 단락)
```

답에 따라:
- a → `format: list-with-comments` (기본)
- b → `format: one-liner`
- c → `format: detailed`

**Q2. 길이 — 짧게 / 중간 / 길게**

```
short  : 총 3줄 내외
medium : 각 일정 1줄 + 마무리 1줄
long   : 페르소나의 짧은 생각까지 포함
```

답에 따라 `length: short | medium | long`.

**Q3. 빈 시간 / 빈 하루도 표시할까요?**

```
yes : "14~16시 비어있음" 또는 "오늘 일정 없음 — 한가한 날이에요" 같이
no  : 일정 있는 항목만, 빈 하루는 짧게 한 줄
```

답에 따라 `show_empty: true | false`.

### 2. `config/briefing.yml` 의 style 섹션 박기

```bash
# python 한 줄로 yml 안전 갱신 (sed 보다 안전)
python3 - <<'PY'
import yaml
from pathlib import Path
p = Path('config/briefing.yml')
data = yaml.safe_load(p.read_text(encoding='utf-8')) or {}
style = data.get('style') or {}
style.update({
    'format': '<사용자_Q1_답>',
    'length': '<사용자_Q2_답>',
    'show_empty': <사용자_Q3_답_bool>,
})
data['style'] = style
p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding='utf-8')
print('briefing.yml updated:', style)
PY
```

### 3. 시연 브리핑 — 1회 굴려 보기

봇 재시작 없이도 적용돼요 (`generate_briefing` 이 매 호출 reload).

텔레그램에서 `/today` 보내거나, *터미널에서 dry-run*:

```bash
~/.local/bin/uv run python - <<'PY'
from commands.briefing import generate_briefing
from pathlib import Path
persona = Path('persona/system_prompt.md').read_text(encoding='utf-8')
print(generate_briefing(persona))
PY
```

### 4. lock or 재조정

사용자에게 *마음에 드는지* 물어 보세요.
- 마음에 들면 → lock. 다음 단계 `/setup-briefing-schedule` (선택).
- 아니면 → Q1~Q3 다시 또는 페르소나 자체를 `/tune-persona` 로 조정.

### 5. 다음 단계 안내

"양식 OK 🐾  매일 자동으로 받고 싶으면 `/setup-briefing-schedule` 해 봐요. 지금은 `/today` 로만 받아도 OK."

## 금기

- 갱이가 답을 *대신 고르지 않기* — 3개 질문 모두 사용자 답이 와야 진행
- yml 의 *다른 섹션(schedule)* 손대지 않기 — 본 스킬은 style 만
- 페르소나 시스템 프롬프트 자체를 손대지 않기 (별도 `/tune-persona`)
