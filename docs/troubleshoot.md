# 자주 막히는 부분 — 트러블슈팅

> 갱이가 W2 동안 자주 봤던 막힘들이에요. 차례로 확인해 보세요 🐾

---

## 1. `/bot start` 했는데 봇이 답을 안 해요

### 1-1. 우선 `/diagnose` 부터

Claude Code 에서 `/diagnose` 호출 → 6가지 자동 체크.

### 1-2. 로그 직접 보기

```bash
tail -n 50 /tmp/doppel-bot.log
```

자주 나오는 에러:

| 로그 메시지 | 원인 | 해결 |
|------------|------|------|
| `Unauthorized` | 토큰 틀림 | `.env` 의 `TELEGRAM_BOT_TOKEN` 다시 확인. BotFather `/mybots` 에서 토큰 재확인 |
| `Conflict: terminated by other getUpdates` | 같은 토큰으로 봇이 *어딘가에서* 또 떠 있음 | 다른 인스턴스를 끄거나, BotFather `/revoke` 로 토큰 새로 발급 |
| `429 Too Many Requests` | rate limit | 1~2분 기다린 후 재시도 |
| `529 Overloaded` (Claude) | Anthropic 측 일시 과부하 | 몇 분 후 재시도, 또는 모델을 잠시 `claude-haiku-*` 로 다운 |
| `FileNotFoundError: ...system_prompt.md` | 페르소나 프롬프트 없음 | `/research-persona` 로 작성 |

---

## 2. `getMe` 호출이 응답이 없어요

```bash
curl -v "https://api.telegram.org/bot<TOKEN>/getMe"
```

- `Could not resolve host`: DNS / 네트워크
- 타임아웃: 방화벽·VPN·프록시
- `404 Not Found`: URL 또는 토큰 오타

## 3. `python-telegram-bot` 임포트 에러

```
ImportError: cannot import name 'ApplicationBuilder' from 'telegram.ext'
```

→ 버전이 v22 미만이에요.

```bash
pip install --upgrade "python-telegram-bot>=22"
# 또는
uv pip install --upgrade "python-telegram-bot>=22"
```

## 4. Anthropic SDK 모델 이름 에러

```
NotFoundError: model not found: claude-sonnet-4-6
```

→ Anthropic 콘솔에서 *모델 액세스 권한*이 활성화되어 있는지 확인. 또는 `bot.py` 의 `CLAUDE_MODEL` 을 본인 계정에서 *접근 가능한 모델*로 변경.

## 5. `.env` 가 git 에 들어갔어요

이건 *민감*해요. 갱이가 잡아 드릴게요:

```bash
# 1. 즉시 토큰 회전
#   - BotFather /revoke
#   - Anthropic 콘솔에서 API key revoke

# 2. git history 에서 제거
git rm --cached .env
git commit -m "fix: drop .env from tracking"

# 3. (이미 push 됐으면) git filter-repo 또는 BFG 로 history 정리 필요
#    → 그건 W2 범위 밖이라 갱이가 사용자에게 안내만 드려요
```

## 6. macOS 에서 `nohup`/`ps` 가 이상해요

zsh + 외부 인터프리터(예: pyenv) 에서 가끔 PID 가 빨리 죽어요.

```bash
./scripts/start.sh
sleep 2
cat .bot.pid
ps -p $(cat .bot.pid)
```

PID 가 즉시 사라지면 → `tail -n 50 /tmp/doppel-bot.log` 로 부팅 단계 에러 확인.

## 7. 텔레그램에서 답이 *너무 길어요*

페르소나 시스템 프롬프트의 **응답 스타일** 섹션에 다음 한 줄을 추가:

```
- 응답은 항상 3~5문장 이내로 마무리. 추가 설명을 묻지 않는다.
```

→ `/bot stop && /bot start` 으로 재시작.

## 8. 페르소나가 깨졌어요 (다른 캐릭터로 답함)

`/tune-persona` 호출 → 1~2줄만 수정 → 재시작.

큰 수정은 정체성이 흔들리니 작게 잡아 가는 게 좋아요 🐾
