# Conference Schedule Planner

학회 세션 PDF에서 발표 정보를 추출하여, 듣고 싶은 발표를 선택하고
일정·동선을 자동으로 계획해 주는 단일 HTML 도구.

현재 데이터: **IAQVEC 2026** (60 sessions, 321 papers, 5/19–5/21, USC)

---

## 학생용 사용 안내

브라우저(PC·태블릿·폰)에서 URL을 열면 바로 시작됩니다. 별도 설치 없음.

**기본 사용 흐름**
1. 좌측 필터(검색·Day·트랙·건물)로 관심 세션을 좁힙니다.
2. 발표 옆 체크박스로 듣고 싶은 발표를 선택합니다.
3. 상단 **📅 내 일정** 탭에서 시간 순으로 정리된 개인 일정과 발표장 간 이동시간을 확인합니다.
4. 학회 종료 후 발표별로 별점·메모를 남길 수 있습니다.
5. 상단 **캘린더(.ics)** 또는 **CSV** 버튼으로 일정과 메모를 내보낼 수 있습니다.

**데이터 저장 위치**
모든 선택·평점·메모는 **본인 브라우저의 localStorage**에만 저장됩니다. 서버로 전송되지 않고, 다른 사람과 공유되지 않습니다. 같은 기기·같은 브라우저로 다시 접속하면 그대로 유지되지만, 다른 기기로 옮기려면 CSV 내보내기를 활용해야 합니다.

---

## GitHub Pages 배포 절차

이 도구를 학생들과 공유하기 위한 호스팅 방법.

### 1단계: GitHub 계정과 레포 준비

1. GitHub 계정이 없으시면 https://github.com 에서 회원가입 (무료).
2. 우측 상단 **+** → **New repository** 클릭.
3. 다음 정보 입력:
   - **Repository name**: `iaqvec-2026-schedule` (또는 자유롭게)
   - **Public** 선택 (Pages는 무료 계정에서 Public 레포만 가능)
   - **Add a README file** 체크 (선택)
4. **Create repository** 클릭.

### 2단계: 파일 업로드

1. 생성된 레포 페이지에서 **Add file → Upload files** 클릭.
2. 본 폴더의 다음 파일들을 끌어다 놓기:
   - `index.html`  ← **필수**. 도구 본체.
   - `README.md`   ← 이 문서.
   - `schedule.json` ← (선택) 원본 데이터. 향후 갱신용.
   - `parser.py`   ← (선택) PDF 파서. 다음 학회 적용 시 사용.
3. 하단 **Commit changes** 클릭.

### 3단계: GitHub Pages 활성화

1. 레포 페이지 상단 **Settings** 탭 클릭.
2. 좌측 메뉴에서 **Pages** 선택.
3. **Source** 항목에서:
   - Branch: `main`
   - Folder: `/ (root)`
4. **Save** 클릭.
5. 잠시 후(보통 1~2분) 페이지 상단에 URL이 표시됩니다:
   `https://<유저명>.github.io/iaqvec-2026-schedule/`

이 URL을 학생들에게 공유하면 됩니다.

### 4단계: QR 코드 (선택)

학회장에서 학생들이 폰으로 빠르게 접근하도록 위 URL의 QR 코드를 만들어 슬라이드·이메일 시그니처·랩미팅 공지에 첨부하시면 좋습니다. 무료 QR 생성 도구를 검색해 URL을 붙여 넣으면 됩니다.

---

## 다음 학회로 재사용하기

새로운 학회 PDF가 생기면 한 줄로 빌드할 수 있습니다.

### 사전 준비 (한 번만)

```bash
pip install pdfplumber
```

### 빌드 (매 학회마다)

```bash
python3 build.py /path/to/new_conference.pdf \
  --id   iaqvec-2028 \
  --name "IAQVEC 2028"
```

`build.py`가 내부에서 세 단계를 자동으로 수행합니다.
1. `parser.py`로 PDF를 파싱해 `schedule.json` 생성
2. 세션 수·발표 수·orphan paper(파싱 누락) 검증
3. JSON을 `index.html` 안에 임베드

