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
5. **선택·별점·메모를 바꾸는 모든 코드 경로는 `touch(key)`를 호출해야 한다.**
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
parser_utils.py     파서 공통: v2 정규화(finalize_v2)·검증(validate_v2)
parser_llm.py       LLM 범용 추출기. 코드 완성·미가동 (API 키 필요, 사용자가 당분간 보류 결정)
migrate_v2.py       v1→v2 일괄 변환 (일회성, 실행 완료. 참고용으로만 유지)
build.py            PDF→JSON→검증→conferences.json 등록 자동화. --dry-run 지원
assets/             로고. 헤더는 buzzplan-bee.png(+@2x), buzzplan-logo.png(+@2x)도 참조됨
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
    "start": "11:00", "end": "11:15"
  }]
}
```

필드 주의사항 (스키마만 보면 틀리기 쉬운 부분):

- `venue.walk`: 단위는 분. 없으면 기본값(0/2/4/8) 사용. `building_min`은 "이 건물이 끼면 N분".
  현재 iaqvec-2026의 값(7분/10분 등)은 실측이 아니라 **추정치**다. 정밀도를 믿지 말 것
- `session.day`: 정렬·필터용 숫자일 뿐 의미가 학회마다 다르다
  (IAQVEC: 행사 N일차, SAREK: 날짜의 일). 같은 학회 안에서만 일관되면 된다
- `session.type`: `oral`(기본)·`poster`·`keynote`·`social`·`break`.
  oral 외에는 세션 헤더에 뱃지가 붙고, poster는 발표들이 세션 전체 시간을 공유한다
- `paper.paper_no`가 `"HH:MM-HH:MM"` 형태면 그 시간 범위가 발표 시간으로 쓰인다
  (전문가강연·교육 등 번호 없는 항목의 관례)
- `paper.start/end`가 없으면 세션 시작부터 15분(`PAPER_MINUTES`) 단위로 자동 배정
- v1 레거시(12시간제, M/D/YYYY)는 `schema_version` 부재를 보고 index.html이 구식 휴리스틱으로 처리

## 5. 등록된 학회 (현행)

| id | 이름 | 파서 | 규모 | 비고 |
|---|---|---|---|---|
| iaqvec-2026 | IAQVEC 2026 | parser.py | 60세션/321발표 | tz America/Los_Angeles. venue.walk 보유(추정치) |
| sarek-2025-winter | 설비공학회 2025 동계 | parser_sarek.py | 34세션/159발표 | 발표별 명시 시간 |
| sarek-2025-summer | 설비공학회 2025 하계 | parser_sarek_summer.py | 66세션/312발표 | 포스터 누락 (알려진 제한) |
| sarek-2026-summer | 설비공학회 2026 하계 | parser_sarek_summer.py | 76세션/407발표 | **default**. 포스터 67편은 Tier 2로 추가. 재파싱 시 `--day-fix 19:25` 필수 |

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
        { items: { "<sessionId>#<paperNo>": {s: 0|1, r: 별점, n: 메모, t: ms} } }
```

- **키별 LWW 병합**: 로컬 변경은 `touch(key)`가 `state.stamps`에 시각 기록 → 800ms 디바운스 후
  문서 전체 push. 원격 수신은 `remote.t > local.t`인 키만 적용 (적용 시 stamps 직접 갱신, touch 금지)
- **삭제 전파**: 선택 해제해도 stamps가 남아 tombstone(s:0) 역할
- **에코 가드**: onSnapshot에서 `hasPendingWrites`면 무시. 로그인 직후 첫 스냅샷은 토스트 억제
- **게스트 모드 불변 원칙**: 로그인 없으면 동작이 기존과 100% 동일해야 한다
- **오류는 표면화**: 동기화 실패는 조용히 삼키지 말고 `reportSyncError`로 (버튼 ⚠️ + 권한 오류 안내)
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
- 조회 캐시 `_papersBySession` 등은 학회 전환 시 `invalidateCaches()`

## 9. 검증 방법 (테스트 프레임워크 없음, 아래가 관행)

```bash
# 1. JS 구문 검사 (index.html 수정 후 항상)
python3 -c "import re; html=open('index.html').read(); s=re.findall(r'<script>(.*?)</script>', html, re.S); open('/tmp/app.js','w').write('\n'.join(s))" && node --check /tmp/app.js

# 2. 데이터 검증 (데이터·파서 수정 후)
python3 build.py <pdf> --parser <parser> --id tmp --name t --dry-run   # 카운트·orphan·결번·분포 리포트

# 3. 로직 테스트: 스크래치패드에 ad-hoc node 스크립트.
#    /tmp/app.js에서 대상 함수를 문자열로 잘라 eval하고 시나리오 검증하는 패턴
#    (동기화 수정 시 최소: 양방향 반영, 원격이 이기는 경우, 삭제 전파, 에코 무시)

# 4. 배포 확인 (push 후)
gh api repos/imeru/buzzplan/pages/builds/latest --jq .status   # "built" 될 때까지
curl -s "https://imeru.github.io/buzzplan/?v=$RANDOM" | grep -c "<찾을 문자열>"
# 브라우저 확인은 반드시 강력 새로고침 (Cmd+Shift+R). 캐시가 강하다
```

## 10. 완료의 정의 (보고 전 체크리스트)

작업을 "끝났다"고 보고하기 전에 전부 확인한다:

- [ ] index.html 수정 시: JS 구문 검사 통과
- [ ] 신규 사용자 노출 문자열: I18N_KO/EN 양쪽 + (정적이면) applyStaticLang 반영
- [ ] 선택·별점·메모 변경 경로를 추가·수정했으면: touch(key) 포함 여부 확인
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
- 부팅 오류 페이지(conferences.json 로드 실패 등)는 한국어 고정 (i18n 미적용).
  동적으로 DOM을 재생성하는 코드는 문자열을 하드코딩하지 말고 t()를 쓸 것
  (과거 사례: 학회명 편집 후 툴팁이 한국어로 되돌아가는 회귀)

## 13. 백로그 (우선순위 순. 착수 전 사용자에게 한 줄 확인)

1. **파서 레이아웃 헬퍼 통합**(group_rows, consolidate_split_chars, is_skip_row →
   parser_utils.py): 2026 동계 SAREK 추가 전에 해두면 효율
2. **sarek-2025-summer 포스터 추가** (Tier 2 방식): 지난 학회라 아카이브 완결성 목적.
   소스 PDF를 사용자에게 요청해야 함
3. **앱 내 발표 알림** (Notification API): ICS VALARM(5분 전, 완료)의 후속.
   앱을 열어둔 상태에서의 알림
4. **시간 범위 필터 프리셋** (오전만/오후만 + localStorage 기억)
5. **웹 프로그램 페이지(HTML)·Excel/CSV 임포터**: 실수요가 생기면
6. **학회 간 비교 모드 / 통합 통계**: 보류
7. **parser_llm.py 라이브 가동**: 사용자가 API 과금을 승인할 때만
