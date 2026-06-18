#!/usr/bin/env python3
"""
parser_sarek_summer.py — 대한설비공학회 하계학술발표대회 PDF 파서.

지원 형식 (2025, 2026 모두 처리):
  - 세로 A4 페이지, 1단 컬럼 레이아웃
  - 회장(제N회장)이 페이지를 넘어 이어질 수 있음 (2026 PDF)
  - 일자 표시 방식 두 가지를 모두 지원:
      a) 인라인 prefix: "19 1-A 트랙명 좌장 : ..."        (2025)
      b) 별도 헤더 행:  "<6월 25일(목)>" 이후 "1-A 트랙명 좌장 : ..."  (2026)
  - 발표 행: 시간 (HH:MM - HH:MM) + 제목 + 저자 + 발표번호 (YY-S-NNN)
  - 발표번호는 괄호로 둘러싸임: (26-S-001)

사용 예:
    python3 parser_sarek_summer.py /path/to/2026하계학술대회.pdf \
      --id sarek-2026-summer \
      --name "대한설비공학회 2026 하계학술발표대회" \
      --year 2026 --month 6
"""
import argparse
import json
import pathlib
import re
import sys

try:
    import pdfplumber
except ImportError:
    sys.exit("pdfplumber이 필요합니다: pip install pdfplumber")

# ---------- 좌표 ----------
ROW_TOL       = 2.5
# A4 세로 페이지 (높이 841pt) 기준. 페이지번호 "- N -"는 top≈803.
# 2026 PDF는 본문 영역이 top≈775까지 확장되므로 800까지 포함해야 누락이 없음.
CONTENT_Y_MAX = 800
# 단어를 시간·번호 / 제목 / 저자 세 영역으로 가르는 x 경계
META_X_MAX  = 130           # 시간·발표번호 영역의 우측 끝
TITLE_X_MAX = 375           # 제목 영역의 우측 끝

# ---------- 정규식 ----------
# "▣ 제N회장 (간사: ...)" — 회장 시작 마커. 초청강연 안의 "(제9회장)" 같은
# 참조와 구분하기 위해 ▣ 글머리표를 요구.
HALL_START_RE = re.compile(r'^▣\s*제(\d+)회장')
# "<6월 25일(목)>" 같은 일자 헤더
DAY_HEADER_RE = re.compile(r'^<\s*\d+월\s+(\d+)일')
# 두 형태 모두 지원:
#   "19 1-A AI활용 좌장 : ..."  (일자 prefix 있음, 2025 PDF)
#   "1-B 공조설비2 좌장 : ..."   (일자 prefix 없음, 2026 PDF — 별도 일자 헤더에서 가져옴)
SUBSECTION_RE = re.compile(r'^(?:(\d+)\s+)?(\d+-[A-Z])\s+(.+?)\s+좌장\s*:\s*(.+)$')
# 부분 subsection (제목이 길어 좌장이 다음 줄로 밀린 경우)
PARTIAL_SUB_RE = re.compile(r'^(\d+-[A-Z])\s+')
CHAIR_LINE_RE  = re.compile(r'좌장\s*:')
# 시간 구분자로 hyphen(-)과 en-dash(–) 모두 허용 (PDF에 혼용됨)
TIME_RE       = re.compile(r'^(\d{1,2}:\d{2})\s*[\-–]\s*(\d{1,2}:\d{2})')
# 어떤 연도(2자리)든 매칭 — 25-S-001, 26-S-077 등
PAPER_NO_RE   = re.compile(r'^\(?(\d{2}-S-\d{3,4})\)?$')

SKIP_TOKENS = (
    '휴 식', '휴식', '초청강연', '강연제목', '사회', '간사',
    '정기총회', '중 식', '중식', '질의', '응답',
    '시상식', '경진대회', '경품', '추첨', '참가자',
    '오디토리움', '대회의실',
)


def consolidate_split_chars(words, y_tol=0.5, x_gap_max=0.5):
    """동계 파서와 동일한 split-char 보정. gap≤0.5pt로 인접한 토큰을 병합."""
    by_top = {}
    for w in words:
        by_top.setdefault(round(w['top']), []).append(w)
    out = []
    for _, group in by_top.items():
        if len(group) <= 1:
            out.extend(group); continue
        group = sorted(group, key=lambda w: w['x0'])
        merged = []
        cur = None
        for w in group:
            if (cur is not None
                and abs(w['top'] - cur['top']) <= y_tol
                and (w['x0'] - cur['x1']) <= x_gap_max):
                cur['text'] += w['text']
                cur['x1']    = w.get('x1', w['x0'] + 5)
            else:
                if cur is not None: merged.append(cur)
                cur = dict(w)
                if 'x1' not in cur: cur['x1'] = cur['x0'] + 5
        if cur is not None: merged.append(cur)
        out.extend(merged)
    return sorted(out, key=lambda w: (w['top'], w['x0']))


