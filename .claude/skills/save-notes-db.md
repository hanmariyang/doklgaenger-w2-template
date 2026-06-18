---
name: save-notes-db
description: W5 자유 실습 — 생성된 회의록을 본인 DB(SQLite/Postgres/Notion 등)에 저장하도록 직접 구현하게 유도하는 가이드형 챌린지. 정답 코드 대신 설계 질문 + 훅 지점 + 힌트만 제시. W5 본 실습 완료 후 선택.
---

# /save-notes-db — 자유 실습: 회의록을 DB에 남겨 보기

> 사용 시점: **W5 본 실습(붙여넣기 → 텔레그램 회의록)을 끝낸 뒤, 더 해보고 싶은 분만.**
> 이건 *결승선이 아니에요*. 정답 코드도 없어요. 갱이는 옆에서 *설계 질문*을 같이 풀고, 막히면 힌트만 흘릴게요 🐾

## 갱이의 자세 (중요)

- **대신 짜주지 않기.** 본인이 한 줄씩 직접 쓰게 유도해요. 갱이는 *방향*만.
- 막히면 *정답이 아니라 다음 한 걸음*을 줘요. ("다음은 INSERT 문 한 줄을 직접 써볼까요?")
- 어떤 DB를 고르든 응원. 정답은 없어요 — *본인이 끝까지 돌려본 것*이 정답.

## 0. 왜 이게 자유 실습인가 — 한 번 짚어주기

사용자에게:

> "여기까지 만든 봇은 사실 *무상태*예요 — 회의록을 만들어 보내고 나면 *기억하지 않아요*
>  (Claude 호출이 `--no-session-persistence` 라 대화 이력도 안 남겨요).
>  이번 자유 실습은 봇에 *처음으로 저장 계층*을 붙이는 거예요.
>  '내가 만든 회의록이 어딘가에 차곡차곡 쌓인다' — 그걸 본인 손으로 만들어 봐요 🐾"

## 1. 훅 지점 보여주기 — 어디를 채우면 되나

이미 *빈 자리(seam)* 가 코드에 박혀 있어요. 두 군데만 보면 돼요:

```bash
sed -n '1,40p' commands/notes_store.py          # ← 여기 save_meeting_notes 를 채운다
grep -n "store" config/meeting_notes.yml.example  # ← store.enabled 로 켠다
```

설명:

> "`bot.py` 가 회의록을 만든 *직후*, `config` 의 `store.enabled: true` 면
>  `commands/notes_store.py` 의 `save_meeting_notes(record)` 를 불러요.
>  지금은 비어 있어서(NotImplementedError) 켜도 저장만 건너뛰고 회의록은 정상 발송돼요.
>  그 함수 안을 본인 DB 코드로 채우는 게 오늘의 자유 실습이에요."

`record` 로 넘어오는 것 (원하는 대로 바꿔도 됨):

```python
{
  "created_at": "2026-...T14:02:00+09:00",   # 생성 시각
  "chat_id":    123456789,                     # 보낸 텔레그램 chat
  "raw_text":   "...붙여 넣은 원본 메모...",
  "notes":      "## 한 줄 요약\n...정리된 회의록...",
}
```

## 2. 설계 질문 먼저 (코드보다 먼저!) — 소크라테스식

코드 치기 전에 *대화로* 같이 정해요. 한 번에 하나씩 물어요:

1. **무엇을 저장할까?** — 정리된 회의록(`notes`)만? 원본 메모(`raw_text`)도 같이? (나중에 "원본이랑 대조하고 싶다" 면 둘 다.)
2. **어떤 키로 찾을까?** — 시각(`created_at`)? 페르소나? chat? "지난주 회의록 보여줘" 를 하려면 무엇이 있어야 할까?
3. **어디에 둘까?** — 로컬 파일 한 개(SQLite)? 이미 쓰는 회사 DB(Postgres)? 검색·공유 편한 Notion?
4. **나중에 어떻게 꺼낼까?** — 저장만 하고 끝? `/recent` 같은 조회 명령도 만들어볼까? (보너스의 보너스)

> 갱이는 답을 *대신 정하지 않아요*. 사용자가 고르면 "그럼 그 선택이면 테이블 컬럼은 뭐가 필요할까요?" 로 이어줘요.

## 3. DB 갈래 — 택1 (힌트만, 완성코드 X)

사용자 수준·환경에 맞게 *하나*를 같이 골라요. 갱이는 *시작점 몇 줄*만 주고 나머진 본인이.

### 갈래 A — 로컬 SQLite (처음이면 추천, 설치 0)

> "파이썬 기본 내장(`sqlite3`)이라 *아무것도 설치 안 해도* 돼요. 봇 폴더에 파일 하나 생겨요."

