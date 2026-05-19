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


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pdf', help='학회 스케줄 PDF 파일 경로')
    ap.add_argument('--id',   required=True, help='학회 ID (소문자·하이픈, 예: iaqvec-2028)')
    ap.add_argument('--name', required=True, help='학회 표시명')
    ap.add_argument('--parser', default='parser.py',
                    help='사용할 파서 스크립트 (기본: parser.py)')
    ap.add_argument('--default', action='store_true',
                    help='이 학회를 conferences.json의 default로 지정')
    ap.add_argument('--dry-run', action='store_true',
                    help='검증만; 파일은 수정하지 않음')
    args = ap.parse_args()

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
