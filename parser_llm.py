#!/usr/bin/env python3
"""
parser_llm.py — LLM 기반 범용 학회 스케줄 추출기 (Tier 2).

규칙 파서(parser.py, parser_sarek*.py)가 처음 보는 PDF 레이아웃은 좌표·정규식
하드코딩으로 처리할 수 없다. 이 파서는 Claude API의 structured output으로
어떤 레이아웃이든 표준 스키마 v2 JSON을 추출한다.

동작 방식:
  1. PDF를 N페이지 청크로 분할 (pypdf)
  2. 각 청크를 base64 document로 Claude에 전달, JSON schema로 강제 추출
  3. 이전 청크의 마지막 세션 정보를 다음 청크에 힌트로 전달 (페이지 걸침 처리)
  4. 청크 결과 병합 + 중복 제거 → finalize_v2 → validate_v2

사용 예:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 parser_llm.py conference.pdf --id acme-2027 --name "ACME 2027" \
        --timezone Asia/Seoul --out data/acme-2027.json

    # 파이프라인 통합 (build.py가 검증·등록까지 수행)
    python3 build.py conference.pdf --parser parser_llm.py --id acme-2027 \
        --name "ACME 2027" --timezone Asia/Seoul

    # 저렴한 파일럿 테스트 (앞 4페이지만)
    python3 parser_llm.py conference.pdf --id test --name "Test" --max-pages 4

주의: LLM 추출은 누락·오인식이 가능하다. build.py --dry-run으로 세션/발표 수를
프로그램북 목차와 대조하고, 스팟체크 후 사용할 것.
"""
import argparse
import base64
import io
import json
import pathlib
import sys

try:
    import anthropic
except ImportError:
    sys.exit("anthropic SDK가 필요합니다: pip3 install anthropic")
try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    sys.exit("pypdf가 필요합니다: pip3 install pypdf")

from parser_utils import finalize_v2, validate_v2

DEFAULT_MODEL = "claude-opus-4-8"

# 구조화 출력 스키마 — 스키마 v2의 sessions/papers와 1:1 대응.
# structured outputs 제약: 모든 object에 additionalProperties:false + required 필수,
# min/max 계열 제약 불가. 선택 필드는 ["string","null"] 유니온으로 표현.
EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "sessions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id":          {"type": "string"},
                    "day":         {"type": ["integer", "null"]},
                    "date":        {"type": ["string", "null"]},
                    "track_title": {"type": ["string", "null"]},
                    "start":       {"type": ["string", "null"]},
                    "end":         {"type": ["string", "null"]},
                    "building":    {"type": ["string", "null"]},
                    "room":        {"type": ["string", "null"]},
                    "floor":       {"type": ["integer", "null"]},
                    "chair":       {"type": ["string", "null"]},
                    "type": {
                        "type": "string",
                        "enum": ["oral", "poster", "keynote", "social", "break"],
                    },
                },
                "required": ["id", "day", "date", "track_title", "start", "end",
                             "building", "room", "floor", "chair", "type"],
                "additionalProperties": False,
            },
        },
        "papers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "paper_no":   {"type": ["string", "null"]},
                    "session_id": {"type": "string"},
                    "authors":    {"type": ["string", "null"]},
                    "title":      {"type": "string"},
                    "start":      {"type": ["string", "null"]},
                    "end":        {"type": ["string", "null"]},
                },
                "required": ["paper_no", "session_id", "authors", "title",
                             "start", "end"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["sessions", "papers"],
    "additionalProperties": False,
}

PROMPT_TEMPLATE = """\
이 PDF는 학회 프로그램북의 일부입니다 (전체 {total}페이지 중 {page_range}페이지).
학회: {conf_name}

세션과 발표(논문) 정보를 모두 추출하세요. 규칙:

- **세션**: 고유 id(프로그램북에 인쇄된 표기 그대로, 예: "1-A", "2-3"), 날짜(ISO
  YYYY-MM-DD), 시작/종료 시간(**24시간제 HH:MM** — 오후 1:30은 "13:30"),
  트랙/세션 제목, 발표장(building/room — 예: "제3회장"은 building "회장",
  room "3"), 층(floor, 방 번호 첫 자리 등으로 추정 가능하면), 좌장(chair),
  타입(oral/poster/keynote/social/break).
- **발표**: 발표번호(paper_no — 인쇄된 그대로), 소속 세션 id(session_id),
  저자(authors — 쉼표 구분 한 문자열), 제목(title), 명시된 발표별 시작/종료
  시간이 있으면 start/end(24시간제).
- 휴식/중식/총회 같은 비발표 항목은 세션으로 넣되 type을 break/social로 하고
  papers는 만들지 마세요.
- 페이지 상단에 세션 헤더 없이 발표 목록이 이어지면 **이전 페이지에서 계속되는
  세션**입니다. 아래 컨텍스트의 세션 id를 session_id로 사용하세요.
- 확실하지 않은 필드는 null로 두세요. 추측으로 채우지 마세요.
- 표지·목차·광고·안내문 페이지에는 추출할 것이 없으면 빈 배열을 반환하세요.

{context_hint}
"""


def chunk_pdf(pdf_path, pages_per_chunk, max_pages=None):
    """PDF를 (base64 문자열, 페이지범위 라벨) 청크 리스트로 분할."""
    reader = PdfReader(pdf_path)
    total = len(reader.pages)
    limit = min(total, max_pages) if max_pages else total
    chunks = []
    for start in range(0, limit, pages_per_chunk):
        end = min(start + pages_per_chunk, limit)
        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])
        buf = io.BytesIO()
        writer.write(buf)
        b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")
        chunks.append((b64, f"{start + 1}-{end}", total))
    return chunks


