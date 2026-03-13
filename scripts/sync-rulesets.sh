#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-check}"
if [[ "$MODE" != "check" && "$MODE" != "apply" ]]; then
  echo "Usage: $0 [check|apply]" >&2
  exit 2
fi

REPO="${GITHUB_REPOSITORY:-}"
if [[ -z "$REPO" ]]; then
  REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required" >&2
  exit 2
fi

shopt -s nullglob
files=(infra/github-rulesets/*.json)
if [[ ${#files[@]} -eq 0 ]]; then
  echo "No ruleset files found in infra/github-rulesets" >&2
  exit 2
fi

normalize_desired() {
  jq -S '
    {
      name,
      target,
      enforcement,
      bypass_actors: (.bypass_actors // []),
      conditions,
      rules: (
        .rules
        | map(
            if .type == "required_status_checks" then
              .parameters.required_status_checks = (
                .parameters.required_status_checks
                | map({context})
                | sort_by(.context)
              )
            elif .type == "pull_request" then
              .parameters.allowed_merge_methods = (
                (.parameters.allowed_merge_methods // []) | sort
              )
            else .
            end
          )
        | sort_by(.type)
      )
    }
  ' "$1"
}

normalize_live() {
  jq -S '
    {
      name,
      target,
      enforcement,
      bypass_actors: (.bypass_actors // []),
      conditions,
      rules: (
        .rules
        | map(
            if .type == "required_status_checks" then
              .parameters.required_status_checks = (
                .parameters.required_status_checks
                | map({context})
                | sort_by(.context)
              )
            elif .type == "pull_request" then
              .parameters.allowed_merge_methods = (
                (.parameters.allowed_merge_methods // []) | sort
              )
            else .
            end
          )
        | sort_by(.type)
      )
    }
  '
}

status=0
for file in "${files[@]}"; do
  name="$(jq -r '.name // empty' "$file")"
  target="$(jq -r '.target // empty' "$file")"
  if [[ -z "$name" || -z "$target" ]]; then
    echo "Missing required fields (name/target) in $file" >&2
    status=1
    continue
  fi

  match_id="$(
    gh api "repos/$REPO/rulesets" --jq \
      ".[] | select(.name == \"$name\" and .target == \"$target\") | .id" \
    | head -n1
  )"

  if [[ -z "$match_id" ]]; then
    echo "Processing ruleset name=$name target=$target from $file"
    echo "  Ruleset not found"
    if [[ "$MODE" == "check" ]]; then
      status=1
      continue
    fi

    payload_file="$(mktemp)"
    normalize_desired "$file" > "$payload_file"
    gh api -X POST "repos/$REPO/rulesets" --input "$payload_file" >/dev/null
    rm -f "$payload_file"
    echo "  Created"
    continue
  fi

  echo "Processing ruleset id=$match_id name=$name target=$target from $file"
  live_json="$(gh api "repos/$REPO/rulesets/$match_id")"
  desired_norm="$(normalize_desired "$file")"
  live_norm="$(printf '%s' "$live_json" | normalize_live)"

  if [[ "$desired_norm" == "$live_norm" ]]; then
    echo "  In sync"
    continue
  fi

  echo "  Drift detected"
  desired_file="$(mktemp)"
  live_file="$(mktemp)"
  printf '%s\n' "$desired_norm" > "$desired_file"
  printf '%s\n' "$live_norm" > "$live_file"
  echo "  Desired vs live diff:"
  diff -u "$desired_file" "$live_file" || true
  rm -f "$desired_file" "$live_file"

  if [[ "$MODE" == "check" ]]; then
    status=1
    continue
  fi

  payload_file="$(mktemp)"
  normalize_desired "$file" > "$payload_file"
  gh api -X PUT "repos/$REPO/rulesets/$match_id" --input "$payload_file" >/dev/null
  rm -f "$payload_file"
  echo "  Updated"
done

if [[ "$status" -ne 0 ]]; then
  echo "Ruleset drift detected (mode=$MODE)" >&2
fi

exit "$status"
