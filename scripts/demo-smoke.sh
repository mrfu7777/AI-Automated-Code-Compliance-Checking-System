#!/usr/bin/env sh
set -eu

api_base_url=${1:-http://localhost:8000/api/v1}
report_file=$(mktemp)
trap 'rm -f "$report_file"' EXIT

scenario=$(curl --fail --silent --request POST "$api_base_url/demo/scenario")
project_id=$(echo "$scenario" | jq --raw-output .project_id)
rule_pack_id=$(echo "$scenario" | jq --raw-output .rule_pack_id)
run=$(curl --fail --silent --request POST \
  --header 'Content-Type: application/json' \
  --data "{\"project_id\":\"$project_id\",\"rule_pack_ids\":[\"$rule_pack_id\"],\"name\":\"Guided V1 demo\"}" \
  "$api_base_url/check-runs")
job_id=$(echo "$run" | jq --raw-output .job.id)
run_id=$(echo "$run" | jq --raw-output .run.id)
job_status=queued

for _attempt in $(seq 1 30); do
  job_status=$(curl --fail --silent "$api_base_url/jobs/$job_id" | jq --raw-output .status)
  if [ "$job_status" = "succeeded" ]; then
    break
  fi
  if [ "$job_status" = "failed" ]; then
    echo "The guided demo job failed: $job_id" >&2
    exit 1
  fi
  sleep 2
done

test "$job_status" = "succeeded"
curl --fail --silent "$api_base_url/check-runs/$run_id" |
  jq --exit-status '
    [.results[].status] | sort ==
    ["compliant", "compliant", "insufficient_information", "non_compliant"]' >/dev/null
curl --fail --silent "$api_base_url/check-runs/$run_id/reports/pdf" --output "$report_file"
head --bytes 4 "$report_file" | grep --quiet '%PDF'

echo "Guided demo passed."
echo "Project: $project_id"
echo "Check run: $run_id"
