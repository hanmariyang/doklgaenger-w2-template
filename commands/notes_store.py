"""도클갱어 W5 자유 실습 — 회의록 DB 저장 훅 (seam).

지금까지 봇은 *무상태*였어요 (`--no-session-persistence` — 대화 이력 저장 0).
이 파일이 봇에 처음 붙는 '저장 계층' 이에요. 자유 실습이니, 천천히 본인 손으로.

동작 방식:
- `config/meeting_notes.yml` 의 `store.enabled: true` 일 때,
- `bot.py` 의 `_send_meeting_notes` 가 회의록 생성 직후 이 `save_meeting_notes` 를 부릅니다.
- 기본은 *미구현* (NotImplementedError) — 켜도 회의록 발송엔 영향 0, 저장만 skip + 로그 안내.

가이드 (설계 질문 + 힌트): Claude Code 안에서  /save-notes-db
"""

from __future__ import annotations


def save_meeting_notes(record: dict) -> bool:
    """생성된 회의록 한 건을 *본인 DB* 에 저장. 성공하면 True 반환.

    record 예시 (원하는 대로 바꿔도 돼요 — 무엇을 저장할지는 본인 설계):
        {
          "created_at": "2026-06-18T14:02:00+09:00",   # 생성 시각 (ISO)
          "chat_id":    123456789,                       # 보낸 텔레그램 chat
          "raw_text":   "...붙여 넣은 원본 메모...",
          "notes":      "## 한 줄 요약\\n...정리된 회의록...",
        }

    ── 자유 실습 ──────────────────────────────────────────────
    아래 `raise NotImplementedError` 를 지우고 본인 DB 저장 코드를 넣으세요.
    어떤 DB든 OK. 힌트 세 갈래 (택1, 또는 본인 방식):

    # (A) 로컬 SQLite — 설치 0, 파이썬 stdlib. 처음이면 여기부터.
    #   import sqlite3
    #   con = sqlite3.connect("meeting_notes.db")
    #   con.execute(
    #       "CREATE TABLE IF NOT EXISTS notes("
    #       "id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, "
    #       "chat_id INTEGER, raw_text TEXT, notes TEXT)")
    #   con.execute(
    #       "INSERT INTO notes(created_at, chat_id, raw_text, notes) VALUES(?,?,?,?)",
    #       (record["created_at"], record["chat_id"], record["raw_text"], record["notes"]))
    #   con.commit(); con.close()
    #   return True

    # (B) 본인 Postgres/MySQL — 회사·개인 프로젝트에 이미 쓰는 DB 로.
    #   conn 문자열은 *반드시 .env* 로 (코드에 박지 말기). INSERT 한 줄.
    #   psycopg 등 드라이버는 pyproject 에 의존성 추가 필요.

    # (C) Notion 을 DB 로 — 검색·공유 편한 노션 DB row 생성.
    #   토큰은 .env. (워크스페이스에 NOTION_API_TOKEN 자산이 이미 있어요.)

    먼저 풀어 볼 설계 질문은 /save-notes-db 가 같이 풀어 줘요.
    ⚠️ 회의 본문이 DB 에 남아요 — 로컬 보관 · .gitignore · 민감 회의 주의.
    """
    raise NotImplementedError(
        "자유 실습: commands/notes_store.py 의 save_meeting_notes 를 본인 DB 로 채워 보세요. "
        "가이드는 Claude Code 안에서 /save-notes-db 🐾"
    )