성공하면 갱신된 `index.html` 한 파일만 GitHub 레포에 다시 업로드하시면 됩니다.

**옵션**
- `--dry-run`: HTML은 건드리지 않고 파싱 결과만 검증.
- `--out-json`, `--html`: 산출 경로를 바꿀 때 사용.

### 학회 ID 관리

`--id`는 학회마다 고유한 슬러그(소문자·하이픈). 이 ID가 학생들의 평점·메모를 분리 저장하는 키가 됩니다.

권장 명명 규칙:

| 형식 | 예 |
|---|---|
| `<학회약어>-<년도>` | `iaqvec-2026`, `iaqvec-2028` |
| `<학회약어>-<주최지>` | `ibpsa-bs-2027-glasgow` |

같은 학회 ID로 재빌드하면(예: 스케줄 갱신 시), 그 ID로 저장된 학생들의 평점·메모는 그대로 유지됩니다. 발표 ID(`session-id#paper-no`)가 같으면 메모가 연결되고, 바뀐 발표 ID는 그냥 새 항목이 됩니다.

### GitHub에 다시 업로드

레포 페이지에서 **Add file → Upload files**로 갱신된 `index.html`을 끌어다 놓고 **Commit changes**. GitHub Pages는 1~2분 안에 자동 반영됩니다. 학생들에게는 같은 URL을 그대로 쓰시면 됩니다.

브라우저 캐시 때문에 학생들에게 이전 버전이 보일 수 있습니다. 강제 새로고침(Cmd+Shift+R / Ctrl+Shift+R) 안내를 함께 전달하시면 좋습니다.

---

## 비표준 학회 PDF 대응

본 파서는 표준적인 IAQVEC·IBPSA 학회 PDF 형식을 가정합니다. 다른 학회 PDF는 부분 수정이 필요할 수 있습니다. `build.py --dry-run`을 먼저 돌려 보고, 다음 신호를 확인하세요.

### 진단

```bash
python3 build.py /path/to/pdf.pdf --id test --name "Test" --dry-run
```

출력에서 다음을 확인:

| 신호 | 의미 | 조치 |
|---|---|---|
| `sessions=0` 또는 `papers=0` | 세션 헤더를 전혀 인식하지 못함 | `parser.py`의 `SESS_RE` 보강 |
| `[경고] orphan papers: N` | 일부 세션 헤더만 파싱 실패 | `TIME_LOC_RE` 등 보강 |
| 발표 수가 PDF에 적힌 수보다 적음 | 표 컬럼 좌표가 다름 | `AUTHOR_X`, `TITLE_X` 상수 조정 |

### parser.py 주요 수정 지점

`parser.py` 상단의 상수와 정규식:

```python
AUTHOR_X = 190         # author 컬럼 시작 x 좌표
TITLE_X  = 335         # title 컬럼 시작 x 좌표

DAY_RE      = ...      # "Day 2: 5/19/2026 (Tue)" 패턴
SESS_RE     = ...      # "Session 1 1-1 Indoor Air Quality" 패턴
TIME_LOC_RE = ...      # "11:00 - 12:30 Location: SGM 123 / Session chair: ..." 패턴
```

PDF의 실제 좌표를 보려면 pdfplumber로 단어별 위치를 출력해 확인:

```bash
python3 -c "
import pdfplumber
with pdfplumber.open('/path/to/pdf.pdf') as pdf:
    for w in pdf.pages[0].extract_words()[:40]:
        print(f\"{w['top']:6.1f} {w['x0']:6.1f}  {w['text']}\")
"
```

이 출력을 보고 'Author', 'Title' 같은 헤더의 x 좌표를 파악해 조정합니다.

---

## 라이선스

내부 사용 목적. 외부 공유 시 학교/연구실 정책을 따릅니다.

## 문의

건국대학교 건축대학 ecosoop@gmail.com
