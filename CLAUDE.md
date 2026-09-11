# CLAUDE.md : 프로젝트 컨텍스트 (Claude Code용)

이 파일은 어떤 모델이 읽어도 이 프로젝트에서 같은 품질로 일할 수 있게 하는 핸드오프 문서다.
여기 없는 관습은 존재하지 않는 것으로 간주하고, 애매하면 사용자에게 묻는다.

## 1. 무엇을 만드는 프로젝트인가

**BuzzPlan (버즈플랜)** : 학회 일정·동선 도우미.

학회 프로그램북 PDF에서 세션·발표 정보를 추출해, 사용자가 듣고 싶은 발표를
고르면 개인 일정과 발표장 동선을 계획해 주는 **단일 페이지 웹 도구**.
여러 학회를 한 URL에서 `?conf=<id>`로 전환한다.

- 배포: GitHub Pages `https://imeru.github.io/buzzplan/` (push하면 1~2분 내 반영, 즉시 아님)
- 사용자: 현재 연구실 약 10명. 학회 공개 시 수백 명까지 무료 티어로 감당하도록 설계됨
- 백엔드 없음. 정적 호스팅 + localStorage(게스트) + **Firebase 계정 동기화(선택)**
- Firebase 프로젝트: `buzzplan` (사용자 구글 계정 소유). 콘솔 작업(규칙 배포, 도메인 승인)은
  사용자만 할 수 있으므로, 필요 시 정확한 클릭 경로를 안내한다

## 2. 하드 룰 (어기면 기능이 조용히 죽는다)

1. **file://로 열면 동작하지 않는다.** 데이터를 런타임에 fetch하므로 반드시 HTTP 서버로 띄운다:
   `python3 -m http.server 8080`
2. **스키마 v2 계약**: 시간은 24시간제 `HH:MM`, 날짜는 ISO `YYYY-MM-DD`.
   모든 파서는 출력 직전 `parser_utils.finalize_v2()` 호출, build.py가 `validate_v2()`로 강제한다
3. **단일 건물 학회의 building 값은 전 세션 동일해야 한다** (SAREK은 전부 `"회장"`).
   하나라도 다른 값이 섞이면 `_useRoomLevelBuilding`이 꺼져 회장별 필터가 무너진다.
   포스터 등 특수 장소도 building은 `"회장"` 유지, room으로만 구분 (예: room `"포스터"`)
4. **사용자 노출 문자열은 한국어가 소스**이고, 새로 추가할 때 반드시
   `I18N_KO`와 `I18N_EN` 양쪽에 키를 넣고 `t(key)`로 쓴다.
   정적 HTML 문자열이면 `applyStaticLang()`에도 영어 치환을 추가한다
5. **선택, 별점, 메모, 꼭 듣기(⭐)를 바꾸는 모든 코드 경로는 `touch(key)`를 호출해야 한다.**
   touch가 빠지면 그 변경은 다른 기기로 동기화되지 않는다.
   단, 원격 수신 적용부(`applyRemoteItems`)에서는 touch 금지 (push 루프 발생)
6. **모바일 로그인은 `signInWithPopup`만 쓴다.** `signInWithRedirect`는 호스팅 도메인
   (imeru.github.io) ≠ authDomain(buzzplan.firebaseapp.com) 환경에서 브라우저의
   서드파티 스토리지 차단으로 로그인이 소실된다 (실기기에서 확인된 함정)
7. **프로그램북 PDF는 커밋 금지** (`*.pdf`는 .gitignore). 소스 PDF는 로컬 보관
8. 파괴적 작업(파일·데이터 삭제, git 강제 푸시, 과금 발생, 아키텍처 전환)은 사용자 확인 후 진행

## 3. 파일 지도

