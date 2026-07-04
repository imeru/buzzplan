#!/usr/bin/env python3
"""
parser_sarek.py — 대한설비공학회(SAREK) 동·하계 학술발표대회 PDF 파서.

본 파서는 SAREK 프로그램북 PDF의 다음 특성을 가정합니다.

  - 가로 페이지 (≈1066 × 729 pt)
  - 한 페이지 = 한 회장 (제N회장), 페이지 안에 오전 컬럼(좌)·오후 컬럼(우)
  - 한 컬럼 안에 여러 subsection: 예) "1-A 에너지 생산/저장 1 좌장 : 최종민(제주대학교)"
  - 발표 행: 시간 (HH:MM-HH:MM) + 제목 + 저자 + 발표번호 (YY-W-NNN)
  - 휴식·초청강연·간사 등은 본문에 끼어들 수 있어 모두 필터링

표준 conference JSON 스키마와 호환되도록 출력합니다.

사용 예:
    python3 parser_sarek.py /path/to/2025동계학술대회프로그램북.pdf \
      --id sarek-2025-winter \
      --name "대한설비공학회 2025 동계학술발표대회" \
      --date 2025-11-28 \
      --out data/sarek-2025-winter.json
"""
import argparse
import json
import pathlib
import re

from parser_utils import finalize_v2
import sys

try:
    import pdfplumber
except ImportError:
    sys.exit("pdfplumber이 필요합니다: pip install pdfplumber")

# ---------- 페이지·컬럼 좌표 ----------
COLUMN_SPLIT_X = 570        # AM/PM 컬럼 경계
ROW_TOL        = 2.5        # 행 클러스터링 허용 오차 (pt)
CONTENT_Y_MAX  = 635        # 페이지 푸터 시작점(정기총회 등) 직전까지 포함

# 컬럼 내부 x 경계 — meta(시간·번호) / title / author
COL_BOUNDS_AM = {'meta_max': 110, 'title_max': 355}
COL_BOUNDS_PM = {'meta_max': 640, 'title_max': 880}

# ---------- 정규식 ----------
HALL_RE      = re.compile(r'제(\d+)회장')
SUBSECTION_RE= re.compile(r'^(\d+)-([A-Z])\s+(.+?)\s+좌장\s*:\s*(.+)$')
TIME_RE      = re.compile(r'^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})')
PAPER_NO_RE  = re.compile(r'^(\d{2}-W-\d{3,4})$')

SKIP_TOKENS  = (
    '휴 식', '휴식', '초청강연', '강연제목', '사회', '간사',
    '정기총회', '중 식', '중식', '질의', '응답',
    '시상식', '경진대회', '행사', '대회의실',
)


def consolidate_split_chars(words, y_tol=0.5, x_gap_max=0.5):
    """PDF 렌더링이 시간·발표번호 등을 문자별로 쪼개 추출하는 경우가 있다.
    같은 y이고 이전 토큰의 x1과 다음 토큰의 x0이 거의 일치(gap ≤ 0.5pt)할 때
    같은 단어로 병합. 일반 단어는 1.5pt 정도 띄어쓰기 간격이 있어 영향 없음.
    예: ['16', ':', '1', '0', '-1', '6', ':', '25'] → '16:10-16:25'
    """
    by_top = {}
    for w in words:
        key = round(w['top'])
        by_top.setdefault(key, []).append(w)

    result = []
    for top_key, group in by_top.items():
        if len(group) <= 1:
            result.extend(group); continue
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
        result.extend(merged)
    return sorted(result, key=lambda w: (w['top'], w['x0']))


def group_rows(words, tol=ROW_TOL):
    """y-좌표가 비슷한 단어들을 한 행으로 묶는다."""
    if not words:
        return []
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


def split_columns(rows):
    """각 행을 AM(좌) / PM(우) 단어 리스트로 분리하여 두 컬럼의 행 시퀀스 반환."""
    am_rows, pm_rows = [], []
    for row in rows:
        am = [w for w in row if w['x0'] < COLUMN_SPLIT_X]
        pm = [w for w in row if w['x0'] >= COLUMN_SPLIT_X]
        # 같은 row에서 두 컬럼에 동시에 있을 수 있음. 빈 컬럼은 스킵.
        if am: am_rows.append(am)
        if pm: pm_rows.append(pm)
    return am_rows, pm_rows


def is_skip_row(text):
    """휴식·초청강연·간사 등 본문에 끼어드는 행을 식별."""
    for tok in SKIP_TOKENS:
        if tok in text:
            return True
    return False


def collect_paper_words(words, bounds, skip_first=False):
    """주어진 단어들에서 title / author 영역의 텍스트를 수집."""
    title_parts, author_parts = [], []
    for w in (words[1:] if skip_first else words):
        x = w['x0']
        if x < bounds['meta_max']:
            continue
        if x < bounds['title_max']:
            title_parts.append(w['text'])
        else:
            author_parts.append(w['text'])
    return title_parts, author_parts