def extract_chunk(client, model, b64_pdf, page_range, total, conf_name, context_hint):
    """청크 하나를 Claude에 보내 sessions/papers를 추출."""
    prompt = PROMPT_TEMPLATE.format(
        total=total, page_range=page_range, conf_name=conf_name,
        context_hint=context_hint or "(첫 청크 — 이전 컨텍스트 없음)")

    with client.messages.stream(
        model=model,
        max_tokens=64000,
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": EXTRACT_SCHEMA}},
        messages=[{
            "role": "user",
            "content": [
                {"type": "document",
                 "source": {"type": "base64", "media_type": "application/pdf",
                            "data": b64_pdf}},
                {"type": "text", "text": prompt},
            ],
        }],
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "max_tokens":
        raise RuntimeError(
            f"페이지 {page_range}: 출력이 max_tokens에서 잘렸습니다. "
            "--pages-per-chunk를 줄여 다시 실행하세요.")

    text = next(b.text for b in message.content if b.type == "text")
    data = json.loads(text)
    usage = message.usage
    return data, usage


def build_context_hint(sessions):
    """다음 청크에 전달할 '진행 중인 세션' 힌트."""
    if not sessions:
        return None
    last = sessions[-1]
    return (
        "이전 청크 컨텍스트: 마지막으로 추출된 세션은 "
        f"id={last.get('id')!r}, 날짜={last.get('date')!r}, "
        f"발표장={last.get('building')!r} {last.get('room')!r}, "
        f"시간={last.get('start')}-{last.get('end')} 입니다. "
        "이 청크 첫 페이지가 세션 헤더 없이 발표 목록으로 시작하면 "
        "그 발표들은 위 세션에 속합니다."
    )


def merge_results(results):
    """청크별 추출 결과를 병합. 세션은 id, 발표는 (session_id, paper_no, title)로 dedupe."""
    sessions, papers = [], []
    seen_s, seen_p = {}, set()
    for data in results:
        for s in data.get("sessions", []):
            sid = s.get("id")
            if sid in seen_s:
                # 페이지 걸침으로 재등장한 세션: 비어 있던 필드를 채움
                prev = seen_s[sid]
                for k, v in s.items():
                    if prev.get(k) in (None, "") and v not in (None, ""):
                        prev[k] = v
            else:
                seen_s[sid] = s
                sessions.append(s)
        for p in data.get("papers", []):
            key = (p.get("session_id"), p.get("paper_no"), p.get("title"))
            if key not in seen_p:
                seen_p.add(key)
                papers.append(p)
    return sessions, papers


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", help="학회 프로그램북 PDF")
    ap.add_argument("--id",   required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out",  default="schedule.json")
    ap.add_argument("--timezone", default=None,
                    help="IANA timezone (예: Asia/Seoul)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--pages-per-chunk", type=int, default=6)
    ap.add_argument("--max-pages", type=int, default=None,
                    help="앞 N페이지만 처리 (파일럿 테스트용)")
    args = ap.parse_args()

    if not pathlib.Path(args.pdf).exists():
        sys.exit(f"PDF를 찾을 수 없습니다: {args.pdf}")

    chunks = chunk_pdf(args.pdf, args.pages_per_chunk, args.max_pages)
    total_pages = chunks[0][2] if chunks else 0
    print(f"Conference: {args.name}  (id={args.id})")
    print(f"PDF {total_pages}페이지 → {len(chunks)}청크 "
          f"(청크당 {args.pages_per_chunk}페이지, model={args.model})")

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 또는 프로필에서 인증

    results = []
    context_hint = None
    in_tok = out_tok = 0
    for i, (b64, page_range, total) in enumerate(chunks):
        print(f"  [{i + 1}/{len(chunks)}] 페이지 {page_range} 추출 중...", flush=True)
        try:
            data, usage = extract_chunk(
                client, args.model, b64, page_range, total, args.name, context_hint)
        except anthropic.AuthenticationError:
            sys.exit("인증 실패: ANTHROPIC_API_KEY를 설정하세요 "
                     "(https://platform.claude.com 에서 발급).")
        results.append(data)
        in_tok += usage.input_tokens + (usage.cache_read_input_tokens or 0)
        out_tok += usage.output_tokens
        print(f"       sessions +{len(data.get('sessions', []))}, "
              f"papers +{len(data.get('papers', []))}")
        context_hint = build_context_hint(data.get("sessions", [])) or context_hint

    sessions, papers = merge_results(results)

    out = {
        "conference": {"id": args.id, "name": args.name},
        "sessions": sessions,
        "papers": papers,
    }
    # LLM에게 24h/ISO를 지시했지만 보증은 finalize_v2가 한다 (멱등)
    finalize_v2(out, timezone=args.timezone, pm_threshold=0)

    problems = validate_v2(out)
    if problems:
        print(f"[경고] v2 검증 {len(problems)}건:")
        for p in problems[:10]:
            print(f"  - {p}")

    sess_ids = {s["id"] for s in sessions}
    orphans = [p for p in papers if p.get("session_id") not in sess_ids]

    print(f"Sessions: {len(sessions)}")
    print(f"Papers:   {len(papers)}" + (f"  (orphan {len(orphans)})" if orphans else ""))
    print(f"토큰 사용: input≈{in_tok:,}, output≈{out_tok:,}")

    pathlib.Path(args.out).write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved → {args.out} ({pathlib.Path(args.out).stat().st_size} bytes)")


if __name__ == "__main__":
    main()
