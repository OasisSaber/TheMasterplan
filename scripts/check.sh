#!/bin/bash
# Authoritative repository validation entrypoint for TheMasterplan.

set -o pipefail

FAILED=0
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR" || exit 1

if ! command -v git >/dev/null 2>&1; then
    echo "ERROR: Git is required for repository validation." >&2
    exit 1
fi
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: repository validation must run inside a Git worktree." >&2
    exit 1
fi

PYTHON_FILES="$(mktemp)" || exit 1
trap 'rm -f "$PYTHON_FILES"' EXIT
if ! git ls-files -z -- 'scripts/*.py' >"$PYTHON_FILES"; then
    echo "ERROR: unable to enumerate tracked Python validation scripts." >&2
    exit 1
fi

PYTHON=""
if python3 -c "import sys" >/dev/null 2>&1; then
    PYTHON="python3"
elif python -c "import sys" >/dev/null 2>&1; then
    PYTHON="python"
fi

echo "=== Repository check ==="
echo ""

echo "--- Check 1: Python syntax ---"
PYTHON_ERRORS=0
if [ -z "$PYTHON" ]; then
    echo "  UNAVAILABLE: Python is required."
    PYTHON_ERRORS=$((PYTHON_ERRORS + 1))
else
    while IFS= read -r -d '' python_file; do
        if ! "$PYTHON" - "$python_file" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
except SyntaxError as error:
    print(
        f"  PYTHON SYNTAX ERROR: {path}:{error.lineno}: {error.msg}",
        file=sys.stderr,
    )
    raise SystemExit(1)
PY
        then
            PYTHON_ERRORS=$((PYTHON_ERRORS + 1))
        fi
    done <"$PYTHON_FILES"
fi

if [ "$PYTHON_ERRORS" -eq 0 ]; then
    echo "  All tracked Python validation scripts compile."
else
    echo "  $PYTHON_ERRORS Python syntax error(s)."
    FAILED=$((FAILED + 1))
fi
echo ""

echo "--- Check 2: Validation unit tests ---"
if [ -z "$PYTHON" ]; then
    echo "  UNAVAILABLE: Python is required."
    FAILED=$((FAILED + 1))
elif "$PYTHON" -m unittest discover -s scripts -p 'test_*.py'; then
    echo "  Validation unit tests passed."
else
    echo "  Validation unit tests failed."
    FAILED=$((FAILED + 1))
fi
echo ""

echo "--- Check 3: Technical validation ---"
if bash scripts/validate.sh; then
    echo "  Technical validation passed."
else
    echo "  Technical validation failed."
    FAILED=$((FAILED + 1))
fi
echo ""

echo "--- Check 4: Repository collaboration record ---"
if [ "${GITHUB_EVENT_NAME:-}" != "pull_request" ]; then
    echo "  Not a PR event; local structure/compatibility tests cover this gate."
elif [ -z "$PYTHON" ] || [ -z "${GITHUB_EVENT_PATH:-}" ]; then
    echo "  UNAVAILABLE: Python and PR event metadata are required."
    FAILED=$((FAILED + 1))
elif "$PYTHON" scripts/validate_pr_body.py --require-collaboration --event-file "$GITHUB_EVENT_PATH"; then
    echo "  Collaboration record structure passed (not identity or native review approval)."
else
    echo "  Collaboration record validation failed."
    FAILED=$((FAILED + 1))
fi
echo ""

echo "=== Repository check results ==="
if [ "$FAILED" -eq 0 ]; then
    echo "All repository checks passed."
else
    echo "$FAILED repository check category or categories failed."
fi
exit "$FAILED"
