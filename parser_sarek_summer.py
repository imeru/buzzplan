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

from parser_utils import (
    finalize_v2, group_rows, consolidate_split_chars, is_skip_row,
    derive_session_times,
)

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
# "▣ 포스터 세션" — 정규 발표가 끝나는 지점. 이후 행은 처리하지 않음
# (포스터 표는 시간 컬럼이 없어 정규 발표 파싱 로직과 충돌함).
POSTER_STOP_RE = re.compile(r'^▣\s*포스터')
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

# 발표가 아닌 진행성 안내 행만 스킵. 짧은 토큰("응답", "추첨")은
# 일반 발표 제목("열응답", "추첨식 회수")에 우연히 매칭돼서 진짜 발표를
# 누락시키므로 반드시 phrase 단위로 매칭.
SKIP_TOKENS = (
    '휴 식', '휴식', '강연제목', '정기총회', '중 식', '중식',
    '질의 응답', '시상식', '경진대회', '경품 추첨', '참가자 경품',
)


def process_table(table_data, year, month, state, sessions, papers):
    """extract_tables가 만든 한 표를 처리.

    표 첫 행은 subsection 헤더 (예: ['1-A 열환경', '', '좌장 : 위승환 (서울과학기술대학교)']).
    이후 행들은 발표 (예: ['09:00 - 09:15\\n(26-S-001)', '제목', '저자']).
    셀 안의 다중라인 텍스트는 PDF의 시각적 줄바꿈을 \\n으로 보존하므로 단순히
    공백으로 합치면 깔끔한 단일 문자열이 된다 — 기존 단어 단위 파싱이 겪던
    '제목 라인이 시간 라인보다 위에 렌더돼 잘못 귀속' 문제가 사라짐.
    """
    if not table_data: return
    # 헤더 — 모든 셀을 합쳐 SUBSECTION_RE에 매칭. 슬래시·줄바꿈 정규화.
    header_cells = [(c or '').replace('\n', ' ').replace('/', ' ').strip()
                    for c in table_data[0]]
    header_text  = ' '.join(c for c in header_cells if c)
    m = SUBSECTION_RE.match(header_text)
    if not m:
        return  # 세션 표가 아님 (초청강연 등)
    day_str    = m.group(1)
    section_id = m.group(2)
    if day_str is None:
        sm = re.match(r'^(19|20|25|26)(\d+-[A-Z])$', section_id)
        if sm:
            day_str    = sm.group(1)
            section_id = sm.group(2)
    if day_str is not None:
        state['day'] = int(day_str)
    if state['day'] is None:
        return
    hall_num = int(section_id.split('-')[0])
    track_title = m.group(3).strip()
    chair       = m.group(4).strip()
    existing = next((s for s in sessions if s['id'] == section_id), None)
    if existing:
        session = existing
    else:
        session = {
            'id': section_id,
            'block': hall_num,
            'day': state['day'],
            'date': f"{month}/{state['day']}/{year}",
            'track_title': track_title,
            'start': None, 'end': None,
            'building': '회장',
            'room': str(hall_num),
            'floor': 1,
            'chair': chair,
        }
        sessions.append(session)

    # 발표 행 처리
    for row in table_data[1:]:
        if len(row) < 2: continue
        # 보통 [time_cell, title_cell, author_cell] 3열이지만 일부 표는 2열.
        time_cell   = row[0] or ''
        title_cell  = row[1] or ''
        author_cell = row[2] if len(row) > 2 else ''

        # time_cell: "HH:MM - HH:MM" 또는 "HH:MM - HH:MM\n(26-S-NNN)"
        time_line = time_cell.split('\n', 1)[0].strip()
        tm = TIME_RE.match(time_line)
        if not tm: continue
        # 발표가 아닌 진행 항목 (질의 응답 등)은 스킵
        joined = (time_cell + ' ' + title_cell).strip()
        if is_skip_row(joined, SKIP_TOKENS): continue
        # paper_no — time_cell 두번째 줄 또는 title_cell에서 찾기
        paper_no = ''
        for src in (time_cell, title_cell):
            pm = re.search(r'\(?(\d{2}-S-\d{3,4})\)?', src or '')
            if pm:
                paper_no = pm.group(1)
                break
        if not paper_no:
            paper_no = f"{tm.group(1)}-{tm.group(2)}"
        # title·author 정규화: \n과 다중 공백을 단일 공백으로
        title   = ' '.join((title_cell  or '').split())
        # 제목에서 발표번호 패턴이 끼어들면 제거
        title   = re.sub(r'\(?\d{2}-S-\d{3,4}\)?\s*', '', title).strip()
        authors = ' '.join((author_cell or '').split())
        if not title and not authors: continue
        papers.append({
            'paper_no':   paper_no,
            'session_id': section_id,
            'authors':    authors,
            'title':      title,
            'start':      tm.group(1),
            'end':        tm.group(2),
        })


def parse_pdf(pdf_path, year, month):
    sessions, papers = [], []
    state = {'day': None, 'stopped': False}

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            if state['stopped']: break

            # 페이지의 텍스트 마커(<6월 N일>, 포스터 시작)와 표를 y순서로 처리
            items = []  # [(y, kind, payload)]

            # 1) 텍스트에서 마커 찾기
            words = page.extract_words(keep_blank_chars=False)
            words = consolidate_split_chars(words)
            rows  = group_rows(words, ROW_TOL)
            for row in rows:
                rtext = ' '.join(w['text'] for w in row).strip()
                y = min(w['top'] for w in row)
                dm = DAY_HEADER_RE.match(rtext)
                if dm:
                    items.append((y, 'day', int(dm.group(1))))
                elif POSTER_STOP_RE.match(rtext):
                    items.append((y, 'stop', None))

            # 2) 표
            for tbl in page.find_tables():
                y = tbl.bbox[1]
                items.append((y, 'table', tbl.extract()))

            items.sort(key=lambda it: it[0])

            for y, kind, payload in items:
                if kind == 'stop':
                    state['stopped'] = True
                    break
                elif kind == 'day':
                    state['day'] = payload
                elif kind == 'table':
                    process_table(payload, year, month, state, sessions, papers)

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
    ap.add_argument('--timezone', default='Asia/Seoul',
                    help='IANA timezone (기본: Asia/Seoul)')
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
    # SAREK PDF는 이미 24시간제 → pm_threshold 0 (zero-pad·날짜 ISO화만)
    finalize_v2(out, timezone=args.timezone, pm_threshold=0)
    pathlib.Path(args.out).write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Saved → {args.out} ({pathlib.Path(args.out).stat().st_size} bytes)")


if __name__ == '__main__':
    main()
