#!/usr/bin/env python3
"""
parser_utils.py — 파서 공통 헬퍼 + 스키마 v2 정규화.

스키마 v2 규칙:
  - schema_version: 2 명시
  - 시간은 항상 24시간제 HH:MM (zero-pad). "1:30"(오후) → "13:30"
  - 날짜는 ISO 8601 (YYYY-MM-DD). "5/19/2026" → "2026-05-19"
  - conference.timezone: IANA 시간대 (예: "Asia/Seoul") — 선택
  - session.type: "oral" | "poster" | "keynote" | "social" | "break" (기본 oral)
  - venue.walk: 발표장 간 도보시간 데이터 (선택; index.html walkMinutes가 소비)

모든 파서는 출력 직전에 finalize_v2(doc, ...)를 호출해 위 규칙을 보장한다.
마이그레이션(migrate_v2.py)도 같은 함수를 사용한다.
"""
import re

SCHEMA_VERSION = 2

TIME_RE = re.compile(r'^(\d{1,2}):(\d{2})$')
TIME_RANGE_RE = re.compile(r'^(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})$')
ISO_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
MDY_DATE_RE = re.compile(r'^(\d{1,2})/(\d{1,2})/(\d{4})$')


def to_24h(t, pm_threshold=0):
    """시간 문자열을 24시간제 HH:MM으로 정규화.

    pm_threshold > 0 이면 h < pm_threshold 를 오후로 간주해 +12.
    (IAQVEC류 PDF는 AM/PM 표기 없이 "1:30"=오후 1:30을 쓴다 → threshold 8)
    이미 24시간제인 소스(SAREK)는 threshold 0으로 zero-pad만 수행.
    """
    if not t:
        return t
    m = TIME_RE.match(t.strip())
    if not m:
        return t  # 시간 형식이 아니면 건드리지 않음
    h, mm = int(m.group(1)), m.group(2)
    if pm_threshold and h < pm_threshold:
        h += 12
    return f"{h:02d}:{mm}"


def normalize_time_range(t, pm_threshold=0):
    """"3:30-3:50" 같은 시간 범위 문자열을 24시간제로 정규화."""
    if not t:
        return t
    m = TIME_RANGE_RE.match(str(t).strip())
    if not m:
        return t
    return f"{to_24h(m.group(1), pm_threshold)}-{to_24h(m.group(2), pm_threshold)}"


def to_iso_date(d):
    """날짜를 ISO 8601(YYYY-MM-DD)로 정규화. "5/19/2026" → "2026-05-19"."""
    if not d:
        return d
    d = str(d).strip()
    if ISO_DATE_RE.match(d):
        return d
    m = MDY_DATE_RE.match(d)
    if m:
        mo, day, y = int(m.group(1)), int(m.group(2)), m.group(3)
        return f"{y}-{mo:02d}-{day:02d}"
    return d  # 인식 못 하는 형식은 보존


def finalize_v2(doc, timezone=None, pm_threshold=0, venue=None):
    """파싱 결과 dict를 스키마 v2로 정규화 (in-place + return).

    - schema_version 스탬프
    - sessions: date→ISO, start/end→24h, type 기본값 "oral"
    - papers: start/end→24h, paper_no가 시간 범위면 그것도 24h
    - timezone/venue 인자가 주어지면 기록 (기존 값은 덮지 않음)
    """
    doc['schema_version'] = SCHEMA_VERSION

    conf = doc.setdefault('conference', {})
    if timezone and not conf.get('timezone'):
        conf['timezone'] = timezone
    if venue and not doc.get('venue'):
        doc['venue'] = venue

    for s in doc.get('sessions', []):
        s['date'] = to_iso_date(s.get('date'))
        s['start'] = to_24h(s.get('start'), pm_threshold)
        s['end'] = to_24h(s.get('end'), pm_threshold)
        s.setdefault('type', 'oral')

    for p in doc.get('papers', []):
        if p.get('start'):
            p['start'] = to_24h(p['start'], pm_threshold)
        if p.get('end'):
            p['end'] = to_24h(p['end'], pm_threshold)
        # 특별세션은 paper_no 자리에 "3:30-3:50" 같은 시간 범위가 들어감
        pno = p.get('paper_no')
        if pno and TIME_RANGE_RE.match(str(pno)):
            p['paper_no'] = normalize_time_range(pno, pm_threshold)

    return doc


def validate_v2(doc):
    """v2 문서 검증. 문제 목록(list[str]) 반환 — 비어 있으면 통과."""
    problems = []
    if doc.get('schema_version') != SCHEMA_VERSION:
        problems.append(f"schema_version != {SCHEMA_VERSION}")

    time_ok = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')

    for s in doc.get('sessions', []):
        sid = s.get('id', '?')
        if s.get('date') and not ISO_DATE_RE.match(str(s['date'])):
            problems.append(f"session {sid}: date not ISO: {s['date']}")
        for k in ('start', 'end'):
            v = s.get(k)
            if v and not time_ok.match(v):
                problems.append(f"session {sid}: {k} not 24h HH:MM: {v}")

    for p in doc.get('papers', []):
        pid = p.get('paper_no', '?')
        for k in ('start', 'end'):
            v = p.get(k)
            if v and not time_ok.match(v):
                problems.append(f"paper {pid}: {k} not 24h HH:MM: {v}")
        pno = str(p.get('paper_no', ''))
        m = TIME_RANGE_RE.match(pno)
        if m and not (time_ok.match(m.group(1)) and time_ok.match(m.group(2))):
            problems.append(f"paper time-range not 24h: {pno}")

    return problems


def slugify(s):
    """소문자·ASCII 영숫자·하이픈만. 학회 id 생성용."""
    s = re.sub(r'[^A-Za-z0-9]+', '-', s).strip('-').lower()
    return s or 'conference'
