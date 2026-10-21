#!/bin/sh
# Check the public repository without photos, hardware, or model downloads.
set -eu

repo_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo_root"

for file in .gitignore AGENTS.md ATTRIBUTION.md CODE_OF_CONDUCT.md LICENSE README.md \
    requirements.txt docs/progress.md scripts/check.sh scripts/n900-fetch-photo.sh \
    scripts/transfer_photos.py scripts/match_archive.py \
    tests/test_transfer_photos.py tests/test_match_archive.py; do
    [ -f "$file" ] || { printf 'Missing required file: %s\n' "$file" >&2; exit 1; }
done

for script in scripts/*.sh; do
    sh -n "$script"
done

python3 -c 'import numpy' 2>/dev/null || {
    printf 'NumPy is missing. Install it with: python3 -m pip install numpy\n' >&2
    exit 1
}
python3 - <<'EOF'
import ast, pathlib
for path in sorted(pathlib.Path('scripts').glob('*.py')) + sorted(pathlib.Path('tests').glob('*.py')):
    ast.parse(path.read_text(), filename=str(path))
EOF
python3 -m unittest discover -s tests

git diff --check
git diff --cached --check

tracked_private=$(git ls-files | grep -E '(^|/)private/|\.(jpe?g|png|heic|gif|webp|tiff?|npy)$' || true)
[ -z "$tracked_private" ] || {
    printf 'Private path or photo format is tracked:\n%s\n' "$tracked_private" >&2
    exit 1
}

printf 'Public repository checks passed.\n'