```
index.html          도구 본체 (HTML/CSS/JS 한 파일, 약 2,600줄). 부팅 시 conferences.json + data/<id>.json fetch
conferences.json    학회 목록 + default. 드롭다운·라우팅의 소스
data/<id>.json      학회별 데이터 (스키마 v2)
firestore.rules     Firestore 보안 규칙. 콘솔에 수동 배포 (본인 uid 경로만 허용)
parser.py           IAQVEC·IBPSA 형식(세로 1단, 표) 규칙 파서
parser_sarek.py     SAREK 동계(가로 2단 컬럼) 규칙 파서
parser_sarek_summer.py  SAREK 하계(세로 1단, 다일자) 규칙 파서. --day-fix 옵션 있음
parser_roomvent.py  RoomVent(ConfTool 인쇄용 프로그램) 규칙 파서. 좌표가 아니라
                    글꼴 크기와 굵기로 역할(세션헤더 15pt / 메타 10.6pt 이탤릭 /
                    시간마커 9.5pt 볼드 / 제목 11pt 볼드 / 저자 10pt)을 구분한다
parser_utils.py     파서 공통: v2 정규화(finalize_v2)·검증(validate_v2) + 레이아웃 헬퍼
                    (group_rows, consolidate_split_chars, is_skip_row 등. 상수는 파라미터로 주입)
parser_llm.py       LLM 범용 추출기. 코드 완성·미가동 (API 키 필요, 사용자가 당분간 보류 결정)
migrate_v2.py       v1→v2 일괄 변환 (일회성, 실행 완료. 참고용으로만 유지)
build.py            PDF→JSON→검증→conferences.json 등록 자동화. --dry-run 지원
map-editor.html     회장 지도 저작 도구 (내부용, 앱에서 링크하지 않음). 지도 이미지를 끌어다 놓고
                    두 점 실거리로 축척을 잡고 방마다 핀을 찍어 venue.maps JSON을 뽑는다.
                    로컬 서버로 열 것 (data/*.json을 fetch한다). Chrome이나 Edge에서
                    저장소 루트를 연결하면(File System Access API) 이미지는 assets/maps/에,
                    venue JSON은 data/<id>.json에 직접 쓴다. 자세한 계약은 13장 참조
assets/             로고. 헤더는 buzzplan-bee.png(+@2x), buzzplan-logo.png(+@2x)도 참조됨
assets/maps/        회장 도면 이미지. venue.maps[].image가 여기를 가리킨다 (커밋 대상)
README.md           사용자용 안내. 학회 표(세션/발표 수)를 여기와 중복 보유하므로 함께 갱신할 것
```

## 4. 데이터 스키마 (v2)

```json
{
  "schema_version": 2,
  "conference": { "id": "...", "name": "...", "timezone": "Asia/Seoul" },
  "venue": {
    "walk": {
      "same_room": 0, "same_floor": 2, "same_building": 4, "cross_building": 8,
      "pairs": [{ "between": ["SGM", "GFS"], "min": 7 }],
      "building_min": { "VHE": 10 }
    },
    "walk_model": { "speed_m_per_min": 66, "detour": 1.3, "floor_min": 1.5 },
    "maps": [{
      "building": "CTU", "floor": 1, "label": "CTU 1층",
      "image": "assets/maps/ctu-1f.png",
      "width_px": 1600, "height_px": 1100, "width_meters": 82,
      "pins": [{ "room": "B 168", "x": 430, "y": 720 }]
    }]
  },
  "sessions": [{
    "id": "1-1", "block": 1, "day": 2, "date": "2026-05-19",
    "track_title": "...", "start": "11:00", "end": "12:30", "type": "oral",
    "building": "SGM", "room": "123", "floor": 1, "chair": "..."
  }],
  "papers": [{
    "paper_no": "26", "session_id": "1-1",
    "authors": "...", "title": "...",
    "start": "11:00", "end": "11:15"
  }]
}
```

필드 주의사항 (스키마만 보면 틀리기 쉬운 부분):

- `venue.walk`: 단위는 분. 없으면 기본값(0/2/4/8) 사용. `building_min`은 "이 건물이 끼면 N분".
  현재 iaqvec-2026의 값(7분/10분 등)은 실측이 아니라 **추정치**다. 정밀도를 믿지 말 것
- `venue.maps`: 선택 사항. 없으면 지도 기능 전체가 꺼지고 동작이 이전과 같다.
  좌표는 **원본 이미지 픽셀** 기준이고 `width_px`/`height_px`는 그 이미지의 실제 크기여야 한다
  (이미지를 리사이즈하면 핀이 전부 어긋난다). `pins[].room`은 세션의 `room` 값과 정확히 같아야
  매칭된다. 작성은 `map-editor.html`로 한다
- `venue.maps[].width_meters`: 도면 가로가 실제 몇 미터인가. **이 키가 없으면 표시 전용**이고
  거리 계산을 하지 않는다. 비례가 맞지 않는 안내형 일러스트 지도에는 일부러 넣지 말 것
- `venue.walk_model`: 거리를 분으로 바꾸는 상수. 기본 66 m/min(혼잡한 학회장 기준 1.1 m/s),
  우회 계수 1.3, 층당 1.5분. 지도가 있을 때만 쓰인다
- `session.day`: 정렬·필터용 숫자일 뿐 의미가 학회마다 다르다
  (IAQVEC: 행사 N일차, SAREK: 날짜의 일). 같은 학회 안에서만 일관되면 된다
- `session.type`: `oral`(기본)·`poster`·`keynote`·`social`·`break`.
  oral 외에는 세션 헤더에 뱃지가 붙고, poster는 발표들이 세션 전체 시간을 공유한다
- `paper.paper_no`가 `"HH:MM-HH:MM"` 형태면 그 시간 범위가 발표 시간으로 쓰인다
  (전문가강연·교육 등 번호 없는 항목의 관례)