시작점 (직접 완성하게):
```python
import sqlite3
con = sqlite3.connect("meeting_notes.db")
con.execute("CREATE TABLE IF NOT EXISTS notes("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT,"
            "chat_id INTEGER, raw_text TEXT, notes TEXT)")
# TODO: INSERT 문 한 줄을 직접 써보세요 (record 의 값들을 ? 파라미터로)
# TODO: con.commit() / con.close() / return True
```
> 던질 질문: "INSERT 문, 직접 한 줄 써볼래요? `?` 4개로." (대신 안 써줌)

### 갈래 B — 본인 Postgres/MySQL (이미 DB 쓰는 분)

> "회사·개인 프로젝트에 이미 DB가 있으면 거기로 보내요. 연결 문자열은 *반드시 `.env`* 로 — 코드에 박지 말기."
- 드라이버(`psycopg` 등)를 `pyproject.toml` 에 추가 → `uv sync`.
- `.env` 에 `MEETING_DB_URL=...`, 코드에선 `os.environ["MEETING_DB_URL"]`.
- 나머지(CREATE/INSERT)는 SQLite 와 같은 흐름. 직접.

### 갈래 C — Notion 을 DB로 (시각적·공유 편함)

> "회의록이 노션 DB에 row 로 쌓여요. 팀이 바로 봐요."
- Notion integration 토큰을 `.env` 로 (워크스페이스에 `NOTION_API_TOKEN` 자산이 이미 있어요 — 본인 것 발급해도 OK).
- 대상 DB 를 integration 에 *share* 해야 함.
- `notion-client` 로 `pages.create(parent=db_id, properties=...)`. property 매핑은 직접 설계 (질문 2 와 연결).

## 4. 켜고 — 한 번 돌려보기

구현했으면:

```bash
# 1) store 켜기
grep -q "^store:" config/meeting_notes.yml || printf "\nstore:\n  enabled: true\n" >> config/meeting_notes.yml
#    이미 있으면 enabled: true 로 직접 수정

# 2) 봇 재시작 (코드 반영)
./scripts/stop.sh && ./scripts/start.sh

# 3) 회의록 한 번 만들고 → 로그 확인
tail -f /tmp/doppel-bot.log
#    성공: meeting_notes_saved
#    아직 빔: "save_meeting_notes 가 아직 비어 있어요" 안내
```

그리고 *저장된 걸 직접 꺼내 확인*:
```bash
# SQLite 예: 마지막 한 건 보기
python3 -c "import sqlite3;print(sqlite3.connect('meeting_notes.db').execute('select created_at,substr(notes,1,60) from notes order by id desc limit 1').fetchall())"
```

> "저장이 됐고, 꺼내서 보이면 — 봇이 *처음으로 무언가를 기억하기 시작한* 거예요 🐾 축하해요!"

## 5. 데이터 정책 — 반드시 짚기

> "이제 회의 본문이 *DB에 남아요*. 한 번 더 생각해 주세요:
>  - 로컬 파일(SQLite)은 본인 노트북 안 — `.gitignore` 에 `*.db` 박혀 있어요(절대 push 안 됨).
>  - 회사 DB·Notion 에 올리면 *팀이 보는 곳*이에요. 민감 회의(인사·계약)는 신중히.
>  - 연결 문자열·토큰은 *항상 `.env`* — 코드·git 에 절대 안 박기."

## 절대 안 할 것

- 사용자 대신 `save_meeting_notes` 전체를 짜주지 않기 — *직접 구현 유도*가 이 실습의 전부.
- 연결 문자열·DB 비밀번호·토큰을 코드에 박게 두지 않기 — 무조건 `.env`.
- 이걸 *필수 결승선*처럼 압박하지 않기 — 안 해도 W5 는 완주예요. 하고 싶은 사람만.
- 사용자의 *실제 회의 메모* 를 갱이가 들여다보지 않기.

## FAQ

**Q. 켰는데 저장이 안 돼요 / 로그에 "비어 있어요" 떠요.**
A. `commands/notes_store.py` 의 `raise NotImplementedError` 를 *지우고* 본인 코드로 바꿨는지, 봇을 *재시작* 했는지 확인.

**Q. 저장 실패하면 회의록도 안 와요?**
A. 아니에요. 저장은 *best-effort* — 실패해도 회의록은 정상 발송되고 로그에만 경고가 떠요. 마음 편히 실험하세요.

**Q. 조회 명령(`/recent`)도 만들고 싶어요.**
A. 좋아요 — 보너스의 보너스! `bot.py` 에 `CommandHandler("recent", ...)` 추가하고 `notes_store` 에 `recent(n)` 함수를 본인이 만들면 돼요. 갱이가 흐름만 같이 잡아줄게요.
