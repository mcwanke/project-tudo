#!/usr/bin/env bash
# One-off script to verify assumptions in docs/tududi-api-notes.md against a
# real Tududi instance before writing the polling service. Not part of the
# running app — delete once the API notes are confirmed.
#
# Usage:
#   TUDUDI_URL=https://your-host TUDUDI_TOKEN=tt_xxx ./scripts/verify-api.sh
#
# By default this only reads data (steps 1-2). Steps 3-4 mutate a task and
# are gated behind --mutate plus an explicit task uid, so you don't
# accidentally cancel/snooze something you care about.

set -euo pipefail

: "${TUDUDI_URL:?Set TUDUDI_URL, e.g. export TUDUDI_URL=https://your-host}"
: "${TUDUDI_TOKEN:?Set TUDUDI_TOKEN, e.g. export TUDUDI_TOKEN=tt_xxx}"

MUTATE=0
TASK_UID=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mutate)
            MUTATE=1
            shift
            ;;
        --uid)
            TASK_UID="${2:?--uid requires a value}"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

auth_header=(-H "Authorization: Bearer ${TUDUDI_TOKEN}")
json_header=(-H "Content-Type: application/json")

echo "== 1. Auth sanity check: GET /api/tasks?status=active&limit=1 =="
curl -s -o /dev/null -w "HTTP %{http_code}\n" "${auth_header[@]}" \
    "${TUDUDI_URL}/api/tasks?status=active&limit=1"
echo

echo "== 2. Sample open task shape =="
sample_json=$(curl -s "${auth_header[@]}" "${TUDUDI_URL}/api/tasks?status=active&limit=1")
echo "$sample_json" | python3 -m json.tool
echo

if [[ $MUTATE -eq 0 ]]; then
    echo "Skipping mutation steps (3-4). Re-run with --mutate --uid <uid> to test"
    echo "status:\"cancelled\" and due_date write format against one real task."
    echo "Pick a uid from the sample above, ideally a throwaway/test task."
    exit 0
fi

if [[ -z "$TASK_UID" ]]; then
    echo "Error: --mutate requires --uid <task_uid>" >&2
    exit 1
fi

echo "== 3a. PATCH status:\"cancelled\" (string) on uid=${TASK_UID} =="
curl -s -w "\nHTTP %{http_code}\n" -X PATCH "${auth_header[@]}" "${json_header[@]}" \
    -d '{"status":"cancelled"}' \
    "${TUDUDI_URL}/api/task/${TASK_UID}"
echo
echo "If that did not return the task with status cancelled/5, try the integer form:"
echo "  curl -s -w '\\nHTTP %{http_code}\\n' -X PATCH ${auth_header[*]} ${json_header[*]} -d '{\"status\":5}' '${TUDUDI_URL}/api/task/${TASK_UID}'"
echo

echo "== 4. PATCH due_date (snooze format) on uid=${TASK_UID} =="
one_hour_later=$(python3 -c "
import datetime
print((datetime.datetime.utcnow() + datetime.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S.000Z'))
")
curl -s -w "\nHTTP %{http_code}\n" -X PATCH "${auth_header[@]}" "${json_header[@]}" \
    -d "{\"due_date\":\"${one_hour_later}\"}" \
    "${TUDUDI_URL}/api/task/${TASK_UID}"
echo