- `paper.start/end`가 없으면 세션 시작부터 15분(`PAPER_MINUTES`) 단위로 자동 배정
- v1 레거시(12시간제, M/D/YYYY)는 `schema_version` 부재를 보고 index.html이 구식 휴리스틱으로 처리

`conferences.json`의 항목 스키마는 따로다. 키 순서는 `id, name, start, data`다.

```json
{ "default": "roomvent-2026",
  "conferences": [
    { "id": "roomvent-2026", "name": "RoomVent 2026",
      "start": "2026-09-15", "data": "data/roomvent-2026.json" }
  ] }
```

- `start`는 개최 첫날(ISO). **학회 드롭다운 정렬 키**이고, build.py가 등록할 때
  `sessions[].date`의 최소값에서 뽑아 넣는다. 없으면 index.html이 id의 4자리 연도로
  폴백하므로 같은 해의 하계(6월)와 동계(11월)가 이름순으로 섞인다
- 파일 자체도 `start` 내림차순으로 정렬해 둔다 (build.py가 등록 후 재정렬한다).
  사람이 읽을 때와 diff를 볼 때 드롭다운 순서와 일치하게 하려는 것이다

## 5. 등록된 학회 (현행)

| id | 이름 | 파서 | 규모 | 비고 |
|---|---|---|---|---|
| iaqvec-2026 | IAQVEC 2026 | parser.py | 60세션/321발표 | tz America/Los_Angeles. venue.walk 보유(추정치) |
| sarek-2025-winter | 설비공학회 2025 동계 | parser_sarek.py | 34세션/159발표 | 발표별 명시 시간 |
| sarek-2025-summer | 설비공학회 2025 하계 | parser_sarek_summer.py | 66세션/312발표 | 포스터 누락 (알려진 제한) |
| sarek-2026-summer | 설비공학회 2026 하계 | parser_sarek_summer.py | 76세션/407발표 | 포스터 67편은 Tier 2로 추가. 재파싱 시 `--day-fix 19:25` 필수. **venue.maps 보유**(알펜시아 1층과 2층, 축척 0.067 m/px) |
| roomvent-2026 | RoomVent 2026 | parser_roomvent.py | 59세션/269발표 | **default**. tz Europe/Prague. 단일 건물 `CTU`, 방으로만 구분. 발표번호 없어 paper_no는 `<세션ID>-<순번>` |

이 표의 숫자가 바뀌는 작업을 했으면 이 파일과 **README.md의 학회 표**도 같이 갱신한다.

## 6. 새 학회 추가 (결정 트리)

```
새 PDF
 ├─ 알려진 형식인가? ──→ Tier 1: 규칙 파서 (무료·결정적)
 │    python3 build.py new.pdf --parser <parser_*.py> --id <id> --name "..." [--year --month]
 │    검증: --dry-run으로 세션/발표 수·orphan 먼저 확인
 │
 ├─ 처음 보는 형식? ──→ Tier 2 (현재 표준 관행): PDF를 Claude Code 대화에 첨부받아
 │    Claude가 직접 스키마 v2 JSON을 추출한다. API 키·추가 비용 없음.
 │    절차: 추출 → validate_v2 통과 → 발표번호 결번 검사 → 프로그램북 목차와
 │    세션/발표 수 대조 → 무작위 스팟체크 → data/<id>.json + conferences.json 등록
 │    관례: Q&A 행도 발표로 포함, 번호 없는 항목은 paper_no에 시간 범위
 │
 └─ 대량 자동화가 필요해지면 ──→ parser_llm.py (ANTHROPIC_API_KEY 필요, 종량 과금.
      사용자가 보류 중이므로 먼저 확인할 것)
```

등록 후: data/<id>.json + conferences.json 두 파일만 커밋하면 된다. index.html 무관.

## 7. 계정 동기화 (Firebase) 동작 계약

```
게스트: localStorage만 (cs:<confId>:selected / :notes / :stamps / :collapsed)
로그인: 위 + Firestore users/<uid>/confs/<confId> 문서 1개
        { items: { "<sessionId>#<paperNo>": {s: 0|1, r: 별점, n: 메모, m: 0|1(꼭 듣기), t: ms} } }
```

- **키별 LWW 병합**: 로컬 변경은 `touch(key)`가 `state.stamps`에 시각 기록 → 800ms 디바운스 후
  문서 전체 push. 원격 수신은 `remote.t > local.t`인 키만 적용 (적용 시 stamps 직접 갱신, touch 금지)
