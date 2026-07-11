"""
Conference schedule PDF parser.
Extracts sessions and papers into a structured JSON.
"""
import pdfplumber
import re
import json
from pathlib import Path

from parser_utils import finalize_v2, slugify, group_rows

# Column x-boundaries (based on actual left-aligned column text, not centered headers).
# Header text is centered (Author@252, Title@436), but body text is left-aligned at ~194 and ~336.
AUTHOR_X = 190
TITLE_X  = 335
ROW_TOL  = 2.5  # vertical clustering tolerance

DAY_RE     = re.compile(r'Day\s+(\d+):\s+(\d{1,2}/\d{1,2}/\d{4})\s*\(([^)]+)\)')
SESS_RE    = re.compile(r'Session\s+(\d+)\s+(\d+-\d+)\s+(.+)')
# Time + location header. Accept missing or misspelled "Session chair:" and bare names.
# Examples handled:
#   "11:00 - 12:30 Location: SGM 123 / Session chair: Vincenzo Gentile"
#   "11:00 - 12:30 Location: GFS 118 / Yumna Kurdi"               (no 'Session chair:' label)
#   "11:00 - 12:30 Location: GFS 116 / Sesssion Chair: Lexuan Z."  (typo, capital)
#   "1:30 - 3:00  Location: VHE Courtyard"                         (no chair at all)
TIME_LOC_RE= re.compile(
    r'(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\s+Location:\s*([^/]+?)(?:\s*/\s*(?:Ses{2,}ion\s*[Cc]hair\s*:\s*)?(.+))?$'
)
PAPER_NO_RE= re.compile(r'^(\d+\s*\*?)$')
# Elsevier-style special session uses time ranges like "3:30-3:50" in the paper-no column
SPECIAL_TIME_RE = re.compile(r'^(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})$')

def split_columns(row):
    """Split a row into (paper_no_text, author_text, title_text) by x0."""
    pn, au, ti = [], [], []
    for w in row:
        if w['x0'] < AUTHOR_X:
            pn.append(w['text'])
        elif w['x0'] < TITLE_X:
            au.append(w['text'])
        else:
            ti.append(w['text'])
    return ' '.join(pn).strip(), ' '.join(au).strip(), ' '.join(ti).strip()

def parse_location(loc):
    """Parse 'SGM 123' or 'GFS 116' → (building, room, floor_guess)."""
    m = re.match(r'([A-Za-z]+)\s+(\d+)', loc.strip())
    if not m:
        return loc.strip(), '', None
    bldg, room = m.group(1), m.group(2)
    floor = int(room[0]) if room and room[0].isdigit() else None
    return bldg, room, floor

