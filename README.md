# BuzzPlan (버즈플랜) : Conference Schedule Planner

학회 세션 PDF에서 발표 정보를 추출하여, 듣고 싶은 발표를 선택하고
일정과 동선을 자동으로 계획해 주는 도구. 한 URL에서 여러 학회를 함께 다룰 수 있습니다.

배포본: [https://imeru.github.io/buzzplan/](https://imeru.github.io/buzzplan/)

---

## 현재 등록된 학회

| ID | 이름 | 일시 | 회장 | 세션 | 발표 | 지도 |
|---|---|---|---|---|---|---|
| `roomvent-2026` | RoomVent 2026 | 2026/9/15~18 (프라하 CTU) | A 230, B 168/169/286, C 215~223 | 59 | 269 | 1층, 2층 |
| `sarek-2026-summer` | 대한설비공학회 2026 하계학술발표대회 | 2026/6/24~26 (평창 알펜시아) | 제1~제13회장 | 76 | 407 | 1층, 2층 |
| `iaqvec-2026` | IAQVEC 2026 | 2026/5/19~21 (USC) | SGM, GFS, VHE | 60 | 321 | |
| `sarek-2025-winter` | 대한설비공학회 2025 동계학술발표대회 | 2025/11/28 (한국과학기술회관) | 제1~제7회장 | 34 | 159 | |
| `sarek-2025-summer` | 대한설비공학회 2025 하계학술발표대회 | 2025/6/19~20 (평창 알펜시아) | 제1~제12회장 | 66 | 312 | |

"지도" 열이 있는 학회에서는 회장 이름 옆에 🗺 가 붙고, 세션 사이 이동 시간을 도면상 거리로
계산합니다. 지도를 넣는 방법은 아래 "회장 지도 추가하기"를 보세요.

기본 학회는 RoomVent 2026이며, URL 끝에 `?conf=<id>`를 붙이면 다른 학회로 전환됩니다. 헤더 드롭다운으로도 즉시 전환 가능합니다.

---

## 폴더 구조

```
buzzplan/
├── index.html                    # 도구 본체 (학회별 데이터를 부팅 시 fetch)
├── map-editor.html               # 회장 지도 저작 도구 (내부용, 앱에서 링크하지 않음)
├── conferences.json              # 사용 가능한 학회 목록 + default
├── firestore.rules               # 계정 동기화 보안 규칙 (Firebase 콘솔에 수동 배포)
├── assets/
│   ├── buzzplan-bee.png          # 헤더 로고 (벌 아이콘 1x)
│   ├── buzzplan-bee@2x.png       # 헤더 로고 (2x retina)
│   ├── buzzplan-logo.png         # 파비콘용 풀 로고
│   ├── buzzplan-logo@2x.png
│   └── maps/                     # 회장 도면 이미지 (venue.maps가 참조)
├── data/
│   ├── iaqvec-2026.json
│   ├── roomvent-2026.json
│   ├── sarek-2025-winter.json
│   ├── sarek-2025-summer.json
│   └── sarek-2026-summer.json
├── parser.py                     # IAQVEC, IBPSA 형식 PDF 파서
├── parser_sarek.py               # SAREK 동계(가로 2단 컬럼) 파서
├── parser_sarek_summer.py        # SAREK 하계(세로 1단 컬럼) 파서
├── parser_roomvent.py            # RoomVent(ConfTool 인쇄 프로그램) 파서
├── parser_utils.py               # 파서 공통 (스키마 v2 정규화와 검증, 레이아웃 헬퍼)
├── parser_llm.py                 # LLM 범용 추출기 (API 키 필요, 현재 미가동)
├── migrate_v2.py                 # v1 → v2 일괄 변환 (일회성, 실행 완료)
├── build.py                      # PDF → JSON → 학회 등록 자동화
├── CLAUDE.md                     # 개발 핸드오프 문서 (설계 계약과 함정 기록)
└── README.md
```

학회를 추가하면 `data/<conf-id>.json`이 새로 생기고 `conferences.json`에 자동 등록됩니다.

---

## 학생용 사용 안내

브라우저에서 사이트 URL을 열면 시작됩니다.

| 접근 방식 | URL |
|---|---|
| 기본 학회 (RoomVent 2026) | `https://imeru.github.io/buzzplan/` |
| RoomVent 2026 명시 | `…/?conf=roomvent-2026` |
| SAREK 2026 하계 | `…/?conf=sarek-2026-summer` |
| IAQVEC 2026 | `…/?conf=iaqvec-2026` |
| SAREK 2025 동계 | `…/?conf=sarek-2025-winter` |
| SAREK 2025 하계 | `…/?conf=sarek-2025-summer` |
| 다른 학회로 전환 | 헤더 드롭다운 또는 URL의 `?conf=` 변경 |
| 영어 화면 | URL 뒤에 `&lang=en` (헤더 🌐 로도 전환) |

**기본 흐름**
1. 좌측 필터(검색, Day, 트랙, 회장)로 관심 세션을 좁힙니다.
2. 발표 옆 체크박스로 듣고 싶은 발표를 선택합니다.
   - 그중 반드시 들어야 하는 발표는 오른쪽 **☆** 를 눌러 **⭐ 꼭 듣기**로 표시하세요. 내 일정과 시간표에서 눈에 띄게 강조되고, 표시하면 일정에도 자동으로 담깁니다.
3. 상단 **📅 내 일정** 탭에서 리스트와 시간표 두 가지로 일정을 확인합니다.
   - 회장 지도를 공개한 학회에서는 회장 이름 옆에 🗺 가 붙습니다. 누르면 그 방의 위치가 지도에 뜨고, 이동 안내의 "A → B"를 누르면 두 지점과 예상 도보 시간을 함께 보여 줍니다. 지도에 축척이 있으면 이동 시간도 도면상 거리로 계산합니다(직선거리 기준 추정치라 실제 복도 경로와는 차이가 있습니다).
4. 학회 종료 후 발표별로 별점과 메모를 남길 수 있습니다. 별점은 듣고 난 뒤의 평가라 ⭐ 꼭 듣기와는 별개입니다.
5. 상단 **📅 ICS** 와 **📊 CSV** 버튼으로 일정을 캘린더 앱이나 엑셀로 내보낼 수 있습니다.
6. 컴퓨터에서 짠 일정을 모바일에서 이어 보려면 헤더의 **🔑 로그인(구글)**으로 같은 계정에 로그인하면 자동 동기화됩니다. 자세한 내용은 아래 "기기 간 동기화" 섹션 참고.

**데이터 저장**
로그인하지 않으면(게스트 모드) 선택과 꼭 듣기, 별점, 메모는 **본인 브라우저의 localStorage**에 학회별로 분리 저장되어 그 기기에만 남습니다.
헤더에서 **🔑 로그인(구글)**을 하면 같은 데이터가 클라우드에도 저장되어 다른 기기에서도 이어볼 수 있습니다.

---

## 🔄 기기 간 동기화 (구글 로그인)

로그인은 선택 사항입니다. 로그인하지 않아도 도구는 그대로 동작하며, 이 경우 데이터는 지금 쓰는 기기의 브라우저에만 저장됩니다(게스트 모드).

**로그인 방법**
헤더의 **🔑 로그인(구글)** 버튼을 눌러 구글 계정으로 로그인합니다.

**동기화되는 데이터**
발표 **선택 여부와 ⭐ 꼭 듣기, 별점, 메모**가 학회별로 저장되고, 같은 계정으로 로그인한 모든 기기에 실시간(1~2초 내)으로 반영됩니다.

**다른 기기에서 이어 보기**
컴퓨터에서 고른 일정을 모바일에서 보고 싶다면(또는 그 반대) 그 기기에서도 같은 구글 계정으로 로그인하기만 하면 됩니다. 그것으로 끝입니다.

오프라인 상태에서도 계속 사용할 수 있고, 다시 연결되면 그동안의 변경 사항이 자동으로 병합됩니다.

**로그인하지 않으면?**
게스트 모드로 동작합니다. 선택과 꼭 듣기, 별점, 메모는 그 브라우저(기기)에만 localStorage로 저장되고, 다른 기기와는 동기화되지 않습니다. 언제든 로그인하면 그 시점부터 동기화가 시작됩니다.

**문제 해결**

| 증상 | 먼저 해 볼 것 |
|---|---|
| 로그인 버튼이 **⚠️ 동기화 오류** | 버튼을 눌러 안내 메시지를 확인하세요. 권한 오류면 Firestore 설정 문제이니 관리자에게 문의하세요 |
| 다른 기기에서 고른 발표가 안 보임 | 두 기기의 **구글 계정이 같은지**, 그리고 **같은 학회(`?conf=`)를 보고 있는지** 확인하세요. 저장은 학회별로 나뉩니다 |
| 로그인했는데 한동안 비어 있다가 채워짐 | 정상입니다. 사파리는 첫 연결에 1~2초 걸립니다. 그 사이 화면은 이 기기에 남아 있던 내용을 보여 줍니다 |
| 최근 고친 내용이 반영되지 않음 | 강력 새로고침을 하세요 (Mac은 `Cmd+Option+R`, Windows는 `Ctrl+F5`). 브라우저 캐시가 옛 버전을 오래 붙잡습니다 |

그래도 해결되지 않으면 URL 뒤에 `&debug=sync`를 붙여 열면(예:
`…/?conf=roomvent-2026&debug=sync`) 화면 아래에 진단 패널이 뜹니다. **복사**를 눌러
나온 내용을 관리자에게 보내 주세요. 계정, 학회, 서버 읽기 상태가 한 화면에 나옵니다.

---

## GitHub Pages 배포

### 최초 1회

1. github.com에서 **New repository** → `buzzplan` (또는 원하는 이름) → **Public** → Create.
2. 본 폴더의 모든 파일과 폴더를 **Add file → Upload files**로 끌어다 놓고 **Commit changes**.
   - `data/` 와 `assets/` 폴더도 함께 드래그.
3. **Settings → Pages** → Source: `main` 브랜치, `/ (root)` → **Save**.
4. 1~2분 후 페이지 상단에 URL이 표시됩니다.

이후 학생들에게는 그 URL 하나만 공유하면 됩니다.

### 다음 학회 추가

학회마다 PDF 형식이 다르므로 적절한 파서를 선택해 실행합니다.

| 학회 유형 | 파서 |
|---|---|
| IAQVEC, IBPSA, ASHRAE 등 영문 표 형식 | `parser.py` |
| SAREK 동계 (가로 2단) | `parser_sarek.py` |
| SAREK 하계 (세로 1단, 다일자) | `parser_sarek_summer.py` |
| RoomVent 등 ConfTool 인쇄용 프로그램 | `parser_roomvent.py` |
| 그 외 형식 | 새 파서 작성 (아래 트러블슈팅 참고) |

빌드 명령 예:

```bash
# IAQVEC 형식
python3 build.py /path/to/new_iaqvec.pdf \
  --id iaqvec-2028 --name "IAQVEC 2028" --default

# SAREK 동계
python3 build.py /path/to/sarek-winter.pdf \
  --parser parser_sarek.py \
  --id sarek-2026-winter --name "대한설비공학회 2026 동계학술발표대회" --default

# SAREK 하계
python3 build.py /path/to/sarek-summer.pdf \
  --parser parser_sarek_summer.py \
  --id sarek-2027-summer --name "대한설비공학회 2027 하계학술발표대회" \
  --default

# RoomVent (ConfTool 인쇄용 프로그램)
python3 build.py /path/to/roomvent_program.pdf \
  --parser parser_roomvent.py \
  --id roomvent-2028 --name "RoomVent 2028" --timezone Europe/Prague --default
```

`build.py`가 자동으로 다음을 수행합니다.
1. 지정한 파서로 PDF 파싱 + 검증 (세션과 발표 수, orphan 확인)
2. `data/<id>.json` 생성
3. `conferences.json`에 새 학회 항목 추가 (이미 있으면 갱신)

이후 변경된 `data/<id>.json`과 `conferences.json` 두 파일만 GitHub에 push하면 학생들이 보는 사이트에서 새 학회가 즉시 선택 가능해집니다. HTML 자체는 건드릴 필요 없음.

**옵션**
- `--default`: 이 학회를 default로 지정 (URL에 `?conf` 없을 때 처음 보이는 학회). 가장 최신 학회를 등록할 땐 함께 주세요.
- `--dry-run`: 파일 갱신 없이 파서 결과만 검증

### 학회 ID 명명 규칙

| 형식 | 예 |
|---|---|
| `<학회약어>-<년도>` | `iaqvec-2026`, `iaqvec-2028` |
| `<학회약어>-<년도>-<시즌>` | `sarek-2025-winter`, `sarek-2026-summer` |
| `<학회약어>-<주최지>` | `ibpsa-bs-2027-glasgow` |

같은 ID로 재빌드하면 그 학회 참가자들의 별점과 메모는 그대로 유지됩니다.

---

## 🗺 회장 지도 추가하기 (선택)

지도는 없어도 됩니다. 넣으면 두 가지가 좋아집니다. 회장 이름 옆의 🗺 로 방 위치를 보여 주고,
세션 사이 이동 시간을 도면상 실제 거리로 계산합니다. 지도가 없으면 기존처럼 같은 층 2분,
같은 건물 4분 같은 규칙만 씁니다.

**1. 도면 이미지를 구합니다**
프로그램북, 학회 홈페이지의 venue 안내, 주최 기관의 시설 안내 페이지 순으로 찾습니다.
층이 여러 개면 **층마다 한 장으로 자르되 자르는 기준을 층끼리 맞춥니다.** 같은 위치의
계단이나 기둥이 두 도면에서 같은 좌표에 와야 층 사이 거리가 맞습니다.

**2. `map-editor.html`로 축척과 핀을 잡습니다**

```bash
python3 -m http.server 8080
# 브라우저에서 http://localhost:8080/map-editor.html (Chrome 또는 Edge)
```

이미지를 끌어다 놓고, 도면에서 실제 길이를 아는 두 지점을 찍어 축척을 정한 뒤,
방마다 핀을 찍습니다. **핀의 방 이름은 데이터의 `room` 값과 정확히 같아야** 연결됩니다
(`B 168`과 `B168`은 다릅니다).

저장소 루트를 연결하면(Chrome, Edge의 파일 접근 권한) 이미지는 `assets/maps/`에,
좌표는 `data/<id>.json`의 `venue.maps`에 직접 씁니다. 원본은 `.bak`으로 백업되고,
결과가 이상하면 `git checkout -- data/<id>.json`으로 되돌립니다.

**3. 확인하고 커밋합니다**

```bash
git diff data/          # venue 블록만 바뀌었는지 확인
git add data/<id>.json assets/maps/ && git commit -m "..."
```

**주의**

- 좌표는 **원본 이미지의 픽셀** 기준입니다. 넣은 뒤에 이미지를 리사이즈하면 핀이 전부 어긋납니다.
- `width_meters`(도면 가로가 실제 몇 미터인가)를 넣어야 거리 계산을 합니다. 비례가 맞지 않는
  안내형 일러스트 지도에는 **일부러 넣지 마세요.** 그러면 표시 전용으로만 쓰입니다.
- 계산값은 직선거리에 우회 계수를 곱한 추정치입니다. 실제 복도 경로가 아니라서 ㄷ자 동선이나
  막힌 구역이 있으면 실제보다 짧게 나옵니다. 실측값을 안다면 `venue.walk.pairs`에
  `{"between": ["A동", "B동"], "min": 7}` 형태로 적어 두는 편이 낫습니다 (이 값이 지도 계산을 이깁니다).
- 도면의 저작권을 확인하세요. 저장소가 공개라면 재배포해도 되는 자료인지 먼저 보고 넣습니다.

---

## 로컬에서 테스트하기

`index.html`을 더블클릭으로 열면 **동작하지 않습니다**. 브라우저의 `file://` 보안 정책 때문에 `fetch()`로 다른 파일을 읽을 수 없습니다. 로컬 테스트는 다음 한 줄로 가능합니다.

```bash
cd /path/to/buzzplan
python3 -m http.server 8080
```

그 다음 브라우저에서 `http://localhost:8080/` 접속.
특정 학회 검증: `http://localhost:8080/?conf=sarek-2026-summer`.

---

## 비표준 학회 PDF 대응

기존 네 파서는 다음 가정을 합니다.

| 파서 | 가정 |
|---|---|
| `parser.py` | 세로 페이지, 1단 컬럼, 표 형식. 영문. 발표 시간은 세션 전체 시간을 15분으로 분할 |
| `parser_sarek.py` | 가로 페이지(2단 컬럼), 1일, 발표마다 명시 시간 (HH:MM-HH:MM), `25-W-NNN` |
| `parser_sarek_summer.py` | 세로 페이지, 1단 컬럼, 다일자(subsection 헤더에 일자 prefix), 발표마다 명시 시간, `(26-S-NNN)` |
| `parser_roomvent.py` | 좌표가 아니라 **글꼴 크기와 굵기**로 역할을 구분 (세션헤더 15pt, 메타 10.6pt 이탤릭, 시간마커 9.5pt 볼드, 제목 11pt 볼드, 저자 10pt). 발표번호가 없어 `<세션ID>-<순번>`을 붙임 |

**처음 보는 형식이라면** 규칙 파서를 새로 쓰기 전에, PDF를 Claude Code 대화에 첨부해
스키마 v2 JSON을 직접 추출하는 방법이 더 빠릅니다. 추출한 뒤 아래 검증 절차
(세션과 발표 수 대조, 발표번호 결번 검사, 무작위 스팟체크)를 거쳐 `data/<id>.json`과
`conferences.json`에 등록하면 규칙 파서 없이도 학회가 하나 늘어납니다.

### 진단

```bash
python3 build.py /path/to/pdf.pdf --parser parser.py --id test --name "Test" --dry-run
```

| 신호 | 의미 | 조치 |
|---|---|---|
| `sessions=0` 또는 `papers=0` | 세션 헤더 인식 실패 | 해당 파서의 `SUBSECTION_RE`/`SESS_RE` 보강 |
| `[경고] orphan papers: N` | 일부 세션만 인식 실패 | `TIME_LOC_RE` 등 보강 |
| 발표 수가 PDF보다 적음 | 표 컬럼 좌표 다름 | `AUTHOR_X`/`TITLE_X` 또는 `META_X_MAX`/`TITLE_X_MAX` 조정 |

PDF의 실제 좌표를 확인:

```bash
python3 -c "
import pdfplumber
with pdfplumber.open('/path/to/pdf.pdf') as pdf:
    p = pdf.pages[0]
    print(f'page size: {p.width:.0f} × {p.height:.0f}')
    for w in p.extract_words()[:40]:
        print(f\"{w['top']:6.1f} {w['x0']:6.1f}  {w['text']}\")
"
```

### 완전히 다른 형식이라면

별도 파서 파일을 만들고 `build.py --parser <새파서>.py` 옵션으로 사용합니다. 파서는 다음 JSON 스키마(v2)를 출력하면 됩니다.

```json
{
  "schema_version": 2,
  "conference": { "id": "...", "name": "...", "timezone": "Asia/Seoul" },
  "sessions": [
    {
      "id": "1-A",
      "block": 1,
      "day": 1,
      "date": "2025-11-28",
      "track_title": "...",
      "start": "08:50",
      "end": "10:05",
      "type": "oral",
      "building": "회장",
      "room": "1",
      "floor": 1,
      "chair": "..."
    }
  ],
  "papers": [
    {
      "paper_no": "25-W-001",
      "session_id": "1-A",
      "authors": "...",
      "title": "...",
      "start": "08:50",
      "end": "09:05"
    }
  ]
}
```

**지켜야 할 것 넷**

1. **시간은 24시간제 `HH:MM`, 날짜는 ISO `YYYY-MM-DD`**입니다. 파서는 출력 직전에
   `parser_utils.finalize_v2()`를 호출하고, `build.py`가 `validate_v2()`로 막습니다.
   12시간제나 `11/28/2025` 형식은 등록 단계에서 거부됩니다.
2. **단일 건물 학회는 `building` 값을 전 세션 똑같이** 씁니다(SAREK은 전부 `"회장"`).
   하나라도 다른 값이 섞이면 회장별 필터가 무너집니다. 포스터장 같은 특수 장소도
   `building`은 그대로 두고 `room`으로만 구분하세요(예: `room: "포스터"`).
3. `session.type`은 `oral`(기본), `poster`, `keynote`, `social`, `break` 중 하나입니다.
   `oral` 외에는 세션 헤더에 뱃지가 붙고, `poster`는 발표들이 세션 전체 시간을 공유합니다.
4. `session.day`는 정렬과 필터용 숫자일 뿐이라 의미가 학회마다 달라도 됩니다
   (행사 N일차든 날짜의 일이든). 같은 학회 안에서만 일관되면 됩니다.

`paper.start` / `paper.end`가 있으면 그대로 사용되고, 없으면 세션 시간을 15분씩 분할해
자동 계산합니다. `paper_no`가 `"HH:MM-HH:MM"` 형태면 그 범위가 발표 시간으로 쓰입니다
(전문가강연처럼 번호가 없는 항목의 관례).

---

## 라이선스

내부 사용 목적. 외부 공유 시 학교/연구실 정책을 따릅니다.

## 문의

건국대학교 건축대학 ecosoop@gmail.com