def group_rows(words, tol=ROW_TOL):
    if not words: return []
    words = sorted(words, key=lambda w: (w['top'], w['x0']))
    rows, cur = [], [words[0]]
    for w in words[1:]:
        if abs(w['top'] - cur[-1]['top']) <= tol:
            cur.append(w)
        else:
            rows.append(sorted(cur, key=lambda x: x['x0']))
            cur = [w]
    rows.append(sorted(cur, key=lambda x: x['x0']))
    return rows


def is_skip_row(text):
    return any(tok in text for tok in SKIP_TOKENS)


def collect_paper_words(words, skip_first=False):
    """주어진 단어들에서 title / author 영역의 텍스트를 수집."""
    title_parts, author_parts = [], []
    for w in (words[1:] if skip_first else words):
        x = w['x0']
        if x < META_X_MAX:
            continue
        if x < TITLE_X_MAX:
            title_parts.append(w['text'])
        else:
            author_parts.append(w['text'])
    return title_parts, author_parts


def process_rows(rows, year, month, sessions, papers, state):
    """Rows 한 묶음을 처리하며 state(hall_num, day, session, paper)를 갱신.

    state는 가변 dict로 전달되며, 페이지를 가로질러 같은 인스턴스가 유지됨.
    이렇게 해야 회장이 페이지를 넘어 이어지는 2026 PDF 형식도 정상 파싱됨.
    """
    def flush_paper():
        cp = state['paper']
        cs = state['session']
        if cp and cs:
            title   = ' '.join(cp['title_parts']).strip()
            authors = ' '.join(cp['author_parts']).strip()
            paper_no = cp['paper_no'] or f"{cp['start']}-{cp['end']}"
            if title or authors:
                papers.append({
                    'paper_no':   paper_no,
                    'session_id': cs['id'],
                    'authors':    authors,
                    'title':      title,
                    'start':      cp['start'],
                    'end':        cp['end'],
                })
        state['paper'] = None

    i = 0
    while i < len(rows):
        row = rows[i]
        text = ' '.join(w['text'] for w in row).strip()

        # 0) 회장 시작 헤더 — "▣ 제N회장 (간사: ...)"
        hm = HALL_START_RE.match(text)
        if hm:
            flush_paper()
            state['hall_num'] = int(hm.group(1))
            state['session']  = None
            i += 1
            continue

        # 0b) 일자 헤더 — "<6월 25일(목)>"
        dh = DAY_HEADER_RE.match(text)
        if dh:
            flush_paper()
            state['day'] = int(dh.group(1))
            i += 1
            continue

        # 0c) 부분 subsection 처리: "1-C 교육 : ..." (좌장이 다음 줄에 있음)
        # 다음 줄에 좌장 정보가 있으면 두 줄을 합쳐 SUBSECTION_RE로 매칭.
        if (PARTIAL_SUB_RE.match(text) and not CHAIR_LINE_RE.search(text)
                and i + 1 < len(rows)):
            next_text = ' '.join(w['text'] for w in rows[i+1]).strip()
            if CHAIR_LINE_RE.search(next_text):
                merged = text + ' ' + next_text
                m = SUBSECTION_RE.match(merged)
                if m:
                    text = merged  # 아래 로직이 처리하도록
                    i += 1         # 다음 줄도 소비

        # 1) Subsection 헤더 (일자 prefix는 선택적)
        m = SUBSECTION_RE.match(text)
        if m:
            flush_paper()
            day_str    = m.group(1)
            section_id = m.group(2)
            # 특수 케이스: "1911-A" 처럼 일자와 subsection이 붙은 경우 (2025)
            if day_str is None:
                sm = re.match(r'^(19|20|25|26)(\d+-[A-Z])$', section_id)
                if sm:
                    day_str    = sm.group(1)
                    section_id = sm.group(2)
            if day_str is not None:
                state['day'] = int(day_str)
            if state['day'] is None or state['hall_num'] is None:
                # 회장이나 일자 정보 없으면 이 subsection은 처리 불가 — skip
                continue
            track_title = m.group(3).strip()
            chair       = m.group(4).strip()
            sid = section_id
            existing = next((s for s in sessions if s['id'] == sid), None)
            if existing:
                state['session'] = existing
            else:
                state['session'] = {
                    'id': sid,
                    'block': int(section_id.split('-')[0]),
                    'day': state['day'],
                    'date': f"{month}/{state['day']}/{year}",
                    'track_title': track_title,
                    'start': None, 'end': None,
                    'building': '회장',
                    'room': str(state['hall_num']),
                    'floor': 1,
                    'chair': chair,
                }
                sessions.append(state['session'])
            i += 1
            continue

        # 2) 시간 행
        tm = TIME_RE.match(text)
        if tm:
            if is_skip_row(text):
                flush_paper(); i += 1; continue
            flush_paper()
            if not state['session']: i += 1; continue
            state['paper'] = {
                'start': tm.group(1),
                'end':   tm.group(2),
                'paper_no':    '',
                'title_parts':  [],
                'author_parts': [],
            }
            t_parts, a_parts = collect_paper_words(row, skip_first=True)
            state['paper']['title_parts'].extend(t_parts)
            state['paper']['author_parts'].extend(a_parts)
            i += 1
            continue

        # 3) 발표번호 행 — (YY-S-NNN) 형식
        if state['paper'] and row:
            first_text = row[0]['text']
            pn = PAPER_NO_RE.match(first_text)
            if pn:
                state['paper']['paper_no'] = pn.group(1)
                t_parts, a_parts = collect_paper_words(row, skip_first=True)
                state['paper']['title_parts'].extend(t_parts)
                state['paper']['author_parts'].extend(a_parts)
                i += 1
                continue

        # 4) 연속 행
        if state['paper']:
            if not is_skip_row(text):
                t_parts, a_parts = collect_paper_words(row)
                state['paper']['title_parts'].extend(t_parts)
                state['paper']['author_parts'].extend(a_parts)
        i += 1