- **삭제 전파**: 선택 해제해도 stamps가 남아 tombstone(s:0) 역할
- **에코 가드**: onSnapshot에서 `hasPendingWrites`면 무시. 로그인 직후 첫 스냅샷은 토스트 억제
- **서버본을 보기 전에는 절대 push하지 않는다** (`_serverSeen` 게이트). 문서를 통째로 `set()`하는
  구조라, 서버본을 못 본 클라이언트의 push 한 번이 다른 기기의 항목 전부를 지운다.
  오프라인 캐시(`enablePersistence`)가 켜져 있어 `onSnapshot`의 첫 스냅샷은 캐시에서
  "문서 없음"으로 올 수 있으므로, 업로드 허용 판정은 리스너가 아니라 `docRef.get()`의
  `metadata.fromCache === false`로 한다. 서버본 도착 전 push 요청은 `_pushQueued`로 보류한다.
  실제로 이 경로에서 데이터 전멸이 보고되었다 (2026-09-11)
- **서버 읽기는 `get({ source: 'server' })`로 강제한다.** 기본 `get()`은 서버에 닿지 못해도
  캐시본으로 resolve되므로, 캐시가 빈 브라우저에서는 "계정에 아무것도 없다"와
  "서버를 읽지 못했다"가 화면상 구별되지 않는다. 실패하면 `_syncOffline`을 켜서 로그인 버튼에
  드러내고(`sync_offline`), 화면은 캐시본으로 채우되 **업로드는 계속 금지**한다.
  여기서 `_serverSeen`을 켜면 캐시본 기준으로 원격을 덮어쓴다
- **그 서버 읽기에 타임아웃과 재시도를 건다** (`getServerWithTimeout`. 첫 시도
  `SERVER_READ_TIMEOUT_MS` 12초, 재시도 `SERVER_READ_RETRY_TIMEOUT_MS` 8초,
  `SERVER_READ_BACKOFF` `[0, 2000, 5000, 10000]`으로 시도 4회).
  `source:'server'`는 조용한 실패를 없애는 대신 **서버에 닿을 때까지 reject도 resolve도 하지 않고
  pending으로 남을 수 있다.** 사파리는 Firestore 연결이 streaming 실패 후 long-polling으로
  폴백하는 데 수 초가 걸려 이 상태에 오래 머문다. 타임아웃도 재시도도 없으면 그 pending이
  그대로 영구 빈 화면이 된다 (2026-09-11 실기기에서 `offline=false` + `serverSeen=false` +
  로컬 0건으로 관측). 지켜야 할 것 넷이다
  - 실패와 타임아웃에서 `_serverSeen`을 켜지 않는다. 업로드는 끝까지 금지하고 화면만 캐시본으로
    채운다 (캐시 폴백 읽기는 첫 실패에서만 한 번)
  - 리스너가 먼저 서버본을 받으면(`_serverSeen`) 루프를 즉시 빠져나간다. 늦게 발화한 타임아웃이
    `_syncOffline`을 켜면 정상 동작 중인데도 경고가 뜨므로, catch 진입 직후에도 `_serverSeen`을
    다시 보고 `state='superseded'`로 남기고 반환한다
  - `permission-denied`는 재시도해도 결과가 같다. 즉시 `reportSyncError`로 알리고 멈춘다
  - **타임아웃에서는 `_syncOffline`을 켜지 않는다.** 정말 연결이 없으면 SDK가 곧바로
    `code: 'unavailable'`로 reject하므로(그 경로에서는 즉시 켠다), 타임아웃은 "연결 수립이
    느리다"는 뜻일 뿐이다. 사파리는 로그인마다 첫 읽기가 늦어 여기서 켜면 거짓 경고가 매번 뜬다
  - 진행 상태는 `_syncRead = {state, tries, ms, err, startedAt}`에 남기고, 상태 전이는
    `_syncReadLog`에 누적한다(`noteSyncRead`가 둘을 같이 쓴다. 14건까지 보관). `state`는
    `idle`/`pending`/`ok`/`timeout`/`error`/`superseded`/`listener-ok`. 진단 패널이 "지연 중"과
    "영구 실패"를 가르는 유일한 근거다. 셋을 지킬 것이다
    - `startedAt`이 있어야 pending 중에도 경과를 보여 줄 수 있다. `ms`는 읽기가 끝날 때만
      채워지므로, pending에서 `ms=0`을 그대로 찍으면 "아직 기다리는 중"이 "즉시 끝났다"로
      읽힌다 (2026-09-11에 이 혼동으로 진단 한 판을 버렸다)
    - 첫 읽기가 타임아웃된 뒤 리스너가 서버본을 받아 복구하는 일이 사파리에서 정상적으로
      일어나므로, 그때 `onSnapshot`이 `timeout`/`error`/`pending`을 `listener-ok`로 갱신한다.
      `pending`을 빼면 리스너가 이긴 뒤에도 패널이 계속 pending을 보여 같은 오진을 낳는다
    - 전이 기록이 있어야 사용자가 **언제 복사하든** 첫 읽기의 결말이 드러난다. 점 측정만으로는
      복사 시점이 읽기 도중이면 아무것도 판정할 수 없다
