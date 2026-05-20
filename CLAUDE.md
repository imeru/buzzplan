# CLAUDE.md — 프로젝트 컨텍스트 (Claude Code용)

이 파일은 Claude Code가 프로젝트를 빠르게 파악하도록 돕는 핸드오프 문서입니다.

## 무엇을 만드는 프로젝트인가

학회 프로그램북 PDF에서 세션·발표 정보를 추출해, 사용자가 듣고 싶은 발표를
고르면 개인 일정과 발표장 동선을 계획해 주는 **단일 페이지 웹 도구**.
여러 학회를 한 URL에서 `?conf=<id>`로 전환해 다룬다.

- 배포: GitHub Pages — `https://imeru.github.io/conference-planner/`
- 백엔드 없음. 정적 호스팅 + 브라우저 localStorage만 사용.

## 아키텍처

```
index.html          단일 도구 (HTML/CSS/JS 한 파일). 부팅 시 conferences.json + data/<id>.json을 fetch.
conferences.json    학회 목록 + default. 드롭다운·라우팅의 소스.
data/<id>.json      학회별 데이터 (parser 산출물). { conference, sessions, papers }
parser.py           IAQVEC·IBPSA 형식(세로 1단, 표) 파서
parser_sarek.py     SAREK 동계(가로 2단 컬럼) 파서
parser_sarek_summer.py  SAREK 하계(세로 1단, 다일자) 파서
build.py            PDF→JSON→conferences.json 등록 자동화
```

데이터는 `index.html`에 임베드돼 있지 않고 런타임에 fetch한다. 따라서
**로컬에서 file://로 열면 동작하지 않는다.** 반드시 HTTP 서버로 띄운다:

```bash
python3 -m http.server 8080
# http://localhost:8080/  또는  ?conf=sarek-2025-winter
```

## 현재 등록된 학회

| id | 이름 | 형식 | 비고 |
|---|---|---|---|
| iaqvec-2026 | IAQVEC 2026 | parser.py | default. 60세션/321발표. 발표 시간=세션÷15분 |
| sarek-2025-winter | 대한설비공학회 2025 동계 | parser_sarek.py | 34세션/159발표. 발표별 명시 시간 |
| sarek-2025-summer | 대한설비공학회 2025 하계 | parser_sarek_summer.py | 66세션/312발표. 2일·다회장 |

## 데이터 스키마

```json
{
  "conference": { "id": "...", "name": "..." },
  "sessions": [{
    "id": "1-1", "block": 1, "day": 2, "date": "5/19/2026",
    "track_title": "...", "start": "11:00", "end": "12:30",
    "building": "SGM", "room": "123", "floor": 1, "chair": "..."
  }],
  "papers": [{
    "paper_no": "26", "session_id": "1-1",
    "authors": "...", "title": "...",
    "start": "11:00", "end": "11:15"   // 선택: 명시 시간. 없으면 세션÷15분 자동
  }]
}
```

시간 표기는 12시간·AM/PM 없음 (예: "1:30"은 오후 1:30). `timeToMin()`이 h<8이면 +12로 처리.

## index.html 주요 구조 (JS)

- `bootApp()` — conferences.json + data fetch → initState → renderAll → 자동 스크롤 + startNowTimer
- `state` — selected/notes/필터/뷰 등. 학회별 localStorage 네임스페이스 `cs:<confId>:*`
- `renderSessions()` — 둘러보기 탭. 필터(검색·Day·시간범위·트랙·건물) + 현재시각 상태(past/current/upcoming)
- `renderItinerary()` — 내 일정 탭. 리스트/시간표(grid) 토글. 다중 방 슬롯 타임라인 + hop 힌트
- `paperTime(session, paper, idx, total)` — 발표별 시간. 우선순위: paper.start/end > paper_no(시간형) > 세션÷15분(PAPER_MINUTES)
- `sessionStatus(s, now)` — past-day/future-day/past/current/upcoming
- `startNowTimer()` — 30초마다 상태 변화 감지해 재렌더 (메모 입력 중이면 건너뜀)

## 새 학회 추가

```bash
# 형식에 맞는 파서 선택
python3 build.py /path/to/new.pdf --id iaqvec-2028 --name "IAQVEC 2028"
python3 build.py /path/to/sarek-w.pdf --parser parser_sarek.py --id sarek-2026-winter --name "..."
python3 build.py /path/to/sarek-s.pdf --parser parser_sarek_summer.py --id sarek-2026-summer --name "..." --year 2026 --month 6
```

build.py가 data/<id>.json 생성 + conferences.json 등록까지 자동 처리.
이후 변경된 두 파일을 git push하면 사이트에 즉시 반영. index.html은 손댈 필요 없음.

검증: `python3 build.py ... --dry-run` 으로 sessions/papers 수와 orphan paper를 먼저 확인.

## 알려진 제한

- SAREK 하계: 일부 특별세션(9-D, 10-D 등)과 포스터 세션(25-S-240~243, 270~273)은 변형 레이아웃이라 누락 가능.
- 일부 발표는 PDF 렌더링이 글자 단위로 쪼개져 추출됨 → `consolidate_split_chars()`로 보정(gap≤0.5pt 병합).
- 발표 시간 균등 분할이 아닌 고정 15분(PAPER_MINUTES). 발표 수 적은 세션은 일찍 종료로 표시.

## 다음에 해볼 만한 작업 (백로그)

- 세 파서의 공통 헬퍼(group_rows, consolidate_split_chars, is_skip_row)를 parser_utils.py로 추출
- SAREK 포스터 세션 전용 파서
- 발표 시작 5분 전 알림 (Notification API)
- 학회 간 비교 모드 / 통합 통계
- 시간 범위 필터 프리셋(오전만/오후만) + localStorage 기억

## 개발 워크플로

1. `python3 -m http.server 8080` 로 로컬 확인
2. 변경 후 git commit & push → GitHub Pages 1~2분 내 반영
3. 캐시 강하므로 테스트 시 강력 새로고침(Cmd+Shift+R)
