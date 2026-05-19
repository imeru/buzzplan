#!/usr/bin/env python3
"""
build.py — 새 학회 PDF로 도구를 빌드.

PDF에서 schedule.json을 만들고 그 결과를 index.html 안에 임베드합니다.
이 스크립트 하나만 실행하면 학생들에게 공유할 index.html이 갱신됩니다.

사용 예:
    # 신규 학회 빌드 (id·이름은 학회마다 고유하게)
    python3 build.py /path/to/new_pdf.pdf --id iaqvec-2028 --name "IAQVEC 2028"

    # 같은 학회의 스케줄이 갱신되어 다시 빌드
    python3 build.py /path/to/updated.pdf --id iaqvec-2026 --name "IAQVEC 2026"

    # 검증만 (HTML은 건드리지 않음)
    python3 build.py /path/to/pdf.pdf --id test --name "Test" --dry-run

이 도구는 같은 폴더 안의 parser.py와 index.html을 사용합니다.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pdf', help='학회 스케줄 PDF 파일 경로')
    ap.add_argument('--id',   required=True, help='학회 ID (소문자·하이픈, 예: iaqvec-2028)')
    ap.add_argument('--name', required=True, help='학회 표시명 (예: "IAQVEC 2028")')
    ap.add_argument('--out-json', default='schedule.json',
                    help='중간 산출 JSON 경로 (기본: schedule.json)')
    ap.add_argument('--html', default='index.html',
                    help='임베드할 HTML 경로 (기본: index.html)')
    ap.add_argument('--dry-run', action='store_true',
                    help='HTML을 수정하지 않고 검증만')
    args = ap.parse_args()

    here = pathlib.Path(__file__).parent
    parser_py = here / 'parser.py'
    html_path = here / args.html
    json_path = here / args.out_json

    if not parser_py.exists():
        sys.exit(f"  parser.py를 찾을 수 없습니다: {parser_py}")
    if not html_path.exists():
        sys.exit(f"  HTML 파일을 찾을 수 없습니다: {html_path}")
    if not pathlib.Path(args.pdf).exists():
        sys.exit(f"  PDF를 찾을 수 없습니다: {args.pdf}")

    # 1. parser.py 실행
    print(f"[1/3] PDF 파싱: {args.pdf}")
    cmd = [sys.executable, str(parser_py), args.pdf,
           '--id', args.id, '--name', args.name, '--out', str(json_path)]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(f"  파서 실행 실패 (exit code {e.returncode})")

    # 2. JSON 검증
    print(f"[2/3] JSON 검증")
    data = json.loads(json_path.read_text(encoding='utf-8'))
    n_sess = len(data.get('sessions', []))
    n_pap  = len(data.get('papers', []))
    print(f"      sessions={n_sess}, papers={n_pap}")
    if n_sess == 0 or n_pap == 0:
        sys.exit("  세션 또는 발표가 0건입니다. parser.py가 PDF를 잘못 인식한 것으로 보입니다.")

    sess_ids = {s['id'] for s in data['sessions']}
    orphans = [p for p in data['papers'] if p['session_id'] not in sess_ids]
    if orphans:
        print(f"      [경고] orphan papers: {len(orphans)} (세션 ID가 일치하지 않음)")
        print(f"             해당 paper_no: {[p['paper_no'] for p in orphans[:10]]}")
        print(f"             parser.py의 SESS_RE / TIME_LOC_RE 보강이 필요할 수 있습니다.")

    if args.dry_run:
        print("[3/3] dry-run: HTML은 수정하지 않음")
        return

    # 3. HTML에 JSON 임베드
    print(f"[3/3] HTML 임베드: {html_path}")
    embedded = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    html = html_path.read_text(encoding='utf-8')
    new_html, n = re.subn(
        r'let DATA = \{.*?\};\s*\n',
        f'let DATA = {embedded};\n',
        html, count=1, flags=re.DOTALL,
    )
    if n != 1:
        sys.exit("  HTML에서 'let DATA = {...};' 위치를 찾지 못했습니다.")
    html_path.write_text(new_html, encoding='utf-8')

    print()
    print(f"빌드 완료: {html_path}")
    print(f"   학회: {args.name}  (id={args.id})")
    print(f"   세션 {n_sess}개, 발표 {n_pap}개 임베드 완료.")
    print()
    print("다음 단계: 변경된 index.html을 GitHub 레포에 업로드(또는 git push).")


if __name__ == '__main__':
    main()