- **현재 학회 문서가 비어 있으면 계정의 다른 학회를 확인한다** (`checkOtherConfs`).
  문서 경로가 `confs/<confId>`로 갈리므로 두 기기의 `?conf=`가 다르면 같은 계정인데도
  빈 화면이 나온다. 이 조회는 진단용 부가 동작이라 실패해도 본 동기화에 영향을 주지 않는다
- **모르는 원격 키는 보존한다**: push payload는 `buildLocalItems()`가 아니라 `buildPushItems()`로
  만든다. 마지막으로 본 서버본(`_remoteItems`)을 바탕에 깔고, 같은 키는 `t`가 큰 쪽을 남긴다.
  이 기기가 아직 받지 못한 다른 기기의 항목이 살아남는 유일한 장치다
- **로컬에 기록이 없는 키는 `t`가 0이어도 수용한다**: `remote.t <= localT` 조건만 쓰면
  스탬프 없이 올라간 옛 항목이 `0 <= 0`에 걸려 새 기기에 영구히 전파되지 않는다.
  단 내용이 빈 tombstone은 받을 것이 없어 건너뛴다
- **세대 번호(`_syncGen`)**: `stopSync`가 증가시켜, 구독 종료 후 뒤늦게 도착하는
  `get()`과 스냅샷 응답을 버린다 (로그아웃 직후 교차 오염 방지)
- **게스트 모드 불변 원칙**: 로그인 없으면 동작이 기존과 100% 동일해야 한다
- **오류는 표면화**: 동기화 실패는 조용히 삼키지 말고 `reportSyncError`로 (버튼 ⚠️ + 권한 오류 안내)
- **구버전 클라이언트 주의**: 문서를 통째로 쓰는 LWW라, `m`을 모르는 옛 index.html이 캐시된 기기가
  push하면 꼭 듣기 플래그가 지워진다. 캐시가 갱신되면 해소된다. 앞으로 항목 필드를 늘릴 때도 같은 성질이 따라온다
- 확장: 무료 쿼터(읽기 5만/쓰기 2만/일)로 수백 명 커버. 초과 시 Blaze 전환만 하면 됨 (구조 불변)

## 8. index.html 주요 구조 (JS)

- `bootApp()` : conferences.json + data fetch → initState → renderAll → 자동 스크롤 + startNowTimer
- **i18n**: `t(key)` + `I18N_KO`/`I18N_EN` + `applyStaticLang()`. `?lang=en` 또는 헤더 🌐 토글
- `nowParts()` : `conference.timezone` 기준 학회 현지 시각 (무효 tz는 기기 로컬 폴백, 1초 메모이즈)
- `sessionStatus(s)` : past-day/future-day/past/current/upcoming (학회 현지 기준)
- `startNowTimer()` : 다음 상태 전환 시각을 계산해 그때만 깨는 setTimeout (30초 폴링 아님).
  메모 입력 중이면 재렌더를 미룬다
- `paperTime(session, paper, idx, total)` : 발표 시간. 우선순위 paper.start/end > paper_no 시간형 >
  poster/Panel/Special은 세션 공유 > 15분 슬라이스
- `renderSessions()` 둘러보기 탭 / `renderItinerary()` 내 일정 탭 (리스트·시간표 토글, hop 힌트)
- 동기화 계층: `startSync`/`stopSync`/`schedulePush`/`applyRemoteItems`/`touch`/`reportSyncError`
- **꼭 듣기(⭐)**: `isMust`/`toggleMust`/`clearMustOnDeselect`. 상태는 notes 항목의 `must` 불리언이라
  별점과 축이 다르다 (별점은 듣고 난 뒤 평가, 꼭 듣기는 듣기 전 우선순위).
  켜면 자동으로 선택에 담기고, 선택을 해제하면 함께 꺼진다. 토글 핸들러는 전체 재렌더 대신
  해당 행이나 카드만 갱신한다 (메모 textarea 포커스 보존).
  **강조 CSS의 축 분리 계약**: 시간 상태(current/upcoming/past)와 꼭 듣기는 서로 다른 CSS 속성을
  써야 한다. 시간 상태는 시간표에서 `outline`, 내 일정 카드에서 ring(`box-shadow`)과 `opacity`를
  쓰고, 꼭 듣기는 배경과 왼쪽 띠, 굵은 제목, 배지를 쓴다. 같은 속성을 쓰면 소스 순서가 뒤인 쪽이
  앞의 표시를 지운다 (과거 사례: `.tt-cell.must`의 outline이 `.tt-cell.current`의 빨간 테두리를 먹었다).
  `renderPick`에서 상태 클래스를 붙일 때도 `pickCls +=`를 쓴다. `=`로 덮으면 must가 날아간다
