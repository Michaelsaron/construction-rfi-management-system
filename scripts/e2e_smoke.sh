#!/usr/bin/env bash
set -euo pipefail
API=${API_URL:-http://localhost:8000}
EMAIL=${ADMIN_EMAIL:-admin@example.com}
PASSWORD=${ADMIN_PASSWORD:-Admin123!}
STAMP=$(date +%s)
json(){ python3 -c "import sys,json; print(json.load(sys.stdin)$1)"; }
echo "[1/10] Login"
TOKEN=$(curl -fsS -X POST "$API/auth/login" -H 'Content-Type: application/json' -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | json "['access_token']")
H=(-H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json')
ME=$(curl -fsS "$API/me" -H "Authorization: Bearer $TOKEN"); ADMIN_UID=$(printf '%s' "$ME"|json "['id']")
echo "[2/10] Resolve project"
PROJECT=$(curl -fsS "$API/projects" -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; a=json.load(sys.stdin); print(a[0]['id'])")
echo "[3/10] Create summary"
SUMMARY=$(curl -fsS -X POST "$API/rfi-summaries" "${H[@]}" -d "{\"project_id\":$PROJECT,\"summary_reference\":\"E2E-$STAMP\",\"submission_date\":\"$(date +%F)\",\"entry_source\":\"ENGINEER_ENTRY\"}" | json "['id']")
echo "[4/10] Create individual RFI"
RFI=$(curl -fsS -X POST "$API/rfis" "${H[@]}" -d "{\"project_id\":$PROJECT,\"summary_id\":$SUMMARY,\"rfi_number\":\"E2E-$STAMP\",\"revision_no\":0,\"work_item\":\"Subgrade\",\"description\":\"Automated end-to-end test RFI\"}" | json "['id']")
echo "[5/10] Submit summary + activate RFI"
curl -fsS -X POST "$API/rfi-summaries/$SUMMARY/submit" -H "Authorization: Bearer $TOKEN" >/dev/null
curl -fsS -X POST "$API/rfis/$RFI/activate" -H "Authorization: Bearer $TOKEN" >/dev/null
echo "[6/10] Assign reviewer"
ASSIGN=$(curl -fsS -X POST "$API/rfis/$RFI/assign-reviewer" "${H[@]}" -d "{\"user_id\":$ADMIN_UID,\"reviewer_role\":\"WORK_INSPECTOR\",\"required\":true}" | json "['id']")
echo "[7/10] Reviewer response"
curl -fsS -X POST "$API/rfis/$RFI/review" "${H[@]}" -d "{\"assignment_id\":$ASSIGN,\"recommendation\":\"SATISFACTORY\",\"comment\":\"Automated smoke test review\"}" >/dev/null
echo "[8/10] RE/ARE final decision"
curl -fsS -X POST "$API/rfis/$RFI/decision" "${H[@]}" -d '{"decision":"APPROVED","comment":"Automated smoke test decision","override_used":false}' >/dev/null
echo "[9/10] Generate PDF + Excel"
curl -fsS "$API/reports/rfi/$RFI.pdf" -H "Authorization: Bearer $TOKEN" -o /tmp/rfi_e2e.pdf
curl -fsS "$API/reports/rfi-register.xlsx" -H "Authorization: Bearer $TOKEN" -o /tmp/rfi_e2e.xlsx
[ -s /tmp/rfi_e2e.pdf ] && [ -s /tmp/rfi_e2e.xlsx ]
echo "[10/10] Verify completed state"
STATE=$(curl -fsS "$API/rfis/$RFI" -H "Authorization: Bearer $TOKEN" | json "['rfi']['workflow_status']")
DECISION=$(curl -fsS "$API/rfis/$RFI" -H "Authorization: Bearer $TOKEN" | json "['rfi']['current_decision']")
[ "$STATE" = "COMPLETED" ] && [ "$DECISION" = "APPROVED" ]
echo "PASS: complete RFI workflow, API, DB writes/reads, review, decision and reports are working. Test RFI ID=$RFI"