def _t(s):
    h, m = map(int, s.split(':'))
    return (h + (12 if h < 8 else 0)) * 60 + m


def derive_session_times(sessions, papers):
    by_sid = {}
    for p in papers:
        by_sid.setdefault(p['session_id'], []).append(p)
    for s in sessions:
        ps = by_sid.get(s['id'], [])
        if not ps: continue
        starts = [p['start'] for p in ps if p.get('start')]
        ends   = [p['end']   for p in ps if p.get('end')]
        if starts: s['start'] = min(starts, key=_t)
        if ends:   s['end']   = max(ends,   key=_t)
        # day는 subsection 헤더에서 정해지지만, 발표가 다른 날이면 갱신
        days = {p.get('day') for p in ps if p.get('day')}
        # day는 paper에 없으니 session에서 유지


def parse_pdf(pdf_path, year, month):
    sessions, papers = [], []
    # 페이지를 가로질러 hall/day/session/paper 상태를 유지.
    # 회장이 페이지를 넘어 이어지는 2026 PDF 형식을 처리하기 위함.
    state = {'hall_num': None, 'day': None, 'session': None, 'paper': None}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(keep_blank_chars=False)
            words = [w for w in words if w['top'] < CONTENT_Y_MAX]
            words = consolidate_split_chars(words)
            rows  = group_rows(words)
            process_rows(rows, year, month, sessions, papers, state)
    # 마지막 페이지에 남은 paper flush
    if state['paper'] and state['session']:
        process_rows([], year, month, sessions, papers, state)  # no-op이지만 안전 호출
        # 직접 flush
        cp, cs = state['paper'], state['session']
        title   = ' '.join(cp['title_parts']).strip()
        authors = ' '.join(cp['author_parts']).strip()
        paper_no = cp['paper_no'] or f"{cp['start']}-{cp['end']}"
        if title or authors:
            papers.append({
                'paper_no':   paper_no,
                'session_id': cs['id'],
                'authors':    authors,
                'title':      title,
                'start':      cp['start'],
                'end':        cp['end'],
            })
        state['paper'] = None
    derive_session_times(sessions, papers)
    return sessions, papers


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pdf')
    ap.add_argument('--id',   required=True)
    ap.add_argument('--name', required=True)
    ap.add_argument('--year', type=int, default=2025)
    ap.add_argument('--month', type=int, default=6)
    ap.add_argument('--out',  default='schedule.json')
    ap.add_argument('--day-fix', action='append', default=[],
                    help='PDF day 오타 보정: --day-fix 19:25 (반복 가능)')
    args = ap.parse_args()

    print(f"Conference: {args.name}  (id={args.id})")
    sessions, papers = parse_pdf(args.pdf, args.year, args.month)

    # PDF 일자 오타 보정 (예: 2026 PDF는 회장10이 "<6월 19일>"로 잘못 표기됨)
    if args.day_fix:
        fixes = {}
        for spec in args.day_fix:
            a, b = spec.split(':')
            fixes[int(a)] = int(b)
        for s in sessions:
            if s.get('day') in fixes:
                new_day = fixes[s['day']]
                s['day']  = new_day
                s['date'] = f"{args.month}/{new_day}/{args.year}"
        print(f"Day 보정 적용: {fixes}")
    print(f"Sessions: {len(sessions)}")
    print(f"Papers:   {len(papers)}")

    out = {
        'conference': {'id': args.id, 'name': args.name},
        'sessions':   sessions,
        'papers':     papers,
    }
    pathlib.Path(args.out).write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Saved → {args.out} ({pathlib.Path(args.out).stat().st_size} bytes)")


if __name__ == '__main__':
    main()
