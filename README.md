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

새로운 학회의 PDF가 생기면 다음과 같이 갱신합니다.

### 1. 파서 실행 (로컬)

```bash
# pdfplumber 설치
pip install pdfplumber

# PDF에서 schedule.json 생성
python3 parser.py /path/to/new_conference.pdf \
  --id      iaqvec-2028 \
  --name    "IAQVEC 2028" \
  --out     schedule.json
```

`--id`는 학회마다 고유한 슬러그(소문자·하이픈). 이 ID를 기준으로 학생들의 평점·메모가 분리 저장됩니다.

### 2. JSON을 index.html에 임베드

도구는 단일 파일로 동작하도록 JSON을 HTML 안에 직접 임베드합니다.
다음 Python 한 줄로 갱신할 수 있습니다.

```bash
python3 -c "
import json, re, pathlib
data = json.load(open('schedule.json'))
embedded = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
html = pathlib.Path('index.html').read_text()
new_html, n = re.subn(r'let DATA = \{.*?\};\s*\n', f'let DATA = {embedded};\n', html, count=1, flags=re.DOTALL)
assert n == 1
pathlib.Path('index.html').write_text(new_html)
print(f'Updated index.html with {len(data[\"sessions\"])} sessions, {len(data[\"papers\"])} papers')
"
```

### 3. GitHub에 다시 업로드

레포 페이지에서 **Add file → Upload files**로 새 `index.html`을 올리고 commit. Pages 사이트는 1~2분 안에 자동 갱신됩니다.

---

## 비표준 학회 PDF 대응

본 파서는 표준적인 IAQVEC·IBPSA 학회 PDF 형식을 가정합니다. 다른 학회 PDF는 다음 케이스에서 부분 수정이 필요할 수 있습니다.

- 표 컬럼 좌표가 다른 경우 → `parser.py`의 `AUTHOR_X`, `TITLE_X` 상수 조정
- "Session N X-Y Title" 헤더 형식이 다른 경우 → `SESS_RE` 정규식 보강
- 시간·장소 줄 형식이 다른 경우 → `TIME_LOC_RE` 보강

파싱 결과 검증을 위해 다음 스크립트로 누락된 세션을 빠르게 확인할 수 있습니다.

```bash
python3 -c "
import json
d = json.load(open('schedule.json'))
sess = {s['id'] for s in d['sessions']}
orphan = [p['session_id'] for p in d['papers'] if p['session_id'] not in sess]
print(f'Sessions: {len(sess)}, Papers: {len(d[\"papers\"])}, Orphan papers: {len(orphan)}')
if orphan: print('Orphan session_ids:', sorted(set(orphan)))
"
```

`Orphan papers` 가 0이 아니면 해당 세션 헤더가 파싱되지 못한 것이므로, 파서를 보강합니다.

---

## 라이선스

내부 사용 목적. 외부 공유 시 학교/연구실 정책을 따릅니다.

## 문의

건국대학교 건축대학 ecosoop@gmail.com
