#!/usr/bin/env bash
# Resolve short bead ID to full ID via suffix matching.
# Usage: resolve-bead.sh <short-id>
# Returns: full bead ID to stdout
# Exit 1: no match, ambiguous, or empty argument

set -euo pipefail

SHORT="${1:-}"
if [ -z "$SHORT" ]; then
  echo "Usage: resolve-bead.sh <short-id>" >&2
  exit 1
fi

# Fast path: if br show succeeds, extract the full ID
FULL_ID=$(br show "$SHORT" --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['id'])" 2>/dev/null || true)
if [ -n "$FULL_ID" ]; then
  echo "$FULL_ID"
  exit 0
fi

# Suffix match against all beads
MATCHES=$(br list --status open --status in_progress --status closed --json | python3 -c "
import json,sys
d=json.load(sys.stdin)
matches=[i['id'] for i in d['issues'] if i['id'].endswith('$SHORT')]
print('\n'.join(matches) if matches else '')
")

if [ -z "$MATCHES" ]; then
  echo "No bead found matching '$SHORT'" >&2
  exit 1
fi

COUNT=$(echo "$MATCHES" | wc -l)
if [ "$COUNT" -gt 1 ]; then
  echo "Ambiguous '$SHORT' — matches $COUNT beads:" >&2
  echo "$MATCHES" >&2
  exit 1
fi

echo "$MATCHES"
