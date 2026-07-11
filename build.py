#!/usr/bin/env python3
"""
build.py — PDF에서 학회 JSON 빌드 + conferences.json 자동 등록.

PDF를 파싱해 data/<id>.json을 만들고, conferences.json에 새 학회 항목을
추가합니다 (이미 있으면 갱신). 도구 본체(index.html)는 부팅 시 그 두
파일을 읽어 자동으로 새 학회를 지원합니다.

사용 예:
    # 신규 학회 빌드
    python3 build.py /path/to/iaqvec-2028.pdf --id iaqvec-2028 --name "IAQVEC 2028"

    # 같은 학회의 스케줄 갱신
    python3 build.py /path/to/updated.pdf --id iaqvec-2026 --name "IAQVEC 2026"

    # default 학회로 지정 (URL에 ?conf 가 없을 때 처음 보일 학회)
    python3 build.py /path/to/new.pdf --id iaqvec-2028 --name "IAQVEC 2028" --default

    # 검증만 (파일 수정하지 않음)
    python3 build.py /path/to/pdf.pdf --id test --name "Test" --dry-run
"""
import argparse
import json
import pathlib
import subprocess
import sys

from parser_utils import validate_v2, SCHEMA_VERSION


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pdf', help='학회 스케줄 PDF 파일 경로')
    ap.add_argument('--id',   required=True, help='학회 ID (소문자·하이픈, 예: iaqvec-2028)')
    ap.add_argument('--name', required=True, help='학회 표시명')
    ap.add_argument('--parser', default='parser.py',
                    help='사용할 파서 스크립트 (기본: parser.py)')
    ap.add_argument('--timezone', default=None,
                    help='IANA timezone (예: Asia/Seoul). 파서에 전달')
    ap.add_argument('--default', action='store_true',
                    help='이 학회를 conferences.json의 default로 지정')
    ap.add_argument('--dry-run', action='store_true',
                    help='검증만; 파일은 수정하지 않음')
    # 인식하지 못한 나머지 옵션(--year, --month, --day-fix 등)은 파서 스크립트로
    # 그대로 전달한다. 파서별 고유 옵션을 build.py가 일일이 알 필요가 없게.
    args, passthrough = ap.parse_known_args()

    here = pathlib.Path(__file__).parent
    parser_py = here / args.parser
    data_dir  = here / 'data'
    confs_idx = here / 'conferences.json'

    if not parser_py.exists():
        sys.exit(f"  파서를 찾을 수 없습니다: {parser_py}")
    if not pathlib.Path(args.pdf).exists():
        sys.exit(f"  PDF를 찾을 수 없습니다: {args.pdf}")

    out_json = data_dir / f"{args.id}.json"
    if args.dry_run:
        import tempfile
        tmp_path = pathlib.Path(tempfile.gettempdir()) / f"dryrun-{args.id}.json"
    else:
        data_dir.mkdir(exist_ok=True)
        tmp_path = out_json

    print(f"[1/4] PDF 파싱 ({args.parser}): {args.pdf}")
    cmd = [sys.executable, str(parser_py), args.pdf,
           '--id', args.id, '--name', args.name, '--out', str(tmp_path)]
    if args.timezone:
        cmd += ['--timezone', args.timezone]
    if passthrough:
        print(f"      파서로 전달: {' '.join(passthrough)}")
        cmd += passthrough
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(f"  파서 실행 실패 (exit {e.returncode})")

    print(f"[2/4] JSON 검증")
    data = json.loads(tmp_path.read_text(encoding='utf-8'))
    n_sess = len(data.get('sessions', []))
    n_pap  = len(data.get('papers', []))
    print(f"      sessions={n_sess}, papers={n_pap}")
    if n_sess == 0 or n_pap == 0:
        sys.exit("  세션 또는 발표가 0건입니다. 파서가 PDF를 잘못 인식한 것으로 보입니다.")
    sess_ids = {s['id'] for s in data['sessions']}
    orphans = [p for p in data['papers'] if p['session_id'] not in sess_ids]
    if orphans:
        print(f"      [경고] orphan papers: {len(orphans)}")
        print(f"             paper_no 일부: {[p['paper_no'] for p in orphans[:8]]}")

    # 스키마 v2 검증 (24h 시간, ISO 날짜, schema_version)
    problems = validate_v2(data)
    if problems:
        print(f"      [실패] 스키마 v{SCHEMA_VERSION} 검증 {len(problems)}건:")
        for p in problems[:10]:
            print(f"             - {p}")
        sys.exit("  파서 출력이 스키마 v2 규칙을 위반합니다. 파서를 확인하세요.")
    print(f"      스키마 v{SCHEMA_VERSION} 검증 통과 (24h 시간·ISO 날짜)")

    # 세션 시간 겹침 검사 (같은 building+room에서 시간대 중복)
    from collections import defaultdict
    by_room = defaultdict(list)
    for s in data['sessions']:
        if s.get('start') and s.get('end') and s.get('date'):
            by_room[(s['date'], s.get('building'), s.get('room'))].append(s)
    overlaps = []
    for key, group in by_room.items():
        group.sort(key=lambda s: s['start'])
        for a, b in zip(group, group[1:]):
            if b['start'] < a['end']:
                overlaps.append(f"{a['id']}({a['start']}-{a['end']}) ↔ {b['id']}({b['start']}-{b['end']}) @ {key}")
    if overlaps:
        print(f"      [경고] 같은 방 시간 겹침: {len(overlaps)}건")
        for o in overlaps[:5]:
            print(f"             - {o}")

    # 발표번호 연속성 검사: "XX-S-001" 같은 숫자 연번 계열에서 빠진 번호를 찾는다.
    # LLM/수동 추출의 누락을 잡는 핵심 게이트 (규칙 파서 결과에도 유효).
    import re as _re
    series = {}
    for p in data['papers']:
        m = _re.match(r'^(.*?)(\d{3,4})$', str(p.get('paper_no', '')))
        if m:
            series.setdefault(m.group(1), set()).add(int(m.group(2)))
    for prefix, nums in series.items():
        if len(nums) < 5:
            continue  # 연번 계열로 보기 어려움
        missing = sorted(set(range(min(nums), max(nums) + 1)) - nums)
        label = f"{prefix}{min(nums):03d}~{max(nums)}"
        if missing:
            head = ', '.join(str(n) for n in missing[:10])
            print(f"      [경고] 발표번호 결번 ({label}): {len(missing)}개 — {head}"
                  + (' ...' if len(missing) > 10 else ''))
        else:
            print(f"      발표번호 연속성 OK ({label}, {len(nums)}편)")

    # 세션별 발표 수 분포 (0편 세션은 키노트/행사가 아니면 파싱 누락 신호)
    from collections import Counter
    per_sess = Counter(p['session_id'] for p in data['papers'])
    zero = [s['id'] for s in data['sessions']
            if per_sess.get(s['id'], 0) == 0 and s.get('type', 'oral') == 'oral']
    counts = sorted(per_sess.values())
    if counts:
        mid = counts[len(counts) // 2]
        print(f"      세션당 발표 수: 최소 {counts[0]} / 중앙값 {mid} / 최대 {counts[-1]}")
    if zero:
        print(f"      [경고] 발표 0편인 oral 세션 {len(zero)}개: {zero[:8]} — 파싱 누락 가능성")

    if args.dry_run:
        try: tmp_path.unlink()
        except OSError: pass
        print("[3/4] dry-run: 파일 갱신 없음")
        return

    # data/<id>.json은 이미 tmp_path 위치에 있음

    print(f"[3/4] conferences.json 갱신")
    if confs_idx.exists():
        reg = json.loads(confs_idx.read_text(encoding='utf-8'))
    else:
        reg = {'default': args.id, 'conferences': []}

    entry = {'id': args.id, 'name': args.name, 'data': f"data/{args.id}.json"}
    existing = [c for c in reg.get('conferences', []) if c.get('id') == args.id]
    if existing:
        existing[0].update(entry)
        action = '갱신'
    else:
        reg.setdefault('conferences', []).append(entry)
        action = '추가'

    if args.default or 'default' not in reg:
        reg['default'] = args.id

    confs_idx.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"      학회 {action}: {args.id}  (default: {reg['default']})")

    print(f"[4/4] 완료")
    print()
    print(f"빌드 결과: {out_json}")
    print(f"URL 형식:  ?conf={args.id}")
    print()
    print(f"다음 단계: data/{args.id}.json + conferences.json을 GitHub에 push.")


if __name__ == '__main__':
    main()
