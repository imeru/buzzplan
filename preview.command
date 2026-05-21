#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

PORT=8080
URL="http://localhost:${PORT}/"

# 포트가 이미 사용 중이면 다음 빈 포트로
while lsof -i ":${PORT}" >/dev/null 2>&1; do
  PORT=$((PORT + 1))
done
URL="http://localhost:${PORT}/"

echo "▶ 로컬 서버 시작: ${URL}"
python3 -m http.server "${PORT}" >/dev/null 2>&1 &
SERVER_PID=$!

cleanup() {
  echo ""
  echo "■ 서버 종료 (PID ${SERVER_PID})"
  kill "${SERVER_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# 서버가 뜰 때까지 잠깐 대기
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -s -o /dev/null "${URL}"; then break; fi
  sleep 0.2
done

# Chrome 으로 열기 (없으면 기본 브라우저)
if [ -d "/Applications/Google Chrome.app" ]; then
  open -a "Google Chrome" "${URL}"
else
  echo "(Google Chrome 을 찾을 수 없어 기본 브라우저로 엽니다)"
  open "${URL}"
fi

echo ""
echo "이 창을 닫거나 Ctrl+C 를 누르면 서버가 종료됩니다."
wait "${SERVER_PID}"
