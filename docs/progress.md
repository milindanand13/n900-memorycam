# Progress log

Only verified results are recorded here. Anything unconfirmed is marked as not yet verified.

## 2026-09-29: N900 connected, photos transferred

- **Hosting change.** The Oracle Cloud account is suspended and unavailable. Processing is planned on the Mac first; Gemma 4 26B is installed via Ollama, but Gemma inference and image analysis have not been verified. Qwen3.5 4B passed a short local text inference test. Replacement cloud hosting remains pending; this does not change the course's earlier cloud-node setup assignment.
- **SSH.** Mac → N900 login as root succeeded over a phone hotspot. The first attempt failed because the phone only offers `ssh-rsa` and `ssh-dss` host keys; adding `-o HostKeyAlgorithms=+ssh-rsa` fixed it. The phone runs BusyBox v1.10.2 on `armv7l`.
- **Existing photo transfer.** One photo was copied and its MD5 matched on both ends.
- **Fresh capture.** A new photo was taken on the N900 and transferred: 2576×1936 JPEG, MD5 matched.
- **Phone clock.** The N900 reported January 2009, so the first fresh photo's filename and EXIF date are wrong. The clock appears corrected after a later capture was named `20260929_001.jpg`. The evidence is that later filename; a new direct clock check remains pending. Earlier photo metadata remains unreliable.
- **Debugging with AI.** The first fresh-transfer attempt failed because a path with spaces broke SSH's `ControlPath` option. Codex switched to `ssh -S`, which fixed it.
- **Test archive.** 29 older N900 photos were copied into a private archive; every file's MD5 matched the phone's. They stay out of this repository.
- **Fetch script on the real phone.** The earlier version of `scripts/n900-fetch-photo.sh` connected to the N900 and transferred a photo with a matching checksum, but picked a 2012 photo as "newest" instead of the fresh one because the phone clock was wrong at that capture. The script now fetches the photo that isn't in the local inbox/archive, which was tested against a simulated phone and then verified on the real N900: it found the one new photo (`20260929_001.jpg`), transferred it and the checksums matched.

## 2026-09-29: repository review and documentation corrections

- Shell syntax and Git whitespace checks passed. Ten simulated transfer cases passed: one unknown photo, archive exclusion, paths with spaces, zero or multiple candidates, an explicit filename, checksum mismatch, an existing destination, a missing named photo, an unsafe filename, and an uppercase `.JPG` suffix. Failed transfers preserved existing files and removed temporary files. The simulation used the Mac's `/bin/sh`; this review did not reconnect to the N900.
- Setup now explains the first named transfer and the existing inbox/archive required for automatic selection. Clock and model status distinguish the recorded evidence from pending verification.

At this September 29 stage, Gemma inference, image analysis, matching, photo-pair layout, printing, and automatic upload were not yet verified. The dated entries below record later progress.

## 2026-10-20: visual-matching prototype accepted

- A local CLIP ViT-B/32 experiment ranked 603 unique archive images for each of five preselected N900 query photos. Matching used image features rather than captions, dates, filenames, or folders.
- Offline checks covered score ordering and normalization, invalid features, duplicate/query-copy exclusion, candidate coverage, finite scores, and unchanged source hashes. The photographs, model cache, and detailed comparison evidence remain private and are not part of this repository.
- Milind reviewed the five-query comparison and accepted the pairings as working for this prototype stage. This is qualitative acceptance of that sample, not a general benchmark, proof that CLIP beats a baseline, or a guarantee of a meaningful memory.
- Matching refinements are deferred. The next hardware milestone is two separate physical photo prints after a printer is available.

Still unverified: daily query selection, unattended transfer, a general matching benchmark, printable layout, physical printing, scheduling, and separate detection that Milind and the N900 are home.

## 2026-10-20: repository bootstrap and harness

- Public AI instructions now state the project, verified state, privacy constraints, next milestone, working loop, and limits without depending on files outside this repository.
- `scripts/check.sh` passed in the working repository and in a separate repository-only checkout. It checks required files, shell syntax, whitespace, and the public/private file boundary without photographs.
- An independent fresh AI session read only the public repository, ran the check, and accurately restated the project, completed work, constraints, next milestone, and verification limits after wording corrections.
- This repository check does not reconnect to the N900, rerun private CLIP inference, judge a pairing, or test a printer.

## 2026-10-21: transfer and matching code moved into this repository

- The batch transfer script and the CLIP matching script were developed outside this repository during October. Both now live here as `scripts/transfer_photos.py` and `scripts/match_archive.py`, with their core logic unchanged (two checks were split into small functions so they can be tested). Paths now point at this repository's ignored `private/` folder, the matching script needs `--query` and `--archive` instead of personal default paths, and the CLIP download is a one-time `--download-model` step.
- Added 13 offline tests in `tests/`, run by `scripts/check.sh`. They cover strict parsing of the phone's file list, never overwriting a photo with a reused name, skipping identical content, image-header checks, ranking order and normalisation, query-copy exclusion, repeatable tie order, rejection of broken features, duplicate counting, and refusing output outside `private/`. Two deliberately broken versions of the code (query copies not excluded; overwriting allowed) made the tests fail, so the tests do detect those faults.
- `scripts/check.sh` passed with all 13 tests. Argument checks were run by hand: a missing archive, output outside `private/`, an invalid host and an inbox outside `private/` are all refused before any work starts.
- Not verified since the move: a real transfer from the N900 and a full CLIP run on real photos with these repository versions. The October 9 transfer and October 20 matching results came from the earlier copies.

## 2026-10-21: repository matcher review-page fix

- Independent verification found that CLIP inference and ranking completed, but review-page generation failed because Python string formatting interpreted the CSS braces as replacement fields. The renderer now keeps the CSS literal, and a focused offline regression test covers the page content.
- `scripts/check.sh` passes with all 14 tests. A repository-version CLIP run against the 29-photo private archive completed with 29 eligible candidates, unchanged source/query hashes, a complete result file, eight preview images and a parsed `review.html` whose image references all resolve.
- This verifies the repository matcher on that private archive. It does not establish a general matching benchmark or new qualitative acceptance. A live N900 transfer with the repository copy and physical printing remain unverified.
