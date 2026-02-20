#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8001}"
TEACHER="${TEACHER:-teacher_001}"
STUDENT="${STUDENT:-20230001}"

WORK_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

PDF_FILE="${WORK_DIR}/demo.pdf"
ATTACH_FILE="${WORK_DIR}/guide.txt"
printf "%%PDF-1.4\n%% minimal\n" > "${PDF_FILE}"
printf "attachment text\n" > "${ATTACH_FILE}"

echo "[1] create course"
COURSE_JSON="$(curl -sS -X POST "${BASE_URL}/api/teacher/courses" -H "Content-Type: application/json" -d "{
  \"name\": \"PG Smoke Course\",
  \"description\": \"pg-smoke\",
  \"teacher_username\": \"${TEACHER}\"
}")"
COURSE_ID="$(python -c "import json,sys; print((json.loads(sys.argv[1]).get('id') or ''))" "${COURSE_JSON}")"
test -n "${COURSE_ID}"

echo "[2] create experiment"
EXPERIMENT_JSON="$(curl -sS -X POST "${BASE_URL}/api/experiments" -H "Content-Type: application/json" -d "{
  \"title\": \"PG Smoke Experiment\",
  \"description\": \"pg-smoke-experiment\",
  \"created_by\": \"${TEACHER}\",
  \"course_id\": \"${COURSE_ID}\",
  \"course_name\": \"PG Smoke Course\",
  \"published\": true
}")"
EXPERIMENT_ID="$(python -c "import json,sys; print((json.loads(sys.argv[1]).get('id') or ''))" "${EXPERIMENT_JSON}")"
test -n "${EXPERIMENT_ID}"

echo "[3] student start experiment"
START_JSON="$(curl -sS -X POST "${BASE_URL}/api/student-experiments/start/${EXPERIMENT_ID}?student_id=${STUDENT}")"
STUDENT_EXP_ID="$(python -c "import json,sys; print((json.loads(sys.argv[1]).get('student_experiment_id') or ''))" "${START_JSON}")"
test -n "${STUDENT_EXP_ID}"

echo "[4] submit experiment"
curl -sS -X POST "${BASE_URL}/api/student-experiments/${STUDENT_EXP_ID}/submit" -H "Content-Type: application/json" -d '{
  "notebook_content": "{\"cells\":[],\"metadata\":{},\"nbformat\":4,\"nbformat_minor\":5}"
}' >/dev/null

echo "[5] upload submission pdf"
PDF_JSON="$(curl -sS -X POST "${BASE_URL}/api/student-experiments/${STUDENT_EXP_ID}/pdf" -F "file=@${PDF_FILE};type=application/pdf")"
PDF_ID="$(python -c "import json,sys; print((json.loads(sys.argv[1]).get('id') or ''))" "${PDF_JSON}")"
test -n "${PDF_ID}"

echo "[6] teacher grade"
curl -sS -X POST "${BASE_URL}/api/teacher/grade/${STUDENT_EXP_ID}?score=96&teacher_username=${TEACHER}&comment=ok" >/dev/null

echo "[7] upload attachment metadata"
curl -sS -X POST "${BASE_URL}/api/teacher/experiments/${EXPERIMENT_ID}/attachments" -F "files=@${ATTACH_FILE};type=text/plain" >/dev/null

echo "[8] list attachments"
curl -sS "${BASE_URL}/api/experiments/${EXPERIMENT_ID}/attachments" >/dev/null

echo "[9] change security/password and read profile"
curl -sS -X POST "${BASE_URL}/api/student/profile/security-question" -H "Content-Type: application/json" -d "{
  \"student_id\": \"${STUDENT}\",
  \"security_question\": \"pet?\",
  \"security_answer\": \"cat\"
}" >/dev/null
curl -sS -X POST "${BASE_URL}/api/student/profile/change-password" -H "Content-Type: application/json" -d "{
  \"student_id\": \"${STUDENT}\",
  \"old_password\": \"123456\",
  \"new_password\": \"1234567\"
}" >/dev/null || true
curl -sS "${BASE_URL}/api/student/profile?student_id=${STUDENT}" >/dev/null

curl -sS -X POST "${BASE_URL}/api/teacher/profile/security-question" -H "Content-Type: application/json" -d "{
  \"teacher_username\": \"${TEACHER}\",
  \"security_question\": \"city?\",
  \"security_answer\": \"sz\"
}" >/dev/null
curl -sS -X POST "${BASE_URL}/api/teacher/profile/change-password" -H "Content-Type: application/json" -d "{
  \"teacher_username\": \"${TEACHER}\",
  \"old_password\": \"123456\",
  \"new_password\": \"1234567\"
}" >/dev/null || true

echo "SMOKE FLOW DONE"
