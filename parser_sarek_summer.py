#!/usr/bin/env python3
"""
parser_sarek_summer.py — 대한설비공학회 하계학술발표대회 PDF 파서.

동계와 달리 다음 특성을 가집니다.
  - 세로 페이지 (≈580 × 776 pt)
  - 한 페이지 = 한 회장. 1단 컬럼 레이아웃.
  - 한 회장 안에서 두 날(목·금)이 섞여 있음. subsection 헤더에 일자 표시.
    예: "19 1-A AI활용 좌장 : 정유준 (한국기계연구원)" → day=19, subsection 1-A
  - 발표 행: 시간 (HH:MM - HH:MM) + 제목 + 저자 + 발표번호 (25-S-NNN)
  - 발표번호는 괄호로 둘러싸임: (25-S-001)

사용 예:
    python3 parser_sarek_summer.py /path/to/2025하계학술대회.pdf \
      --id sarek-2025-summer \
      --name "대한설비공학회 2025 하계학술발표대회" \
      --year 2025 --month 6
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
CONTENT_Y_MAX = 720         # 페이지 푸터(페이지번호) 제거
# 단어를 시간·번호 / 제목 / 저자 세 영역으로 가르는 x 경계
META_X_MAX  = 130           # 시간·발표번호 영역의 우측 끝
TITLE_X_MAX = 375           # 제목 영역의 우측 끝

# ---------- 정규식 ----------
HALL_RE       = re.compile(r'제(\d+)회장')
# 두 형태 모두 지원:
#   "19 1-A AI활용 좌장 : ..."  (일자 prefix 있음, 보통 그 일자의 첫 subsection)
#   "1-B 공조설비2 좌장 : ..."   (일자 prefix 없음, 이전 일자 유지)
SUBSECTION_RE = re.compile(r'^(?:(\d+)\s+)?(\d+-[A-Z])\s+(.+?)\s+좌장\s*:\s*(.+)$')
TIME_RE       = re.compile(r'^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})')
PAPER_NO_RE   = re.compile(r'^\(?(25-S-\d{3,4})\)?$')

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


def parse_hall_page(rows, hall_num, year, month, sessions, papers):
    cur_session = None
    cur_paper   = None
    cur_day     = None      # 1-A는 19, 1-E는 20 등 — subsection 헤더에서 갱신

    def flush_paper():
        nonlocal cur_paper
        if cur_paper and cur_session:
            title   = ' '.join(cur_paper['title_parts']).strip()
            authors = ' '.join(cur_paper['author_parts']).strip()
            paper_no = cur_paper['paper_no'] or f"{cur_paper['start']}-{cur_paper['end']}"
            if title or authors:
                papers.append({
                    'paper_no':   paper_no,
                    'session_id': cur_session['id'],
                    'authors':    authors,
                    'title':      title,
                    'start':      cur_paper['start'],
                    'end':        cur_paper['end'],
                })
        cur_paper = None

    for row in rows:
        text = ' '.join(w['text'] for w in row).strip()

        # 1) Subsection 헤더 (일자 prefix는 선택적)
        m = SUBSECTION_RE.match(text)
        if m:
            flush_paper()
            day_str    = m.group(1)
            section_id = m.group(2)
            # 특수 케이스: "1911-A" 처럼 일자와 subsection이 붙은 경우
            if day_str is None:
                sm = re.match(r'^(19|20)(\d+-[A-Z])$', section_id)
                if sm:
                    day_str    = sm.group(1)
                    section_id = sm.group(2)
            if day_str is not None:
                cur_day = int(day_str)
            # cur_day가 여전히 None이면 19로 기본 (학회 첫날)
            if cur_day is None:
                cur_day = 19
            track_title = m.group(3).strip()
            chair       = m.group(4).strip()
            sid = section_id
            existing = next((s for s in sessions if s['id'] == sid), None)
            if existing:
                cur_session = existing
            else:
                cur_session = {
                    'id': sid,
                    'block': int(section_id.split('-')[0]),
                    'day': cur_day,
                    'date': f"{month}/{cur_day}/{year}",
                    'track_title': track_title,
                    'start': None, 'end': None,
                    'building': '회장',
                    'room': str(hall_num),
                    'floor': 1,
                    'chair': chair,
                }
                sessions.append(cur_session)
            continue

        # 2) 시간 행
        tm = TIME_RE.match(text)
        if tm:
            if is_skip_row(text):
                flush_paper(); continue
            flush_paper()
            if not cur_session: continue
            cur_paper = {
                'start': tm.group(1),
                'end':   tm.group(2),
                'paper_no':    '',
                'title_parts':  [],
                'author_parts': [],
            }
            t_parts, a_parts = collect_paper_words(row, skip_first=True)
            cur_paper['title_parts'].extend(t_parts)
            cur_paper['author_parts'].extend(a_parts)
            continue

        # 3) 발표번호 행 — (25-S-NNN) 형식
        if cur_paper and row:
            first_text = row[0]['text']
            pn = PAPER_NO_RE.match(first_text)
            if pn:
                cur_paper['paper_no'] = pn.group(1)
                t_parts, a_parts = collect_paper_words(row, skip_first=True)
                cur_paper['title_parts'].extend(t_parts)
                cur_paper['author_parts'].extend(a_parts)
                continue

        # 4) 연속 행
        if cur_paper:
            if is_skip_row(text):
                continue
            t_parts, a_parts = collect_paper_words(row)
            cur_paper['title_parts'].extend(t_parts)
            cur_paper['author_parts'].extend(a_parts)

    flush_paper()


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
    with pdfplumber.open(pdf_path) as pdf:
        for pidx, page in enumerate(pdf.pages):
            text_top = (page.extract_text() or '')[:300]
            hm = HALL_RE.search(text_top)
            if not hm: continue
            hall_num = int(hm.group(1))
            words = page.extract_words(keep_blank_chars=False)
            words = [w for w in words if w['top'] < CONTENT_Y_MAX]
            words = consolidate_split_chars(words)
            rows  = group_rows(words)
            parse_hall_page(rows, hall_num, year, month, sessions, papers)
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
    args = ap.parse_args()

    print(f"Conference: {args.name}  (id={args.id})")
    sessions, papers = parse_pdf(args.pdf, args.year, args.month)
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
