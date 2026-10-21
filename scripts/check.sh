#!/bin/sh
# Check the public repository without photos, hardware, or model downloads.
set -eu

repo_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo_root"

for file in .gitignore AGENTS.md ATTRIBUTION.md CODE_OF_CONDUCT.md LICENSE README.md \
    docs/progress.md scripts/check.sh scripts/n900-fetch-photo.sh; do
    [ -f "$file" ] || { printf 'Missing required file: %s\n' "$file" >&2; exit 1; }
done

for script in scripts/*.sh; do
    sh -n "$script"
done

git diff --check
git diff --cached --check

tracked_private=$(git ls-files | grep -E '(^|/)private/|\.(jpe?g|png|heic|gif|webp|tiff?)$' || true)
[ -z "$tracked_private" ] || {
    printf 'Private path or photo format is tracked:\n%s\n' "$tracked_private" >&2
    exit 1
}

printf 'Public repository checks passed.\n'
