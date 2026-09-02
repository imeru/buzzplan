#!/usr/bin/env python3
"""
parser_roomvent.py — RoomVent(ConfTool 인쇄용 프로그램) PDF 파서.

지원 형식:
  - 세로 A4, 1단. 한 페이지에 세션 하나가 원칙이지만 세션이 페이지를 넘어
    이어지기도 한다 (발표 제목과 저자가 페이지 경계에서 갈라지는 경우 포함).
  - 레이아웃 좌표가 아니라 **글꼴 크기·굵기**로 역할을 구분한다:
        8.0  bold    섹션 배너 (PLENARY SESSIONS / PARALLEL SESSIONS /
                     WORKSHOPS / TECHNICAL TOURS)  → 세션 type 판정에 사용
        8.0  regular 러닝 헤더 ("RoomVent 2026 | Printed Program")  → 버림
        15.0 bold    세션 헤더 ("S11: Performance measurement and verification")
        10.6 italic  세션 메타 ("Wed 16/9/26, 10:00am - 11:45am, Location: Room
                     C 215, Session Chair: ...")
        9.5  bold    발표 시간 마커 ("Wed 16/9/26 C215 10:00am - 10:15am")
        11.0 bold    발표 제목
        10.0 regular 저자명 (윗첨자 소속번호 포함)
        10.0 italic  소속·이메일
        11.0 regular 페이지 번호 → 버림

관례 (CLAUDE.md 6장 Tier 1 산출물 규칙):
  - 발표 번호가 없는 프로그램이므로 paper_no는 "<세션ID>-<순번>" (예: S11-3).
    발표 시간은 start/end 필드에 명시하므로 index.html이 그대로 사용한다.
  - 발표가 0편인 세션(위원회 회의, 기술투어)은 type을 social로 둔다.
    oral로 두면 build.py가 "파싱 누락 가능성"으로 경고한다.
  - 단일 건물 학회이므로 building은 전 세션 동일(--building, 기본 "CTU"),
    구분은 room으로만 한다 (하드 룰 3).

사용 예:
    python3 build.py roomvent2026_printedprogram.pdf --parser parser_roomvent.py \
      --id roomvent-2026 --name "RoomVent 2026" --timezone Europe/Prague
"""
import argparse
import json
import pathlib
import re
import sys

from parser_utils import finalize_v2, group_rows

try:
    import pdfplumber
except ImportError:
    sys.exit("pdfplumber이 필요합니다: pip install pdfplumber")

ROW_TOL = 2.5

BANNER_TYPE = {
    'PLENARY SESSIONS':  'keynote',
    'PARALLEL SESSIONS': 'oral',
    'WORKSHOPS':         'oral',
    'TECHNICAL TOURS':   'social',
}

# "Wed 16/9/26 C215 10:00am - 10:15am"
MARKER_RE = re.compile(
    r'^\w{3}\s+(\d{1,2})/(\d{1,2})/(\d{2})\s+(\S+)\s+'
    r'(\d{1,2}:\d{2}\s*[ap]m)\s*-\s*(\d{1,2}:\d{2}\s*[ap]m)$', re.I)
# "Wed 16/9/26, 10:00am - 11:45am, Location: Room C 215, Session Chair: A, Session Chair: B"
META_DATE_RE  = re.compile(r'^\w{3}\s+(\d{1,2})/(\d{1,2})/(\d{2})')
META_TIME_RE  = re.compile(r'(\d{1,2}:\d{2}\s*[ap]m)\s*-\s*(\d{1,2}:\d{2}\s*[ap]m)', re.I)
META_ONE_RE   = re.compile(r',\s*(\d{1,2}:\d{2}\s*[ap]m)\s*(?:,|$)', re.I)
META_LOC_RE   = re.compile(r'Location:\s*(.*?)(?:,\s*Session Chair:|$)', re.I)
CHAIR_SPLIT_RE = re.compile(r'Session Chair:', re.I)
HEADER_RE     = re.compile(r'^([A-Z]{1,2}\d{1,2}):\s*(.+)$', re.S)
SUPERSCRIPT_RE = re.compile(r'(?<=[^\W\d_])\d+(?:\s*,\s*\d+)*(?=\s|,|$)')


def to24(t):
    """'4:00pm' → '16:00'."""
    m = re.match(r'^(\d{1,2}):(\d{2})\s*([ap])m$', t.strip(), re.I)
    if not m:
        return t.strip()
    h, mm, ap = int(m.group(1)), m.group(2), m.group(3).lower()
    if ap == 'p' and h != 12:
        h += 12
    if ap == 'a' and h == 12:
        h = 0
    return f"{h:02d}:{mm}"


