# Guidance for AI coding agents

This repository is the public, self-contained source of truth for the Memorycam prototype. Read this file, `README.md`, and `docs/progress.md` before changing anything. Do not rely on files outside a fresh checkout.

## Project and current state

Memorycam uses a Nokia N900 as a deliberate daily camera. A Mac will select one new photo, find a visually related older photo, and eventually print the two images on separate thermal slips. The images are the output; do not generate journal prompts, captions, or explanations of their meaning.

Verified so far:

- capture on the N900 and manual SSH transfer to a Mac;
- checksum-verified transfer with `scripts/n900-fetch-photo.sh` (one photo) and `scripts/transfer_photos.py` (every new photo; 131/131 verified on the phone on Oct 9 before it moved into this repository);
- a private archive imported and checksum-verified;
- a local CLIP visual-matching prototype, `scripts/match_archive.py`, that ranked 603 unique portfolio photos for each of five hand-picked queries; Milind accepted those five sample pairings as sufficient for this prototype stage.

The five-query result is a qualitative sample, not a general benchmark or a guarantee of a meaningful memory. The candidates were portfolio photos standing in for the full personal archive. Photographs, model weights and results stay in `private/` and are not required to check this repository.

Not yet verified: daily photo selection, unattended transfer, a general matching benchmark, printable layout, physical printing, scheduling, and separate detection that Milind and the N900 are both home. The next hardware milestone is two separate physical photo prints, after a printer is available. Do not implement printing or home automation unless explicitly asked.

## Working rules

- Make the smallest requested change and preserve existing work.
- Never commit photos, screenshots containing them, passwords, credentials, network addresses, model caches, chat archives, or private notes. Photos belong under `private/`, which Git ignores.
- Keep verified results and proposals separate. A passing offline check does not prove phone connectivity, matching quality, or physical printing.
- The N900 runs BusyBox `ash`; phone-side commands must be POSIX `sh`.
- Apply `HostKeyAlgorithms=+ssh-rsa` only when connecting to the legacy N900 SSH server.
- N900 photo dates were unreliable during early captures. Do not rewrite original metadata or treat it as verified chronology.
- Preserve source photos and refuse overwrites. Record failures instead of weakening a check.
- End AI-assisted commits with the model's `Co-Authored-By:` trailer described in `ATTRIBUTION.md`.

## Change and check loop

1. State the requested behavior and the evidence that will count as success.
2. Inspect callers and existing checks before editing.
3. Make the smallest complete change.
4. Run `scripts/check.sh`. Add a focused test if new non-trivial logic is introduced.
5. For hardware or model work, also observe the behavior in that environment. Mark unavailable physical checks as unverified.
6. Update `docs/progress.md` with short, truthful results and remaining limits.
7. Before committing, inspect the full staged diff and tracked-file list for private data.

`scripts/check.sh` is repository-only and needs Python 3 with NumPy: it checks required public files, shell and Python syntax, runs the offline tests in `tests/`, checks whitespace, and confirms no private folder, photo or feature file is tracked. It does not connect to the N900, run CLIP, inspect private photographs, or test a printer. When you change transfer or matching logic, add or update a test in `tests/` that fails without your change.
