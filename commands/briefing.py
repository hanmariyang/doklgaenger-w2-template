"""도클갱어 W3 — 캘린더 아침 브리핑.

신경계 비유:
- iCal URL(혈관)이 오늘 일정(혈액)을 길어 올리고,
- 페르소나(뇌·시각 피질)가 그 일정을 *자기 톤*으로 그려서
- 텔레그램(목소리)으로 흘려 보내요.

설계 원칙 (Pendulum PD-010 차용·단순화):
- iCal URL 1줄만 받으면 셋업 끝. OAuth / Google Cloud Console 0건.
- 시간 윈도우 = *오늘 KST 자정 ~ 다음날 KST 자정*. (PD-010 의 -7d~+30d 보다 좁힘)
- RRULE 전개 — 매주 미팅·매일 운동 같은 반복 이벤트 그날치만 펼쳐 흡수.
- ExternalTask upsert·hard cap·is_company 차단 *전부 제거* (도클갱어는 학습용).
- 회사 캘린더 허용 + *주의 메시지*만 (의뢰자 결정 — PD-010 의 차단 패턴 X).

차용 출처 (Pendulum):
- `projects/pendulum/backend/core/services/ical_feed.py`
- `_fetch_ical`, `_to_aware`, `_component_to_dict`, `_expand_recurring` 의 *순수 함수 부분*
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from datetime import date, datetime, time, timedelta, timezone as dt_tz
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger("doklgaenger-w3-briefing")

# ─────────────────────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────────────────────

KST = ZoneInfo("Asia/Seoul")
HTTP_TIMEOUT = 20  # 초 — PD-010 정합
CLAUDE_MODEL = "sonnet"
CLAUDE_CLI_TIMEOUT = 90  # 초 — bot.py 정합


# ─────────────────────────────────────────────────────────────
# 시간 도구 — 오늘(KST) 윈도우
# ─────────────────────────────────────────────────────────────

def today_window_kst(now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    """오늘 KST 자정 ~ 다음날 KST 자정 (UTC aware 반환).

    now 가 주어지면 *그 시점 기준의 오늘*. 미주어지면 현재 시각.
    """
    now = now or datetime.now(KST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=KST)
    else:
        now = now.astimezone(KST)
    start_kst = datetime.combine(now.date(), time(0, 0), tzinfo=KST)
    end_kst = start_kst + timedelta(days=1)
    return start_kst.astimezone(dt_tz.utc), end_kst.astimezone(dt_tz.utc)


def _to_aware_utc(value) -> Optional[datetime]:
    """iCal dt(date/datetime, naive/aware) → aware UTC datetime.

    PD-010 `_to_aware` 정합. all-day 이벤트는 KST 자정 기준.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=dt_tz.utc)
        return value.astimezone(dt_tz.utc)
    if isinstance(value, date):
        return datetime.combine(value, time(0, 0), tzinfo=KST).astimezone(dt_tz.utc)
    return None


# ─────────────────────────────────────────────────────────────
# iCal fetch — 혈관
# ─────────────────────────────────────────────────────────────

def fetch_ical_bytes(url: str) -> bytes:
    """iCal feed 다운로드. 실패 시 b''.

    PD-010 `_fetch_ical` 정합 — User-Agent + timeout 20s.
    """
    if not url:
        return b""
    try:
        import requests
    except ImportError:
        logger.error("requests 미설치 — `uv sync` 또는 `pip install requests`")
        return b""
    try:
        resp = requests.get(
            url,
            timeout=HTTP_TIMEOUT,
            headers={"User-Agent": "Doklgaenger-W3/1.0"},
        )
        if resp.status_code != 200:
            logger.warning("ical http_%s for %s", resp.status_code, url[:60])
            return b""
        return resp.content
    except Exception as exc:  # noqa: BLE001 — 사용자 친화적 메시지가 필요한 자리
        logger.warning("ical fetch failed (%s): %s", url[:60], exc)
        return b""


# ─────────────────────────────────────────────────────────────
# iCal parse — VEVENT → dict
# ─────────────────────────────────────────────────────────────