- **회장 지도**: `mapsList`/`hasMaps`/`mapPins`/`pinFor`(방 → 핀 조회, 캐시 `_mapPins`)
  → `metersPerPx`/`planarMeters`(같은 건물 안에서만 픽셀 거리를 미터로) → `mapWalkMinutes`.
  `walkMinutes`의 우선순위는 (1) 다른 건물 사이의 명시된 `pairs` → (2) 지도 기반 계산 →
  (3) 기존 계층 규칙(same_room/same_floor/...)이다. 지도가 없으면 (3)만 남아 이전과 동일하다.
  `mapLink(inner, from, to)`는 `{building, room}`을 가진 객체를 받아 장소 텍스트를 지도 링크로
  감싸고, 핀이 없는 방은 평문을 그대로 돌려준다 (죽은 링크 방지). 모달은 `setupMapModal()`
- 조회 캐시 `_papersBySession` 등은 학회 전환 시 `invalidateCaches()`
- **학회 드롭다운 정렬**: `renderConfChip()`의 `confSortKey(c)`가 `conferences.json`의
  `start`를 1순위로 보고 내림차순으로 세운다(최신이 위, 오래된 것이 아래).
  `start`가 없거나 ISO 형식이 아니면 id의 연도로 폴백하고, 같은 키면 `natCompare(name)`로 가른다.
  현재 학회는 목록에서 빼고 맨 위 칩으로 따로 보여 준다
- **동기화 진단 패널 (`?debug=sync`)**: `syncDebugOn`/`mountSyncDiag`/`runSyncDiag`.
  "한 브라우저에서는 보이는데 다른 브라우저에서는 안 보인다"는 신고를 추측으로 쫓지 않기 위한
  창구다. 한 화면에서 원인 후보 셋(다른 구글 계정, 다른 `?conf=`, 서버 읽기 실패)을 가른다.
  계정 주소와 uid, `_serverSeen`/`_syncOffline`/`_pushQueued` 플래그, 현재 학회 문서의 키 수,
  계정 안의 전체 학회 문서 목록을 적고 "복사" 버튼으로 전문을 클립보드에 넣는다.
  SDK가 로드되지 않은 경우에도 떠야 하므로 호출 지점이 둘이다(인증 콜백 안과 밖).
  `server read` 줄(`readStateLine`)에 `_syncRead`를 적고, `read log` 줄(`readLogLine`)에
  `_syncReadLog`의 전이를 첫 전이 기준 상대 시각으로 늘어놓는다. 서버본을 받기 전까지는
  2.5초 간격으로 24회까지 자동 재검사해(`_diagAuto`, 재시도 예산 53초를 덮는 값) 한 번 찍은
  값이 "아직 진행 중"일 뿐인 경우와 영구 실패를 가른다. "검사" 버튼을 누르면 카운터가 0으로
  돌아간다. **패널이 스스로 발행하는 서버 읽기에는 소요 시간을 함께 적는다**
  (`this conf ... (이 읽기 Nms)`, `scan ok`). 위의 `server read`가 pending인 동안 이쪽이
  수백 ms에 끝나면 본 읽기는 느린 것이 아니라 멈춘 것이라고 가를 수 있다. 같은 이유로
  `server read`와 `read log` 두 줄은 자리만 잡아 두고 **네트워크 대기가 끝난 뒤 다시 쓴다.**
  대기 전에 한 번만 찍으면 같은 화면의 두 줄이 서로 다른 시점을 가리키면서 그 사실이
  표시되지 않는다 (2026-09-11에 이 때문에 스냅샷 하나를 판정 불가로 버렸다).
  **운영자와 개발자용이라 i18n 대상이 아니다** (12장의 부팅 오류 페이지와 같은 취급).
  라벨은 영어 키워드로 쓴다

## 9. 검증 방법 (테스트 프레임워크 없음, 아래가 관행)