def to_iso(d, mo, yy):
    return f"20{int(yy):02d}-{int(mo):02d}-{int(d):02d}"


def join_words(words):
    """단어 리스트를 사람이 읽는 한 줄로. 구두점 앞 공백을 정리한다."""
    s = ' '.join(w['text'] for w in words)
    s = re.sub(r'\s+([,;:.])', r'\1', s)
    return re.sub(r'\s{2,}', ' ', s).strip()


def clean_authors(text):
    """저자명에서 소속 윗첨자 번호를 떼어낸다. 'Kameda1, Takahashi2' → 'Kameda, Takahashi'."""
    text = SUPERSCRIPT_RE.sub('', text)
    text = re.sub(r'\s+([,;])', r'\1', text)
    return re.sub(r'\s{2,}', ' ', text).strip(' ,;')


def first_affiliation(text):
    """소속 블록에서 대표 소속 하나만 뽑는다. 이메일은 버린다."""
    text = re.sub(r'^\s*\d+\s*:\s*', '', text.strip())
    parts = [p.strip() for p in text.split(';')]
    parts = [p for p in parts if p and '@' not in p]
    if not parts:
        return ''
    aff = re.sub(r'^\s*\d+\s*:\s*', '', parts[0])
    return aff.strip(' .,')


def classify(row):
    """행의 역할을 (kind, text)로 판정."""
    size = round(max(w['size'] for w in row), 1)
    bold = any('Bold' in w['fontname'] for w in row)
    italic_only = all('Italic' in w['fontname'] for w in row)
    text = join_words(row)

    if size <= 8.5:
        return ('banner', text) if bold else ('skip', text)
    if size >= 14:
        return ('header', text)
    if 10.4 <= size <= 10.9 and italic_only:
        return ('meta', text)
    if 9.2 <= size <= 9.9 and bold:
        return ('marker', text)
    if 10.9 <= size <= 11.4:
        if not bold and re.fullmatch(r'\d{1,3}', text):
            return ('skip', text)       # 페이지 번호
        return ('title', text)
    if 9.9 <= size <= 10.4:
        # 좌장이 여러 명이면 둘째 줄부터 본문 크기(10.0 italic)로 떨어진다 (P1 등)
        if italic_only and CHAIR_SPLIT_RE.match(text):
            return ('meta', text)
        names = [w for w in row if 'Italic' not in w['fontname']]
        affil = [w for w in row if 'Italic' in w['fontname']]
        return ('people', (join_words(names), join_words(affil)))
    return ('skip', text)