def _component_to_dict(component) -> Optional[dict]:
    """VEVENT 1건 → dict. PD-010 `_component_to_dict` 단순화 (uid·source_id 자리 제거)."""
    dtstart = component.get("DTSTART")
    dtend = component.get("DTEND")
    start_at = _to_aware_utc(dtstart.dt if dtstart else None)
    end_at = _to_aware_utc(dtend.dt if dtend else None)
    if start_at is None:
        return None
    if end_at is None:
        end_at = start_at + timedelta(hours=1)

    summary = str(component.get("SUMMARY") or "").strip() or "(제목 없음)"
    location = str(component.get("LOCATION") or "").strip()
    description = str(component.get("DESCRIPTION") or "").strip()

    # all-day 판별 — dtstart 가 date(시간 없음)였으면 all-day
    is_all_day = bool(dtstart and not isinstance(dtstart.dt, datetime))

    return {
        "summary": summary[:300],
        "location": location[:200],
        "description": description[:500],
        "start_at": start_at,  # UTC aware
        "end_at": end_at,
        "is_all_day": is_all_day,
        "is_recurring_instance": False,
    }


def _expand_recurring(component, base: dict, window_start: datetime, window_end: datetime) -> list[dict]:
    """RRULE 펼침 — *오늘 윈도우 안*만 전개.

    PD-010 `_expand_recurring` 단순화 — cancelled_instances 등 고급 case 제거.
    """
    try:
        from dateutil.rrule import rrulestr
    except ImportError:
        logger.warning("dateutil 없음 — recurring 무시")
        return [base] if window_start <= base["start_at"] <= window_end else []

    rrule_str = component.get("RRULE").to_ical().decode()
    dtstart = base["start_at"]
    duration = base["end_at"] - base["start_at"]

    # EXDATE — 시리즈에서 *이 시각*은 제외 (휴가·취소된 회의)
    exdates: set[datetime] = set()
    exdate_raw = component.get("EXDATE")
    if exdate_raw is not None:
        exdate_list = exdate_raw if isinstance(exdate_raw, list) else [exdate_raw]
        for ex in exdate_list:
            if ex is None:
                continue
            for ex_dt in getattr(ex, "dts", []):
                exd = _to_aware_utc(ex_dt.dt)
                if exd:
                    exdates.add(exd)

    try:
        rule = rrulestr(rrule_str, dtstart=dtstart)
    except Exception as exc:  # noqa: BLE001
        logger.warning("rrule parse fail: %s", exc)
        return []

    out: list[dict] = []
    for occurrence in rule.between(window_start, window_end, inc=True):
        if occurrence.tzinfo is None:
            occurrence = occurrence.replace(tzinfo=dt_tz.utc)
        else:
            occurrence = occurrence.astimezone(dt_tz.utc)
        if occurrence in exdates:
            continue
        out.append(
            {
                **base,
                "start_at": occurrence,
                "end_at": occurrence + duration,
                "is_recurring_instance": True,
            }
        )
    return out