```bash
# 1. JS 구문 검사 (index.html 수정 후 항상)
python3 -c "import re; html=open('index.html').read(); s=re.findall(r'<script>(.*?)</script>', html, re.S); open('/tmp/app.js','w').write('\n'.join(s))" && node --check /tmp/app.js

# 2. 데이터 검증 (데이터·파서 수정 후)
python3 build.py <pdf> --parser <parser> --id tmp --name t --dry-run   # 카운트·orphan·결번·분포 리포트

# 3. 로직 테스트: 스크래치패드에 ad-hoc node 스크립트.
#    /tmp/app.js에서 대상 함수를 문자열로 잘라 eval하고 시나리오 검증하는 패턴
#    (동기화 수정 시 최소: 양방향 반영, 원격이 이기는 경우, 삭제 전파, 에코 무시,
#     그리고 "새 기기가 서버본을 보기 전에 push하지 않는가")
#    주의: 시뮬레이션은 한 ms 안에 끝나므로 Date.now()를 단조 증가 가상 클럭으로 섀도잉해야
#    한다. 실제 클럭을 쓰면 스탬프가 겹쳐 LWW 비교가 무의미해지고 tombstone 전파가
#    거짓 FAIL로 나온다 (2026-09-11에 이 함정으로 한 시간을 썼다)

# 4. 배포 확인 (push 후)
gh api repos/imeru/buzzplan/pages/builds/latest --jq .status   # "built" 될 때까지
curl -s "https://imeru.github.io/buzzplan/?v=$RANDOM" | grep -c "<찾을 문자열>"
# builds API만 믿지 말 것. Actions 기반 배포에서는 이 legacy 레코드가 갱신되지 않아
# 몇 분 동안 옛 커밋을 latest로 돌려주는 일이 있다 (2026-09-11에 4분간 관측).
# 판정 근거는 배포본 curl의 문자열 검증이다. 둘이 엇갈리면 curl 쪽을 믿는다
# 브라우저 확인은 반드시 강력 새로고침 (Cmd+Shift+R). 캐시가 강하다
# index.html에 no-cache 메타를 넣어 재검증을 요구하지만, 이미 캐시된 기기에는 소급되지
# 않는다. 사파리는 특히 오래 쓴다. 옛 버전이 돌면 동기화처럼 데이터가 걸린 기능에서
# 사고가 나므로, 동기화 수정 후에는 기기마다 강력 새로고침을 안내할 것

# 5. 현장 동기화 진단 (사용자 신고가 재현되지 않을 때)
#    문제가 난 기기에서 ?debug=sync를 붙여 열고 로그인한 뒤, 패널의 "복사"를 눌러
#    전문을 받는다. 정상 기기에서도 같이 받아 account와 uid 줄을 맞대면
#    계정 불일치가 즉시 갈린다. 추측으로 가설을 쌓기 전에 이 단계를 먼저 할 것
https://imeru.github.io/buzzplan/?conf=<학회id>&debug=sync
```

## 10. 완료의 정의 (보고 전 체크리스트)

작업을 "끝났다"고 보고하기 전에 전부 확인한다:

- [ ] index.html 수정 시: JS 구문 검사 통과
- [ ] 신규 사용자 노출 문자열: I18N_KO/EN 양쪽 + (정적이면) applyStaticLang 반영
- [ ] 선택, 별점, 메모, 꼭 듣기 변경 경로를 추가하거나 수정했으면: touch(key) 포함 여부 확인
- [ ] 데이터 변경 시: validate_v2 통과 + 학회 표(5장) 숫자 갱신
- [ ] 로컬 서버에서 해당 화면 로드 확인 (최소한 게스트 모드)
- [ ] push했으면: Pages 빌드 "built" 확인 후 배포본에서 변경 존재 확인
- [ ] 커밋 메시지는 한국어로, 무엇을+왜 (이 레포의 git log 스타일 참조)
- [ ] 확신 없는 부분은 숨기지 말고 "확인 필요"로 보고

## 11. 사용자와의 작업 방식

- 실행 단계에서 허락을 묻지 않는다. 진행 여부 확인 질문 금지
  (예외: 2장 8번의 파괴적 작업, 그리고 외부 서비스 과금이 생기는 결정)
- 방향 결정(기능 설계, 기술 선택)은 선택지 2~3개 + 권장안을 제시하고 확인받는다.
  확인 후 실행에서는 다시 묻지 않는다
- 긴 작업은 단계 시작 시 무엇을 할지 한 줄, 완료 시 결과 한 줄 보고
- 기계적·반복적 실행은 서브에이전트에 명확한 지침과 함께 위임 가능.
  논리 검토·최종 품질 판정은 메인이 직접 한다
- 산출물 문체: 엠대시(—) 금지, 장황 금지. 이 파일의 문체가 기준

## 12. 알려진 제한

- SAREK 하계 규칙 파서: 변형 레이아웃(일부 특별세션, 포스터)은 누락 가능.
  2026 하계 포스터 67편은 Tier 2로 수동 추가 완료, **2025 하계 포스터는 여전히 누락**
- PDF 글자 쪼개짐은 `consolidate_split_chars()`로 보정 (gap 0.5pt 이하 병합)
- 발표 시간 자동 배정은 고정 15분. 발표 수가 적은 세션은 일찍 끝나는 것으로 표시됨
- roomvent-2026: 기술투어(TT1~TT4)는 프로그램에 시작(8:30)만 있고 종료가 없어
  `--tour-end` 기본값 12:00을 넣었다. **추정치이므로 신뢰하지 말 것.** 같은 방
  `Off-site`를 쓰므로 build.py의 시간 겹침 경고 3건은 정상이다.
  세션 S17의 마지막 발표(11:35-11:50)가 세션 종료(11:45)를 5분 넘기는데 원문 그대로다
