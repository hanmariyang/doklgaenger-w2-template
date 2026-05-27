# 도클갱어 W3 — Skills 4종 (TF-958)

이 폴더의 4개 md 파일은 **W3 Skill 정의**예요. clone 받은 직후에는 자동으로 활성화되지 않으니, 한 번에 `.claude/skills/` 로 복사해 주세요 🐾

## 설치 (1회)

```bash
./scripts/install-w3-skills.sh
```

또는 수동으로:

```bash
cp skills-w3/*.md .claude/skills/
```

복사 후 Claude Code 가 자동으로 `/welcome-w3`, `/setup-ical`, `/setup-briefing-style`, `/setup-briefing-schedule` 4개 명령을 인식해요.

## 왜 이렇게 했어요?

W3 패치 작성 시점의 작업 환경 sandbox 가 `.claude/skills/` 직접 쓰기를 차단했어요. 사용자가 clone 받은 환경에서는 그 제약이 없으니 install script 1줄로 처리해요. (W2 에서는 처음부터 `.claude/skills/` 에 박혀 있어요 — W3 패치만 이렇게 우회.)

## 파일 4종

| 파일 | 명령 | 용도 |
|------|------|------|
| `welcome-w3.md` | `/welcome-w3` | W3 첫 인사 + 8단계 흐름 + 환경 점검 |
| `setup-ical.md` | `/setup-ical` | Google iCal URL 받고 .env 채우기 + 주의 메시지 |
| `setup-briefing-style.md` | `/setup-briefing-style` | 양식·페르소나 톤 사용자 대화로 결정 |
| `setup-briefing-schedule.md` | `/setup-briefing-schedule` | 자동 푸시 시간 사용자 대화로 결정 |
