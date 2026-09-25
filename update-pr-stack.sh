#!/usr/bin/env bash
# Rebuild local/pr-stack on top of latest upstream + PR branches, install side-by-side.
# Never touches stable/current/launcher — those stay on the official release.
# Usage: ./update-pr-stack.sh [--fast]
#   --fast: plain release profile (quicker, larger binary). Default: release-lto.
set -euo pipefail
cd "$(dirname "$0")"

echo "=== fetch ==="
git fetch origin
git fetch fork

echo "=== recreate local/pr-stack off origin/master ==="
git checkout -q master 2>/dev/null || git checkout -q -b master origin/master
git branch -D local/pr-stack 2>/dev/null || true
git checkout -q -b local/pr-stack origin/master

for b in feat/compaction-hooks feat/tool-result-clearing feat/pressure-notices \
         feat/pre-request-transform feat/recurring-schedules feat/span-citations \
         feat/tunable-dedup-rrf feat/repomap-provider feat/memory-age-hedge \
         feat/offload-with-ref feat/summary-schema feat/progress-file; do
  # NOTE: append every new feature branch here, or the next rebuild drops it.
  echo "=== merge $b ==="
  if ! git merge --no-edit "$b"; then
    echo "CONFLICT in $b — resolve manually, commit, then run ./update-pr-stack.sh --resume-build."
    echo "Or to skip the rebuild: cargo build --release -p jcode --bin jcode"
    exit 1
  fi
done

if [[ "${1:-}" == "--resume-build" ]]; then
  echo "=== resuming from existing resolution ==="
elif git grep -l "<<<<<<<" -- . | head -3; then
  echo "Leftover conflict markers. Resolve, commit, re-run with --resume-build."
  exit 1
fi

echo "=== check ==="
if cargo check --workspace 2>&1 | grep -E "^error"; then
  echo "CHECK FAILED"
  exit 1
fi
echo "check clean"

echo "=== build ==="
if [[ "${1:-}" == "--fast" ]]; then
  cargo build --release -p jcode --bin jcode
  BIN=target/release/jcode
else
  cargo build --profile release-lto -p jcode --bin jcode
  BIN=target/release-lto/jcode
fi

echo "=== versioned side-by-side install (stable untouched) ==="
HASH=$(git rev-parse --short=12 HEAD)
DEST=~/.jcode/builds/versions/pr-stack-$HASH
mkdir -p "$DEST"
install -m 755 "$BIN" "$DEST/jcode"
ln -sfn "$DEST/jcode" ~/.jcode/builds/pr-stack
echo "Installed: $DEST/jcode"
echo "Symlink:   ~/.jcode/builds/pr-stack/jcode"
echo ""
echo "Run it:    ~/.jcode/builds/pr-stack/jcode"
echo "Make it your launcher (reversible):"
echo "  ln -sfn ~/.jcode/builds/pr-stack/jcode ~/.local/bin/jcode"
echo "Back to stable:"
echo "  ln -sfn ~/.jcode/builds/current/jcode ~/.local/bin/jcode   # current still points at stable"
