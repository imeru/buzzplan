# CLAUDE.md — 프로젝트 컨텍스트 (Claude Code용)

이 파일은 Claude Code가 프로젝트를 빠르게 파악하도록 돕는 핸드오프 문서입니다.

## 무엇을 만드는 프로젝트인가

**BuzzPlan (버즈플랜)** — 학회 일정·동선 도우미.

학회 프로그램북 PDF에서 세션·발표 정보를 추출해, 사용자가 듣고 싶은 발표를
고르면 개인 일정과 발표장 동선을 계획해 주는 **단일 페이지 웹 도구**.
여러 학회를 한 URL에서 `?conf=<id>`로 전환해 다룬다.

로고: `assets/buzzplan-logo.png` (1x), `assets/buzzplan-logo@2x.png` (retina).

- 배포: GitHub Pages — `https://imeru.github.io/buzzplan/`
- 백엔드 없음. 정적 호스팅 + 브라우저 localStorage만 사용.

## 아키텍처

```
index.html          단일 도구 (HTML/CSS/JS 한 파일). 부팅 시 conferences.json + data/<id>.json을 fetch.
conferences.json    학회 목록 + default. 드롭다운·라우팅의 소스.
data/<id>.json      학회별 데이터 (parser 산출물, 스키마 v2). { schema_version, conference, venue?, sessions, papers }
parser.py           IAQVEC·IBPSA 형식(세로 1단, 표) 파서
parser_sarek.py     SAREK 동계(가로 2단 컬럼) 파서
parser_sarek_summer.py  SAREK 하계(세로 1단, 다일자) 파서
parser_llm.py       LLM 범용 추출기 (Tier 2). 처음 보는 레이아웃용. Claude API 필요
parser_utils.py     파서 공통: 스키마 v2 정규화(finalize_v2)·검증(validate_v2)
migrate_v2.py       data/*.json v1→v2 일괄 변환 (일회성; 이미 실행됨)
build.py            PDF→JSON(+v2 검증)→conferences.json 등록 자동화
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
| iaqvec-2026 | IAQVEC 2026 | parser.py | 60세션/321발표. 발표 시간=세션÷15분. venue.walk 보유 |
| sarek-2025-winter | 대한설비공학회 2025 동계 | parser_sarek.py | 34세션/159발표. 발표별 명시 시간 |
| sarek-2025-summer | 대한설비공학회 2025 하계 | parser_sarek_summer.py | 66세션/312발표. 2일·다회장 |
| sarek-2026-summer | 대한설비공학회 2026 하계 | parser_sarek_summer.py | default. 76세션/407발표 (포스터 2세션 67편은 Claude 직접 추출로 추가). `--day-fix 19:25` 필요 |

## 데이터 스키마 (v2)

```json
{
  "schema_version": 2,
  "conference": { "id": "...", "name": "...", "timezone": "Asia/Seoul" },
  "venue": {                              // 선택: 발표장 간 도보시간 (walkMinutes가 소비)
    "walk": {
      "same_room": 0, "same_floor": 2, "same_building": 4, "cross_building": 8,
      "pairs": [{ "between": ["SGM", "GFS"], "min": 7 }],
      "building_min": { "VHE": 10 }
    }
  },
  "sessions": [{
    "id": "1-1", "block": 1, "day": 2, "date": "2026-05-19",
    "track_title": "...", "start": "11:00", "end": "12:30", "type": "oral",
    "building": "SGM", "room": "123", "floor": 1, "chair": "..."
  }],
  "papers": [{
    "paper_no": "26", "session_id": "1-1",
    "authors": "...", "title": "...",
    "start": "11:00", "end": "11:15"   // 선택: 명시 시간. 없으면 세션÷15분 자동
  }]
}
```

v2 규칙: 시간은 **24시간제 HH:MM**, 날짜는 **ISO 8601**. 모든 파서가 출력 직전
`parser_utils.finalize_v2()`로 보장하고, build.py가 `validate_v2()`로 강제한다.
v1 레거시 데이터(12시간제 "1:30"=오후, M/D/YYYY 날짜)는 index.html이
`schema_version` 부재를 보고 옛 휴리스틱(h<8→+12)으로 처리한다.

## index.html 주요 구조 (JS)

- `bootApp()` — conferences.json + data fetch → initState → renderAll → 자동 스크롤 + startNowTimer
- **i18n** — 소스 문자열은 한국어. `?lang=en`(또는 저장된 설정)이면 `t(key)` + `applyStaticLang()`으로 영어 표시. 헤더 🌐 버튼으로 토글
- **timezone 인지 상태** — `nowParts()`가 `conference.timezone` 기준 현지 시각을 계산 → `sessionStatus()`의 past/current/upcoming이 학회 현지 기준 (tz 없거나 무효하면 기기 로컬 폴백)
- **세션 타입 뱃지** — `session.type`이 poster/keynote/social/break면 세션 헤더에 뱃지. poster는 `paperTime()`에서 세션 전체 시간 공유(kind=shared)
- `state` — selected/notes/필터/뷰 등. 학회별 localStorage 네임스페이스 `cs:<confId>:*`
- `renderSessions()` — 둘러보기 탭. 필터(검색·Day·시간범위·트랙·건물) + 현재시각 상태(past/current/upcoming)
- `renderItinerary()` — 내 일정 탭. 리스트/시간표(grid) 토글. 다중 방 슬롯 타임라인 + hop 힌트
- `paperTime(session, paper, idx, total)` — 발표별 시간. 우선순위: paper.start/end > paper_no(시간형) > 세션÷15분(PAPER_MINUTES)
- `sessionStatus(s, now)` — past-day/future-day/past/current/upcoming
- `startNowTimer()` — 30초마다 상태 변화 감지해 재렌더 (메모 입력 중이면 건너뜀)

## 새 학회 추가

```bash
# Tier 1: 알려진 형식이면 규칙 파서 (무료·결정적)
python3 build.py /path/to/new.pdf --id iaqvec-2028 --name "IAQVEC 2028"
python3 build.py /path/to/sarek-w.pdf --parser parser_sarek.py --id sarek-2026-winter --name "..."
python3 build.py /path/to/sarek-s.pdf --parser parser_sarek_summer.py --id sarek-2026-summer --name "..." --year 2026 --month 6

