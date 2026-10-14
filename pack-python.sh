#!/bin/bash
# Pack python/ into OSWarp-python.zip. The archive root is an OSWarp folder.
set -euo pipefail
root=$(cd "$(dirname "$0")" && pwd)
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
mkdir "$stage/OSWarp"
rsync -a \
  --exclude '__pycache__/' \
  --exclude 'tests/' \
  --exclude '.pytest_cache/' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  "$root/python/" "$stage/OSWarp/"
out="$root/OSWarp-python.zip"
rm -f "$out"
(cd "$stage" && zip -r "$out" OSWarp)
echo "Wrote $out"