def parse_pdf(path, building, tour_end):
    sessions, papers = [], []
    cur_type = 'oral'
    sess = None           # 진행 중인 세션 dict
    header_buf = []       # 여러 줄로 접힌 세션 헤더
    pending = None        # 진행 중인 발표 dict
    title_buf, name_buf, affil_buf = [], [], []
    meta_buf = []

    def flush_paper():
        nonlocal pending, title_buf, name_buf, affil_buf
        if pending is not None:
            pending['title'] = ' '.join(title_buf).strip()
            names = clean_authors(' '.join(name_buf))
            aff = first_affiliation(' '.join(affil_buf))
            pending['authors'] = f"{names} ({aff})" if names and aff else (names or aff)
            papers.append(pending)
        pending = None
        title_buf, name_buf, affil_buf = [], [], []

    def flush_meta():
        """세션 메타(날짜·시간·장소·좌장) 확정."""
        if not sess or not meta_buf:
            return
        text = ' '.join(meta_buf)
        m = META_DATE_RE.match(text)
        if m:
            sess['date'] = to_iso(m.group(1), m.group(2), m.group(3))
        mt = META_TIME_RE.search(text)
        if mt:
            sess['start'], sess['end'] = to24(mt.group(1)), to24(mt.group(2))
        else:
            m1 = META_ONE_RE.search(text)
            if m1:
                sess['start'] = to24(m1.group(1))
                sess['end'] = tour_end          # 프로그램에 종료 시각 없음 (추정)
        ml = META_LOC_RE.search(text)
        if ml:
            loc = ml.group(1).strip().rstrip(',')
            room = re.sub(r'^(Plenary\s+room|Room)\s*', '', loc, flags=re.I).strip()
            sess['room'] = room
            fl = re.search(r'(\d)\d{2}$', room.replace(' ', ''))
            if fl:
                sess['floor'] = int(fl.group(1))
        # "..., Session Chair: A, Session Chair: B" → 좌장 이름만 뽑아 합친다
        chairs = [c.strip().strip(',').strip()
                  for c in CHAIR_SPLIT_RE.split(text)[1:]]
        chairs = [c for c in chairs if c]
        if chairs:
            sess['chair'] = ', '.join(chairs)
        if not sess.get('room'):
            sess['room'] = 'Off-site'   # 기술투어: 집합 장소를 이메일로 공지
        meta_buf.clear()

    def flush_header():
        nonlocal sess
        if not header_buf:
            return
        m = HEADER_RE.match(' '.join(header_buf))
        header_buf.clear()
        if not m:
            return
        sess = {'id': m.group(1), 'track_title': m.group(2).strip(),
                'building': building, 'room': '', 'type': cur_type}
        sessions.append(sess)

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(extra_attrs=['fontname', 'size'])
            for row in group_rows(words, ROW_TOL):
                kind, payload = classify(row)
                if kind == 'skip':
                    continue
                if kind == 'banner':
                    if payload in BANNER_TYPE:
                        cur_type = BANNER_TYPE[payload]
                    continue
                if kind == 'header':
                    flush_paper()
                    flush_meta()
                    flush_header()          # 앞 세션 헤더가 미확정이면 정리
                    header_buf.append(payload)
                    continue
                if header_buf and kind != 'header':
                    flush_header()
                if kind == 'meta':
                    meta_buf.append(payload)
                    continue
                if meta_buf:
                    flush_meta()
                if kind == 'marker':
                    flush_paper()
                    mk = MARKER_RE.match(payload)
                    if not mk or sess is None:
                        continue
                    pending = {
                        'paper_no': '', 'session_id': sess['id'],
                        'authors': '', 'title': '',
                        'start': to24(mk.group(5)), 'end': to24(mk.group(6)),
                    }
                    continue
                if kind == 'title' and pending is not None:
                    title_buf.append(payload)
                elif kind == 'people' and pending is not None:
                    names, affil = payload
                    if names:
                        name_buf.append(names)
                    if affil:
                        affil_buf.append(affil)
        flush_paper()
        flush_meta()
        flush_header()

    # 세션별 발표 순번으로 paper_no 부여 (프로그램에 발표 번호가 없음)
    seq = {}
    for p in papers:
        n = seq[p['session_id']] = seq.get(p['session_id'], 0) + 1
        p['paper_no'] = f"{p['session_id']}-{n}"

    # 발표 0편 세션은 회의·투어 → social (build.py의 oral 0편 경고 회피)
    counted = {p['session_id'] for p in papers}
    for s in sessions:
        if s['id'] not in counted and s['type'] == 'oral':
            s['type'] = 'social'

    # day: 행사 N일차 (IAQVEC과 같은 1-base). 날짜의 일(15~18)을 그대로 쓰면
    # 일자 탭이 "Day 15"로 표시돼 어색하다.
    day_no = {d: i + 1 for i, d in enumerate(sorted({s.get('date') for s in sessions}))}
    # block: (날짜, 시작시각)이 같은 세션 묶음에 1부터 번호
    slots = sorted({(s.get('date'), s.get('start')) for s in sessions})
    slot_no = {k: i + 1 for i, k in enumerate(slots)}
    for s in sessions:
        s['day'] = day_no[s.get('date')]
        s['block'] = slot_no[(s.get('date'), s.get('start'))]

    return sessions, papers


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pdf')
    ap.add_argument('--id',   required=True)
    ap.add_argument('--name', required=True)
    ap.add_argument('--out',  default='schedule.json')
    ap.add_argument('--timezone', default='Europe/Prague')
    ap.add_argument('--building', default='CTU',
                    help='전 세션 공통 건물명 (하드 룰 3: 단일 건물이면 값 하나로 고정)')
    ap.add_argument('--tour-end', default='12:00',
                    help='종료 시각이 없는 세션(기술투어)의 종료 시각 추정값')
    args = ap.parse_args()

    print(f"Conference: {args.name}  (id={args.id})")
    sessions, papers = parse_pdf(args.pdf, args.building, args.tour_end)
    print(f"Sessions: {len(sessions)}")
    print(f"Papers:   {len(papers)}")

    out = {
        'conference': {'id': args.id, 'name': args.name},
        'sessions':   sessions,
        'papers':     papers,
    }
    # 파서가 이미 24시간제·ISO로 변환하므로 pm_threshold 0
    finalize_v2(out, timezone=args.timezone, pm_threshold=0)
    pathlib.Path(args.out).write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Saved → {args.out} ({pathlib.Path(args.out).stat().st_size} bytes)")


if __name__ == '__main__':
    main()