def parse_pdf(pdf_path):
    sessions = []
    papers = []
    cur_day = None
    cur_date = None

    with pdfplumber.open(pdf_path) as pdf:
        for pidx, page in enumerate(pdf.pages):
            words = page.extract_words(keep_blank_chars=False)
            rows = group_rows(words, ROW_TOL)

            cur_session = None
            in_paper_table = False
            paper_buf = None  # (paper_no, author_lines[], title_lines[])

            def flush_paper():
                nonlocal paper_buf
                if paper_buf and cur_session:
                    pno_raw, authors, title = paper_buf
                    starred = '*' in pno_raw
                    # Keep time-range labels (special sessions) as-is; else strip non-digits
                    if SPECIAL_TIME_RE.match(pno_raw):
                        pno = pno_raw.strip()
                    else:
                        pno = re.sub(r'\D', '', pno_raw)
                    # Strip sponsor team prefix from author
                    a = re.sub(r'^\[Sponsor\s+[Tt]eam:[^\]]+\]\s*', '', authors).strip()
                    papers.append({
                        'paper_no': pno,
                        'is_sponsored': starred,
                        'session_id': cur_session['id'],
                        'authors': a,
                        'title': title.strip(),
                    })
                paper_buf = None

            for row in rows:
                text_full = ' '.join(w['text'] for w in row).strip()

                # Day header
                m = DAY_RE.match(text_full)
                if m:
                    cur_day = int(m.group(1))
                    cur_date = m.group(2)
                    continue

                # Session header line 1: "Session 1 1-1 Indoor Air Quality"
                m = SESS_RE.match(text_full)
                if m:
                    flush_paper()
                    cur_session = {
                        'id': m.group(2),                # "1-1"
                        'block': int(m.group(1)),        # 1
                        'day': cur_day,
                        'date': cur_date,
                        'track_title': m.group(3).strip(),
                        'start': None, 'end': None,
                        'building': None, 'room': None, 'floor': None,
                        'chair': None,
                    }
                    in_paper_table = False
                    continue

                # Session header line 2: time + location + (optional) chair
                m = TIME_LOC_RE.search(text_full)
                if m and cur_session and cur_session['start'] is None:
                    cur_session['start'] = m.group(1)
                    cur_session['end']   = m.group(2)
                    bldg, room, floor    = parse_location(m.group(3))
                    cur_session['building'] = bldg
                    cur_session['room']     = room
                    cur_session['floor']    = floor
                    cur_session['chair']    = (m.group(4) or '').strip()
                    sessions.append(cur_session)
                    continue

                # Table header. Accept "Paper Number Author Title" and
                # "Paper Number Speaker Title" (special sessions like 9-7).
                if text_full.startswith('Paper Number') and 'Title' in text_full:
                    in_paper_table = True
                    paper_buf = None
                    continue

                if not in_paper_table or not cur_session:
                    continue

                # Column-split this row
                pn, au, ti = split_columns(row)

                # New "paper" starts if pn is a number OR a time-range
                # (Elsevier-format special session uses "3:30-3:50" as row key).
                is_new_row = bool(pn) and (
                    re.match(r'^\d+\s*\*?$', pn) or SPECIAL_TIME_RE.match(pn)
                )
                if is_new_row:
                    flush_paper()
                    paper_buf = (pn, au, ti)
                else:
                    # Continuation of current paper: append to author / title
                    if paper_buf:
                        pno, a, t = paper_buf
                        a2 = (a + ' ' + au).strip() if au else a
                        t2 = (t + ' ' + ti).strip() if ti else t
                        paper_buf = (pno, a2, t2)

            flush_paper()

    return sessions, papers

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Conference schedule PDF parser.')
    ap.add_argument('pdf', nargs='?',
                    default='/sessions/focused-sharp-goodall/mnt/uploads/session_schedule_0516-3.pdf')
    ap.add_argument('--id',   help='Conference id (slug). Defaults to slugified --name or PDF stem.')
    ap.add_argument('--name', help='Conference display name (e.g. "Building Simulation 2026").')
    ap.add_argument('--out',  default='schedule.json', help='Output JSON path.')
    ap.add_argument('--timezone', default=None,
                    help='IANA timezone (e.g. "America/Los_Angeles").')
    args = ap.parse_args()

    pdf_path = args.pdf
    sessions, papers = parse_pdf(pdf_path)

    # Derive conference identity. Priority: explicit --id, slug(--name), slug(filename).
    name = args.name or Path(pdf_path).stem.replace('_', ' ').replace('-', ' ').title()
    conf_id = args.id or slugify(args.name or Path(pdf_path).stem)

    print(f"Conference: {name}  (id={conf_id})")
    print(f"Sessions: {len(sessions)}")
    print(f"Papers:   {len(papers)}")

    out = {
        'conference': {'id': conf_id, 'name': name},
        'sessions':   sessions,
        'papers':     papers,
    }
    # 이 형식의 PDF는 AM/PM 없는 12시간제("1:30"=오후) → threshold 8로 24h 정규화
    finalize_v2(out, timezone=args.timezone, pm_threshold=8)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"Saved → {args.out} ({Path(args.out).stat().st_size} bytes)")