def parse_column(col_rows, hall_num, bounds, date, sessions, papers):
    """한 컬럼(AM 또는 PM)의 행들을 순회하며 세션과 발표를 누적."""
    cur_session = None
    cur_paper   = None

    def flush_paper():
        nonlocal cur_paper
        if cur_paper and cur_session:
            title   = ' '.join(cur_paper['title_parts']).strip()
            authors = ' '.join(cur_paper['author_parts']).strip()
            # 발표번호가 없는 특별세션(PD 발표 등)은 시간 범위를 ID로 사용
            paper_no = cur_paper['paper_no'] or f"{cur_paper['start']}-{cur_paper['end']}"
            # 제목·저자가 둘 다 비어 있으면 의미 없는 행으로 보고 스킵
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

    for row in col_rows:
        text = ' '.join(w['text'] for w in row).strip()

        # 1) 세션 헤더
        m = SUBSECTION_RE.match(text)
        if m:
            flush_paper()
            block_num   = int(m.group(1))
            sec_letter  = m.group(2)
            track_title = m.group(3).strip()
            chair       = m.group(4).strip()
            sid = f"{block_num}-{sec_letter}"
            # 이미 존재하면 재사용
            existing = next((s for s in sessions if s['id'] == sid), None)
            if existing:
                cur_session = existing
            else:
                cur_session = {
                    'id': sid,
                    'block': block_num,
                    'day': 1,
                    'date': date,
                    'track_title': track_title,
                    'start': None, 'end': None,
                    'building': '회장',
                    'room': str(hall_num),
                    'floor': 1,
                    'chair': chair,
                }
                sessions.append(cur_session)
            continue

        # 2) 시간 행 = 발표 경계
        tm = TIME_RE.match(text)
        if tm:
            if is_skip_row(text):
                flush_paper()
                continue
            flush_paper()
            if not cur_session:
                continue  # 세션 없이 시간 행만 있는 경우는 무시
            cur_paper = {
                'start': tm.group(1),
                'end':   tm.group(2),
                'paper_no':     '',
                'title_parts':  [],
                'author_parts': [],
            }
            # 시간 행 자체에 제목·저자가 함께 있는 경우 흡수
            t_parts, a_parts = collect_paper_words(row, bounds, skip_first=True)
            cur_paper['title_parts'].extend(t_parts)
            cur_paper['author_parts'].extend(a_parts)
            continue

        # 3) 발표번호 행
        if cur_paper:
            # 첫 단어가 발표번호 형태?
            first_text = row[0]['text'] if row else ''
            pn = PAPER_NO_RE.match(first_text)
            if pn:
                cur_paper['paper_no'] = pn.group(1)
                # 발표번호 옆에도 텍스트가 있으면 흡수
                t_parts, a_parts = collect_paper_words(row, bounds, skip_first=True)
                cur_paper['title_parts'].extend(t_parts)
                cur_paper['author_parts'].extend(a_parts)
                continue

        # 4) 그 외 연속 행 — 제목/저자 누적
        if cur_paper:
            if is_skip_row(text):
                continue
            t_parts, a_parts = collect_paper_words(row, bounds)
            cur_paper['title_parts'].extend(t_parts)
            cur_paper['author_parts'].extend(a_parts)

    flush_paper()


def derive_session_times(sessions, papers):
    """각 세션의 start/end를 그 세션 발표들의 시간 범위로 채운다."""
    by_sid = {}
    for p in papers:
        by_sid.setdefault(p['session_id'], []).append(p)
    for s in sessions:
        ps = by_sid.get(s['id'], [])
        if not ps:
            continue
        starts = [p['start'] for p in ps if p.get('start')]
        ends   = [p['end']   for p in ps if p.get('end')]
        if starts: s['start'] = min(starts, key=_t)
        if ends:   s['end']   = max(ends,   key=_t)


def _t(s):
    h, m = map(int, s.split(':'))
    return (h + (12 if h < 8 else 0)) * 60 + m


def parse_pdf(pdf_path, date):
    sessions, papers = [], []
    with pdfplumber.open(pdf_path) as pdf:
        for pidx, page in enumerate(pdf.pages):
            text_top = (page.extract_text() or '')[:300]
            hm = HALL_RE.search(text_top)
            if not hm:
                continue
            hall_num = int(hm.group(1))
            words = page.extract_words(keep_blank_chars=False)
            # 페이지 푸터의 행사 일정·페이지 번호 등을 제거
            words = [w for w in words if w['top'] < CONTENT_Y_MAX]
            # 일부 행에서 시간·발표번호가 문자 단위로 쪼개져 추출되는 경우 보정
            words = consolidate_split_chars(words)
            rows  = group_rows(words)
            am_rows, pm_rows = split_columns(rows)
            parse_column(am_rows, hall_num, COL_BOUNDS_AM, date, sessions, papers)
            parse_column(pm_rows, hall_num, COL_BOUNDS_PM, date, sessions, papers)
    derive_session_times(sessions, papers)
    return sessions, papers


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pdf', help='SAREK 프로그램북 PDF')
    ap.add_argument('--id',   required=True)
    ap.add_argument('--name', required=True)
    ap.add_argument('--date', default='2025-11-28',
                    help='학회 날짜 (YYYY-MM-DD). 기본: 2025-11-28')
    ap.add_argument('--out',  default='schedule.json')
    ap.add_argument('--timezone', default='Asia/Seoul',
                    help='IANA timezone (기본: Asia/Seoul)')
    args = ap.parse_args()

    # 파싱 내부는 M/D/YYYY로 다루고, 출력 직전 finalize_v2가 ISO로 정규화
    y, m, d = args.date.split('-')
    date_us = f"{int(m)}/{int(d)}/{y}"

    print(f"Conference: {args.name}  (id={args.id})")
    sessions, papers = parse_pdf(args.pdf, date_us)
    print(f"Sessions: {len(sessions)}")
    print(f"Papers:   {len(papers)}")

    out = {
        'conference': {'id': args.id, 'name': args.name},
        'sessions':   sessions,
        'papers':     papers,
    }
    # SAREK PDF는 이미 24시간제 → pm_threshold 0 (zero-pad·날짜 ISO화만)
    finalize_v2(out, timezone=args.timezone, pm_threshold=0)
    pathlib.Path(args.out).write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Saved → {args.out} ({pathlib.Path(args.out).stat().st_size} bytes)")


if __name__ == '__main__':
    main()