def extract_today_events(ical_bytes: bytes, now: Optional[datetime] = None) -> list[dict]:
    """iCal bytes → 오늘 KST 이벤트 list (시간 오름차순).

    PD-010 `_extract_events` 단순화 — cancelled_instances 1st pass 제거 (학습용 충분).
    """
    if not ical_bytes:
        return []
    try:
        from icalendar import Calendar
    except ImportError:
        logger.error("icalendar 미설치 — `uv sync` 또는 `pip install icalendar`")
        return []
    try:
        cal = Calendar.from_ical(ical_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ical parse failed: %s", exc)
        return []

    window_start, window_end = today_window_kst(now)
    out: list[dict] = []
    for component in cal.walk("VEVENT"):
        try:
            status = str(component.get("STATUS") or "").upper()
            if status == "CANCELLED":
                continue
            base = _component_to_dict(component)
            if base is None:
                continue
            if component.get("RRULE"):
                out.extend(_expand_recurring(component, base, window_start, window_end))
            else:
                if window_start <= base["start_at"] < window_end:
                    out.append(base)
        except Exception as exc:  # noqa: BLE001
            logger.warning("event skip: %s", exc)
            continue

    out.sort(key=lambda ev: ev["start_at"])
    return out


# ─────────────────────────────────────────────────────────────
# Public — fetch_today_events
# ─────────────────────────────────────────────────────────────

def fetch_today_events(ical_url: str, now: Optional[datetime] = None) -> list[dict]:
    """iCal URL → 오늘 KST 일정 list.

    이 함수가 W3 의 *입구*예요. bot.py 가 이걸 호출해서 그 결과를 페르소나에 paste.
    실패 시 빈 list — 사용자에게 친절한 메시지는 호출부에서 처리.
    """
    raw = fetch_ical_bytes(ical_url)
    return extract_today_events(raw, now=now)


# ─────────────────────────────────────────────────────────────
# 사용자에게 보일 텍스트 (plain) — *페르소나 paste 입력*용
# ─────────────────────────────────────────────────────────────

def format_events_plain(events: list[dict], now: Optional[datetime] = None) -> str:
    """이벤트 list → *plain text* (페르소나 paste 입력 용).

    페르소나가 자기 톤으로 다시 그릴 *재료*. 시간 KST 변환.
    빈 list 면 "오늘 일정 없음" 한 줄.
    """
    if not events:
        return "오늘 일정 없음."
    now = now or datetime.now(KST)
    today_kst = now.astimezone(KST).date()
    lines: list[str] = [f"== 오늘 일정 ({today_kst.isoformat()} KST) =="]
    for ev in events:
        start_kst = ev["start_at"].astimezone(KST)
        end_kst = ev["end_at"].astimezone(KST)
        if ev.get("is_all_day"):
            time_label = "종일"
        else:
            time_label = f"{start_kst.strftime('%H:%M')}~{end_kst.strftime('%H:%M')}"
        line = f"- {time_label} · {ev['summary']}"
        if ev.get("location"):
            line += f" @ {ev['location']}"
        lines.append(line)
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# 설정 로드 — config/briefing.yml
# ─────────────────────────────────────────────────────────────

DEFAULT_STYLE = {
    "format": "list-with-comments",  # list-with-comments | one-liner | detailed
    "length": "medium",                # short | medium | long
    "show_empty": True,
}

DEFAULT_SCHEDULE = {
    "enabled": False,
    "time": "08:00",
    "chat_id": 0,
}


def load_briefing_config(path: Optional[Path] = None) -> dict:
    """`config/briefing.yml` 읽어 dict 반환. 없거나 깨졌으면 기본값.

    Skills(`/setup-briefing-style`, `/setup-briefing-schedule`) 이 사용자 대화로 채움.
    """
    if path is None:
        path = Path(__file__).resolve().parent.parent / "config" / "briefing.yml"
    if not path.exists():
        return {"style": dict(DEFAULT_STYLE), "schedule": dict(DEFAULT_SCHEDULE)}
    try:
        import yaml
    except ImportError:
        logger.warning("pyyaml 미설치 — 기본값 사용")
        return {"style": dict(DEFAULT_STYLE), "schedule": dict(DEFAULT_SCHEDULE)}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("briefing.yml parse fail: %s", exc)
        return {"style": dict(DEFAULT_STYLE), "schedule": dict(DEFAULT_SCHEDULE)}
    style = {**DEFAULT_STYLE, **(data.get("style") or {})}
    schedule = {**DEFAULT_SCHEDULE, **(data.get("schedule") or {})}
    return {"style": style, "schedule": schedule}


# ─────────────────────────────────────────────────────────────
# 페르소나 브리핑 생성 — Claude Code CLI 호출
# ─────────────────────────────────────────────────────────────

BRIEFING_STYLE_HINTS = {
    "format": {
        "list-with-comments": "시간순 리스트 + 각 항목마다 페르소나의 한 줄 코멘트",
        "one-liner": "오늘 핵심을 한 줄로 압축 + 페르소나의 한 줄 코멘트",
        "detailed": "각 일정마다 시간·장소·페르소나의 코멘트를 짧은 단락으로",
    },
    "length": {
        "short": "총 3줄 내외",
        "medium": "각 일정마다 1줄 + 마무리 1줄",
        "long": "각 일정에 대한 페르소나의 짧은 생각까지 포함",
    },
}


def build_briefing_system_prompt(persona_prompt: str, style: dict) -> str:
    """페르소나 시스템 프롬프트 + 브리핑 스타일 지침 합성.

    페르소나 톤은 그대로 두고, *오늘 일정을 어떻게 그릴지*만 덧붙여요.
    """
    fmt = style.get("format", DEFAULT_STYLE["format"])
    length = style.get("length", DEFAULT_STYLE["length"])
    show_empty = style.get("show_empty", DEFAULT_STYLE["show_empty"])

    fmt_hint = BRIEFING_STYLE_HINTS["format"].get(fmt, BRIEFING_STYLE_HINTS["format"]["list-with-comments"])
    length_hint = BRIEFING_STYLE_HINTS["length"].get(length, BRIEFING_STYLE_HINTS["length"]["medium"])

    empty_line = (
        "일정이 비어 있어도 빈 하루를 페르소나 톤으로 격려해 주세요."
        if show_empty else
        "일정이 비어 있으면 짧게 한 줄로 마무리."
    )

    addendum = (
        "\n\n---\n\n"
        "## 오늘 일정 브리핑 지침\n\n"
        "사용자가 아래 형식의 *오늘 일정 raw text*를 보낼 거예요.\n"
        "당신은 페르소나의 톤을 *그대로* 유지하면서 이 일정을 그려 주세요.\n\n"
        f"- 형식: {fmt_hint}\n"
        f"- 길이: {length_hint}\n"
        f"- 빈 하루: {empty_line}\n"
        "- 일정 시간·제목·장소는 *변경하지 마세요* (재확인용).\n"
        "- 일정에 *없는 사실*을 만들지 마세요.\n"
        "- 페르소나의 인사·자기 호칭은 평소대로.\n"
    )
    return (persona_prompt.strip() + addendum).strip()


def build_briefing(
    events: list[dict],
    persona_prompt: str,
    style: Optional[dict] = None,
    now: Optional[datetime] = None,
) -> str:
    """이벤트 list + 페르소나 + 스타일 → 페르소나 톤 브리핑 텍스트.

    Claude Code CLI 서브프로세스로 호출. bot.py 의 `call_claude_code` 정합 패턴.
    실패 시 plain fallback (페르소나 0 — 일정 raw 만 반환).
    """
    style = style or DEFAULT_STYLE
    plain = format_events_plain(events, now=now)
    system_prompt = build_briefing_system_prompt(persona_prompt, style)

    if shutil.which("claude") is None:
        logger.warning("claude CLI not found — fallback to plain")
        return plain

    cmd = [
        "claude", "-p",
        "--system-prompt", system_prompt,
        "--no-session-persistence",
        "--permission-mode", "bypassPermissions",
        "--model", CLAUDE_MODEL,
    ]
    try:
        result = subprocess.run(
            cmd,
            input=plain,
            capture_output=True,
            text=True,
            timeout=CLAUDE_CLI_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        logger.warning("claude timeout — fallback to plain")
        return plain
    except FileNotFoundError:
        return plain

    if result.returncode != 0:
        logger.warning("claude exit=%s stderr=%s", result.returncode, (result.stderr or "")[:200])
        return plain
    output = (result.stdout or "").strip()
    return output or plain


# ─────────────────────────────────────────────────────────────
# 진입점 — 텔레그램에서 한 번에 호출하는 자리
# ─────────────────────────────────────────────────────────────

def generate_briefing(
    persona_prompt: str,
    ical_url: Optional[str] = None,
    config: Optional[dict] = None,
    now: Optional[datetime] = None,
) -> str:
    """`/today` 명령·자연어 트리거·자동 푸시가 한 번에 호출하는 *공통 입구*.

    Args:
        persona_prompt: 페르소나 시스템 프롬프트 (bot.py 에서 보유).
        ical_url: iCal URL. None 이면 환경변수 `ICAL_URL` 사용.
        config: load_briefing_config() 결과. None 이면 즉시 로드.
        now: 테스트용 시각 주입.

    Returns:
        텔레그램에 흘려 보낼 브리핑 텍스트 (Markdown 가능).
    """
    if ical_url is None:
        ical_url = os.getenv("ICAL_URL") or ""
    if not ical_url:
        return (
            "갱이가 iCal URL 을 못 찾았어요... 🐾\n"
            "→ `/setup-ical` 스킬로 먼저 셋업해 주세요.\n"
            "  Google Calendar 설정 → 통합 → 비공개 iCal URL 복사."
        )
    config = config or load_briefing_config()
    style = config.get("style") or DEFAULT_STYLE
    events = fetch_today_events(ical_url, now=now)
    return build_briefing(events, persona_prompt, style=style, now=now)
