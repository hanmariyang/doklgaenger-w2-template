#!/usr/bin/env bash
# 도클갱어 W3 — Skills 4종을 `.claude/skills/` 로 복사 (TF-958).
# clone 받은 직후 1회 실행. 두 번째 실행 시에는 기존 파일을 덮어써요.
#
# 왜 이렇게 했는지: 본 repo 의 W3 패치 작성 시점의 작업 환경이 `.claude/skills/`
# 직접 쓰기를 차단했어서, `skills-w3/` 로 박아 두고 install script 로 옮겨요.
# 사용자 환경(개인 노트북)에서는 그런 제약이 없습니다.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d "skills-w3" ]; then
  echo "갱이가 skills-w3/ 폴더를 못 찾았어요... 🐾  repo 루트에서 실행해 주세요."
  exit 1
fi

mkdir -p .claude/skills

count=0
for f in skills-w3/*.md; do
  base=$(basename "$f")
  if [ "$base" = "README.md" ]; then
    continue
  fi
  cp "$f" ".claude/skills/$base"
  echo "  → .claude/skills/$base"
  count=$((count + 1))
done

echo ""
echo "W3 Skills $count 개 설치 완료 🐾"
echo "Claude Code 안에서 다음 명령을 사용할 수 있어요:"
echo "  /welcome-w3            — W3 첫 인사 + 8단계 안내"
echo "  /setup-ical            — Google iCal URL 받고 .env 채우기"
echo "  /setup-briefing-style  — 양식·페르소나 톤 대화로 결정"
echo "  /setup-briefing-schedule  — 자동 푸시 시간 대화로 결정"
