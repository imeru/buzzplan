#!/usr/bin/env python3
"""
migrate_v2.py — data/*.json 스키마 v1 → v2 일괄 변환 (일회성).

변환 내용은 parser_utils.finalize_v2 참조. 학회별 timezone/venue/pm_threshold는
아래 CONF_META에 명시. 이미 v2인 파일은 건너뜀.

사용: python3 migrate_v2.py [--dry-run]
"""
import argparse
import json
import pathlib
import sys

from parser_utils import finalize_v2, validate_v2, SCHEMA_VERSION

# 학회별 메타. pm_threshold: h<threshold를 오후로 간주 (12시간제 소스만 >0).
CONF_META = {
    'iaqvec-2026': {
        'timezone': 'America/Los_Angeles',  # USC (SGM/GFS/VHE)
        'pm_threshold': 8,                  # PDF가 "1:30"=오후 표기
        'venue': {
            'walk': {
                'same_room': 0, 'same_floor': 2, 'same_building': 4,
                'cross_building': 8,
                'pairs': [{'between': ['SGM', 'GFS'], 'min': 7}],
                'building_min': {'VHE': 10},
            }
        },
    },
    'sarek-2025-winter': {'timezone': 'Asia/Seoul', 'pm_threshold': 0},
    'sarek-2025-summer': {'timezone': 'Asia/Seoul', 'pm_threshold': 0},
    'sarek-2026-summer': {'timezone': 'Asia/Seoul', 'pm_threshold': 0},
}

DEFAULT_META = {'timezone': None, 'pm_threshold': 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    data_dir = pathlib.Path(__file__).parent / 'data'
    failed = False

    for path in sorted(data_dir.glob('*.json')):
        doc = json.loads(path.read_text(encoding='utf-8'))
        cid = doc.get('conference', {}).get('id', path.stem)

        if doc.get('schema_version') == SCHEMA_VERSION:
            print(f"[skip] {path.name}: 이미 v{SCHEMA_VERSION}")
            continue

        meta = CONF_META.get(cid, DEFAULT_META)
        finalize_v2(doc,
                    timezone=meta.get('timezone'),
                    pm_threshold=meta.get('pm_threshold', 0),
                    venue=meta.get('venue'))

        problems = validate_v2(doc)
        if problems:
            failed = True
            print(f"[FAIL] {path.name}: 검증 실패 {len(problems)}건")
            for p in problems[:10]:
                print(f"       - {p}")
            continue

        n_s, n_p = len(doc['sessions']), len(doc['papers'])
        if args.dry_run:
            print(f"[dry ] {path.name}: v2 변환 가능 (sessions={n_s}, papers={n_p}, tz={meta.get('timezone')})")
        else:
            path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"[ok  ] {path.name}: v2 저장 (sessions={n_s}, papers={n_p}, tz={meta.get('timezone')})")

    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