# Tier 2: 처음 보는 형식이면 LLM 추출 (ANTHROPIC_API_KEY 필요, 비용 발생)
export ANTHROPIC_API_KEY=sk-ant-...
python3 parser_llm.py /path/to/new.pdf --id x --name "X" --max-pages 4  # 파일럿 먼저
python3 build.py /path/to/new.pdf --parser parser_llm.py --id x --name "X" --timezone Asia/Seoul
```

LLM 추출은 누락·오인식 가능 → --dry-run 카운트를 프로그램북 목차와 대조 + 스팟체크 필수.

build.py가 data/<id>.json 생성 + conferences.json 등록까지 자동 처리.
이후 변경된 두 파일을 git push하면 사이트에 즉시 반영. index.html은 손댈 필요 없음.

검증: `python3 build.py ... --dry-run` 으로 sessions/papers 수와 orphan paper를 먼저 확인.

## 알려진 제한

- SAREK 하계 규칙 파서: 일부 특별세션(9-D, 10-D 등)과 포스터 세션은 변형 레이아웃이라 누락 가능.
  (2026 하계 포스터 67편은 Tier 2 방식으로 수동 추가 완료. 2025 하계 포스터는 여전히 누락.)
- 일부 발표는 PDF 렌더링이 글자 단위로 쪼개져 추출됨 → `consolidate_split_chars()`로 보정(gap≤0.5pt 병합).
- 발표 시간 균등 분할이 아닌 고정 15분(PAPER_MINUTES). 발표 수 적은 세션은 일찍 종료로 표시.

## 다음에 해볼 만한 작업 (백로그)

- parser_llm.py **라이브 검증** — API 키로 실제 PDF 파일럿 실행 후 규칙 파서 결과와 대조 (코드는 완성, 미실행)
- 웹 프로그램 페이지(HTML)·Excel/CSV 임포터 — PDF 외 입력 소스
- 세 파서의 레이아웃 헬퍼(group_rows, consolidate_split_chars, is_skip_row)도 parser_utils.py로 추출 (v2 정규화는 완료)
- SAREK 포스터 세션 전용 파서 (또는 Tier 2로 처리 — 2026 하계는 후자로 완료)
- 발표 시작 5분 전 알림 (Notification API)
- 학회 간 비교 모드 / 통합 통계
- 시간 범위 필터 프리셋(오전만/오후만) + localStorage 기억
- i18n 잔여: JSON 임포트 오류·공유 충돌 confirm 등 저빈도 다이얼로그는 아직 한국어 고정

## 개발 워크플로

1. `python3 -m http.server 8080` 로 로컬 확인
2. 변경 후 git commit & push → GitHub Pages 1~2분 내 반영
3. 캐시 강하므로 테스트 시 강력 새로고침(Cmd+Shift+R)
