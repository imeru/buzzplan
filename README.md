# Conference Schedule Planner

학회 세션 PDF에서 발표 정보를 추출하여, 듣고 싶은 발표를 선택하고
일정·동선을 자동으로 계획해 주는 도구. 여러 학회의 데이터를 하나의 사이트에서 다룰 수 있습니다.

---

## 폴더 구조

```
conference-planner/
├── index.html              # 도구 본체 (학회별 데이터 로드)
├── conferences.json        # 사용 가능한 학회 목록 + default
├── data/
│   └── iaqvec-2026.json    # 학회별 데이터 (parser 산출물)
├── parser.py               # IAQVEC·IBPSA 형식 PDF 파서
├── build.py                # 새 학회 추가 자동화
└── README.md
```

학회를 추가하면 `data/<conf-id>.json`이 새로 생기고 `conferences.json`에 자동 등록됩니다.

---

## 학생용 사용 안내

브라우저에서 사이트 URL을 열면 시작됩니다.

| 접근 방식 | URL 예 |
|---|---|
| 기본 학회 | `https://<유저명>.github.io/conference-planner/` |
| 특정 학회 명시 | `https://<유저명>.github.io/conference-planner/?conf=iaqvec-2026` |
| 다른 학회로 전환 | 헤더 드롭다운 또는 URL의 `?conf=` 변경 |

**기본 흐름**
1. 좌측 필터(검색·Day·트랙·건물)로 관심 세션을 좁힙니다.
2. 발표 옆 체크박스로 듣고 싶은 발표를 선택합니다.
3. 상단 **📅 내 일정** 탭에서 리스트·시간표 두 가지로 일정을 확인합니다.
4. 학회 종료 후 발표별로 별점·메모를 남길 수 있습니다.
5. 상단 **공유 링크**·**ICS**·**CSV** 버튼으로 데이터를 내보낼 수 있습니다.

**데이터 저장**
모든 선택·평점·메모는 **본인 브라우저의 localStorage**에 학회별로 분리 저장됩니다.
학회 ID(`iaqvec-2026` 등)가 다르면 데이터도 서로 섞이지 않습니다.

---

## GitHub Pages 배포

### 최초 1회

1. github.com에서 **New repository** → 이름 자유롭게(예: `conference-planner`) → **Public** → Create.
2. 본 폴더의 모든 파일을 **Add file → Upload files**로 끌어다 놓고 **Commit changes**.
   - 폴더 구조 그대로 올라가도록 `data/`도 함께 드래그.
3. **Settings → Pages** → Source: `main` 브랜치, `/ (root)` → **Save**.
4. 1~2분 후 페이지 상단에 URL이 표시됩니다.

이후 학생들에게는 그 URL 하나만 공유하면 됩니다.

### 다음 학회 추가

```bash
python3 build.py /path/to/new_conference.pdf \
  --id   iaqvec-2028 \
  --name "IAQVEC 2028"
```

`build.py`가 자동으로 수행합니다.
1. `parser.py`로 PDF 파싱 → 검증
2. `data/iaqvec-2028.json` 생성
3. `conferences.json`에 새 학회 항목 추가 (이미 있으면 갱신)

이후 변경된 두 파일(`data/iaqvec-2028.json`, `conferences.json`)만 GitHub에 push하면 학생들이 보는 사이트에서 새 학회가 즉시 선택 가능해집니다. 기본 URL(`?conf=` 없는 접근)에 표시될 학회를 바꾸시려면 `--default` 옵션을 함께 주세요.

### 학회 ID 명명 규칙

| 형식 | 예 |
|---|---|
| `<학회약어>-<년도>` | `iaqvec-2026`, `iaqvec-2028` |
| `<학회약어>-<주최지>` | `ibpsa-bs-2027-glasgow` |
| `<학회약어>-<년도>-<시즌>` | `sarek-2025-winter` |

같은 ID로 재빌드하면 그 학회 학생들의 평점·메모는 그대로 유지됩니다.

---

## 로컬에서 테스트하기

`index.html`을 더블클릭으로 열면 **동작하지 않습니다**. 브라우저의 `file://` 보안 정책 때문에 `fetch()`로 다른 파일을 읽을 수 없기 때문입니다. 로컬 테스트는 다음 한 줄로 가능합니다.

```bash
cd /path/to/conference-planner
python3 -m http.server 8080
```

그 다음 브라우저에서 `http://localhost:8080/` 접속.
특정 학회는 `http://localhost:8080/?conf=iaqvec-2026`.

---

## 비표준 학회 PDF 대응

본 `parser.py`는 표준적인 IAQVEC·IBPSA 학회 PDF 형식을 가정합니다. 다른 형식의 PDF는 부분 수정이 필요할 수 있습니다.

### 진단

```bash
python3 build.py /path/to/pdf.pdf --id test --name "Test" --dry-run
```

출력에서 다음을 확인:

| 신호 | 의미 | 조치 |
|---|---|---|
| `sessions=0` 또는 `papers=0` | 세션 헤더 인식 실패 | `parser.py`의 `SESS_RE` 보강 |
| `[경고] orphan papers: N` | 일부 세션만 인식 실패 | `TIME_LOC_RE` 등 보강 |
| 발표 수가 PDF보다 적음 | 표 컬럼 좌표 다름 | `AUTHOR_X`, `TITLE_X` 조정 |

### parser.py 주요 수정 지점

```python
AUTHOR_X = 190         # author 컬럼 시작 x 좌표
TITLE_X  = 335         # title 컬럼 시작 x 좌표

DAY_RE      = ...      # "Day 2: 5/19/2026 (Tue)" 패턴
SESS_RE     = ...      # "Session 1 1-1 Indoor Air Quality" 패턴
TIME_LOC_RE = ...      # "11:00 - 12:30 Location: SGM 123 / Session chair: ..." 패턴
```

PDF의 실제 좌표를 확인:

```bash
python3 -c "
import pdfplumber
with pdfplumber.open('/path/to/pdf.pdf') as pdf:
    for w in pdf.pages[0].extract_words()[:40]:
        print(f\"{w['top']:6.1f} {w['x0']:6.1f}  {w['text']}\")
"
```

### 완전히 다른 형식이라면 (예: 한국어 학회·2단 레이아웃·세로형 등)

별도 파서를 만들고 `build.py`에 `--parser parser_xxx.py` 옵션으로 사용합니다. 파서는 다음 JSON 스키마를 출력하면 됩니다.

```json
{
  "conference": { "id": "...", "name": "..." },
  "sessions": [
    { "id": "1-A", "day": 1, "date": "11/28/2025",
      "track_title": "냉동/열펌프 1",
      "start": "08:50", "end": "10:05",
      "building": "제4회장", "room": "",
      "chair": "이동찬(서울시립대학교)" }
  ],
  "papers": [
    { "paper_no": "25-W-063", "session_id": "1-A",
      "authors": "...", "title": "...",
      "start": "08:50", "end": "09:05" }    // 발표별 명시 시간 (선택)
  ]
}
```

---

## 라이선스

내부 사용 목적. 외부 공유 시 학교/연구실 정책을 따릅니다.

## 문의

건국대학교 건축대학 ecosoop@gmail.com