- 회장 지도의 거리는 **직선거리에 우회 계수를 곱한 추정치**다. 실제 복도 경로가 아니므로
  ㄷ자 동선이나 막힌 구역이 있으면 실제보다 짧게 나온다. 실측값이 있으면 `venue.walk.pairs`에
  적어 두는 편이 낫다 (pairs가 지도 계산을 이긴다)
- 같은 건물의 층 도면들은 **같은 기준으로 잘려 있다고 가정**하고 좌표를 그대로 비교한다.
  층마다 다르게 크롭되었거나 축척이 다르면 층 사이 거리가 틀린다. 도면을 넣기 전에
  같은 위치의 기둥이나 계단이 두 층에서 같은 좌표에 오는지 확인할 것
- 부팅 오류 페이지(conferences.json 로드 실패 등)는 한국어 고정 (i18n 미적용).
  동적으로 DOM을 재생성하는 코드는 문자열을 하드코딩하지 말고 t()를 쓸 것
  (과거 사례: 학회명 편집 후 툴팁이 한국어로 되돌아가는 회귀)

**sarek-2026-summer 지도의 유래와 한계** (2026-09-09): 원본은 프로그램북의
"알펜시아리조트 컨벤션센터 행사장 배치도" 한 장인데, 1F와 2F 도면이 한 페이지에
세로로 인쇄되어 있었다. 그대로 한 장으로 넣으면 층 사이 거리가 종이 위 여백까지
포함해 계산되고 층 이동 시간도 붙지 않아, 층별로 잘라 두 장으로 나눴다.
- 자른 기준: 도면 상단이 두 이미지 모두 `y=60`에 오도록 맞췄다(1F는 원본 y=188부터,
  2F는 y=878부터). 가로는 원본 전체 폭을 유지해 범례를 남겼다
- 두 도면의 건물 폭이 1072px와 1045px로 2.6% 차이라 **같은 축척으로 간주**했다.
  둘 다 `width_meters` 102.5를 쓴다
- 건물 윤곽이 층마다 완전히 겹치지는 않으므로 **층 간 수평 거리는 근사**다
  (계통 오차 약 4m, 층 이동 1.5분에 비하면 작다). 같은 층 안의 거리는 도면값 그대로다

## 13. 지도 편집기의 파일 쓰기 계약

`map-editor.html`은 File System Access API로 저장소에 직접 쓴다. Chrome과 Edge에서만
동작하고, Safari와 Firefox에서는 기능만 꺼지고 나머지는 그대로 쓸 수 있다.

- **연결 대상은 저장소 루트**다. `conferences.json`과 `data/`가 있는지 검사해서
  엉뚱한 폴더를 연결하는 사고를 막는다 (`looksLikeRepo`). 핸들은 IndexedDB
  (`buzzplan-mapeditor` / `handles` / `rootDir`)에 기억되지만, 재방문 시 권한이
  `prompt`로 떨어지면 버튼을 한 번 더 눌러야 한다
- **이미지**는 `assets/maps/`에 쓴다. 같은 이름이 있으면 덮어쓰기를 확인받는다
- **venue JSON**은 `data/<id>.json`을 읽어 `venue.maps`만 갈아 끼우고 다시 쓴다.
  `venue.walk`를 비롯한 나머지 키는 건드리지 않는다
- **diff가 venue 블록에만 갇히는 이유**: 브라우저의 `JSON.stringify(d, null, 2)`가
  build.py의 `json.dumps(ensure_ascii=False, indent=2)`와 출력이 같다. 현행 5개 파일
  전부 왕복 후 바이트가 일치하는 것을 확인했다. **끝에 개행을 붙이면 안 된다**
  (파일들의 마지막 문자는 `}`다). 이 성질이 깨지면 전 파일에 diff가 생긴다
- **안전장치 3중**: 쓰기 전 `sessions`와 `papers` 개수와 최상위 키 대조,
  원본을 `data/<id>.json.bak`으로 백업(`*.json.bak`은 .gitignore), 변경 내용을
  확인창으로 표시. 결과가 이상하면 `git checkout -- data/<id>.json`으로 되돌린다

## 14. 백로그 (우선순위 순. 착수 전 사용자에게 한 줄 확인)

1. **sarek-2025-summer 포스터 추가** (Tier 2 방식): 지난 학회라 아카이브 완결성 목적.
   소스 PDF를 사용자에게 요청해야 함
2. **앱 내 발표 알림** (Notification API): ICS VALARM(5분 전, 완료)의 후속.
   앱을 열어둔 상태에서의 알림
3. **시간 범위 필터 프리셋** (오전만/오후만 + localStorage 기억)
4. **웹 프로그램 페이지(HTML)·Excel/CSV 임포터**: 실수요가 생기면
5. **학회 간 비교 모드 / 통합 통계**: 보류
6. **parser_llm.py 라이브 가동**: 사용자가 API 과금을 승인할 때만
