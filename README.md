# BuzzPlan — Conference Schedule Planner

학회 세션 PDF에서 발표 정보를 추출하여, 듣고 싶은 발표를 선택하고
일정·동선을 자동으로 계획해 주는 도구. 한 URL에서 여러 학회를 함께 다룰 수 있습니다.

배포본: [https://imeru.github.io/buzzplan/](https://imeru.github.io/buzzplan/)

---

## 현재 등록된 학회

| ID | 이름 | 일시 | 회장 | 세션 | 발표 |
|---|---|---|---|---|---|
| `sarek-2026-summer` | 대한설비공학회 2026 하계학술발표대회 | 2026/6/24–26 (평창 알펜시아) | 제1~제13회장 | — | — |
| `iaqvec-2026` | IAQVEC 2026 | 2026/5/19–21 (USC) | SGM·GFS·VHE | 60 | 321 |
| `sarek-2025-winter` | 대한설비공학회 2025 동계학술발표대회 | 2025/11/28 (한국과학기술회관) | 제1~제7회장 | 34 | 159 |
| `sarek-2025-summer` | 대한설비공학회 2025 하계학술발표대회 | 2025/6/19–20 (평창 알펜시아) | 제1~제12회장 | 66 | 312 |

기본 학회는 SAREK 2026 하계이며, URL 끝에 `?conf=<id>`를 붙이면 다른 학회로 전환됩니다. 헤더 드롭다운으로도 즉시 전환 가능합니다.

---

## 폴더 구조

```
buzzplan/
├── index.html                    # 도구 본체 (학회별 데이터를 부팅 시 fetch)
├── conferences.json              # 사용 가능한 학회 목록 + default
├── assets/
│   ├── buzzplan-bee.png          # 헤더 로고 (벌 아이콘 1x)
│   ├── buzzplan-bee@2x.png       # 헤더 로고 (2x retina)
│   ├── buzzplan-logo.png         # 파비콘용 풀 로고
│   └── buzzplan-logo@2x.png
├── data/
│   ├── iaqvec-2026.json
│   ├── sarek-2025-winter.json
│   ├── sarek-2025-summer.json
│   └── sarek-2026-summer.json
├── parser.py                     # IAQVEC·IBPSA 형식 PDF 파서
├── parser_sarek.py               # SAREK 동계(가로 2단 컬럼) 파서
├── parser_sarek_summer.py        # SAREK 하계(세로 1단 컬럼) 파서
├── build.py                      # PDF → JSON → 학회 등록 자동화
└── README.md
```

학회를 추가하면 `data/<conf-id>.json`이 새로 생기고 `conferences.json`에 자동 등록됩니다.

---

## 학생용 사용 안내

브라우저에서 사이트 URL을 열면 시작됩니다.

| 접근 방식 | URL |
|---|---|
| 기본 학회 (SAREK 2026 하계) | `https://imeru.github.io/buzzplan/` |
| SAREK 2026 하계 명시 | `…/?conf=sarek-2026-summer` |
| IAQVEC 2026 | `…/?conf=iaqvec-2026` |
| SAREK 2025 동계 | `…/?conf=sarek-2025-winter` |
| SAREK 2025 하계 | `…/?conf=sarek-2025-summer` |
| 다른 학회로 전환 | 헤더 드롭다운 또는 URL의 `?conf=` 변경 |

**기본 흐름**
1. 좌측 필터(검색·Day·트랙·회장)로 관심 세션을 좁힙니다.
2. 발표 옆 체크박스로 듣고 싶은 발표를 선택합니다.
3. 상단 **📅 내 일정** 탭에서 리스트·시간표 두 가지로 일정을 확인합니다.
4. 학회 종료 후 발표별로 별점·메모를 남길 수 있습니다.
5. 상단 **📅 ICS**·**📊 CSV** 버튼으로 일정을 캘린더 앱이나 엑셀로 내보낼 수 있습니다.
6. 컴퓨터에서 짠 일정을 모바일에서 이어 보려면 헤더의 **🔑 로그인(구글)**으로 같은 계정에 로그인하면 자동 동기화됩니다. 자세한 내용은 아래 "기기 간 동기화" 섹션 참고.

**데이터 저장**
로그인하지 않으면(게스트 모드) 선택·별점·메모는 **본인 브라우저의 localStorage**에 학회별로 분리 저장되어 그 기기에만 남습니다.
헤더에서 **🔑 로그인(구글)**을 하면 같은 데이터가 클라우드에도 저장되어 다른 기기에서도 이어볼 수 있습니다.

---

## 🔄 기기 간 동기화 (구글 로그인)

로그인은 선택 사항입니다. 로그인하지 않아도 도구는 그대로 동작하며, 이 경우 데이터는 지금 쓰는 기기의 브라우저에만 저장됩니다(게스트 모드).

**로그인 방법**
헤더의 **🔑 로그인(구글)** 버튼을 눌러 구글 계정으로 로그인합니다.

**동기화되는 데이터**
발표 **선택 여부·별점·메모**가 학회별로 저장되고, 같은 계정으로 로그인한 모든 기기에 실시간(1~2초 내)으로 반영됩니다.

**다른 기기에서 이어 보기**
컴퓨터에서 고른 일정을 모바일에서 보고 싶다면(또는 그 반대) 그 기기에서도 같은 구글 계정으로 로그인하기만 하면 됩니다. 그것으로 끝입니다.

오프라인 상태에서도 계속 사용할 수 있고, 다시 연결되면 그동안의 변경 사항이 자동으로 병합됩니다.

**로그인하지 않으면?**
게스트 모드로 동작합니다. 선택·별점·메모는 그 브라우저(기기)에만 localStorage로 저장되고, 다른 기기와는 동기화되지 않습니다. 언제든 로그인하면 그 시점부터 동기화가 시작됩니다.

**문제 해결**
헤더의 로그인 버튼이 **⚠️ 동기화 오류**로 바뀌면 동기화가 실패한 상태입니다. 버튼을 눌렀을 때 뜨는 안내 메시지를 확인하세요(권한 오류인 경우 Firestore 설정 문제이니 관리자에게 문의).

---

## GitHub Pages 배포

### 최초 1회

1. github.com에서 **New repository** → `buzzplan` (또는 원하는 이름) → **Public** → Create.
2. 본 폴더의 모든 파일·폴더를 **Add file → Upload files**로 끌어다 놓고 **Commit changes**.
   - `data/`·`assets/` 폴더도 함께 드래그.
3. **Settings → Pages** → Source: `main` 브랜치, `/ (root)` → **Save**.
4. 1~2분 후 페이지 상단에 URL이 표시됩니다.

이후 학생들에게는 그 URL 하나만 공유하면 됩니다.

### 다음 학회 추가

학회마다 PDF 형식이 다르므로 적절한 파서를 선택해 실행합니다.

| 학회 유형 | 파서 |
|---|---|
| IAQVEC·IBPSA·ASHRAE 등 영문 표 형식 | `parser.py` |
| SAREK 동계 (가로 2단) | `parser_sarek.py` |
| SAREK 하계 (세로 1단, 다일자) | `parser_sarek_summer.py` |
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
```

`build.py`가 자동으로 다음을 수행합니다.
1. 지정한 파서로 PDF 파싱 + 검증 (세션·발표 수, orphan 확인)
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

같은 ID로 재빌드하면 그 학회 학생들의 평점·메모는 그대로 유지됩니다.

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

기존 세 파서는 다음 가정을 합니다.

| 파서 | 가정 |
|---|---|
| `parser.py` | 세로 페이지, 1단 컬럼, 표 형식. 영문. 발표 시간은 세션 전체 시간 → 15분 분할 |
| `parser_sarek.py` | 가로 페이지(2단 컬럼), 1일, 발표마다 명시 시간 (HH:MM-HH:MM), `25-W-NNN` |
| `parser_sarek_summer.py` | 세로 페이지, 1단 컬럼, 다일자(subsection 헤더에 일자 prefix), 발표마다 명시 시간, `(26-S-NNN)` |

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

별도 파서 파일을 만들고 `build.py --parser <새파서>.py` 옵션으로 사용합니다. 파서는 다음 JSON 스키마를 출력하면 됩니다.

```json
{
  "conference": { "id": "...", "name": "..." },
  "sessions": [
    {
      "id": "1-A",
      "block": 1,
      "day": 1,
      "date": "11/28/2025",
      "track_title": "...",
      "start": "08:50",
      "end": "10:05",
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

`paper.start` / `paper.end`가 있으면 그대로 사용되고, 없으면 세션 시간을 15분씩 분할해 자동 계산합니다.

---

## 라이선스

내부 사용 목적. 외부 공유 시 학교/연구실 정책을 따릅니다.

## 문의

건국대학교 건축대학 ecosoop@gmail.com
