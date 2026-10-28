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

## 2026-10-22: passwordless pull when the phone is home

- Added `scripts/auto_pull.py` and a `--key` option on `scripts/transfer_photos.py`. The pull checks that the phone answers on SSH, logs `phone not home` and exits 0 if it does not, otherwise runs the existing checked copy with a dedicated passwordless key. A lock stops overlapping runs.
- Six new offline tests (not home, home, failed transfer, refused arguments or crash, active lock, reachability check); `scripts/check.sh` passes with 20 tests. Disabling the not-home check made a test fail.
- Checked on the real phone over home Wi-Fi with no password and no open connection: the run found 73 images, 73 already present, 0 copied, exit 0; an unreachable host logged `phone not home`, exit 0; a single photo fetched with the key matched the local copy's MD5. The same day a password-session run of `transfer_photos.py` copied 17 new photos with matching checksums.
- Not verified at this point: a scheduled run, a key-only run that copies new photos, behaviour if the phone's address changes, presence of Milind, and the nightly time. The follow-up below covers the scheduler.
- Follow-up, same day: a job started by macOS launchd ran the pull end to end with the key ("transfer ok"), but its first run logged "phone not home" although the phone was reachable seconds later, probably a phone in Wi-Fi power saving missing the first try. The home check now tries three times, ten seconds apart (one new test).
- A nightly launchd job with two retries is now installed on the author's Mac. Two manual launchd runs were observed; the first real overnight run, the Mac waking for it, and the phone staying on Wi-Fi overnight are NOT CHECKED.

## 2026-10-25: arrival-polling upgrade prepared

- Read the installed launchd job and private logs. An Oct 22 manually triggered launchd run copied five new photos with verified checksums. The Oct 23 unattended overnight run completed with 78 images already present and zero new copies. Later overnight attempts logged the phone unavailable. The job is still installed with only three nightly slots.
- Added `scripts/install_autopull.py` to extend that existing job with a 120-second interval and a login check, retaining its connection settings and nightly slots. It wraps each run in macOS `caffeinate -i` to prevent idle sleep during the check/transfer. Private previews and previous configurations stay outside Git.
- Offline checks cover configuration preservation, repeat installation, refusing the wrong job/too-frequent checks, not interrupting active transfers, restoring the original job after a load failure, and leaving the loaded schedule untouched on a write refusal. The full repository check passes with 26 tests.
- Activation was attempted but the session could not write to the user's LaunchAgents folder (`Operation not permitted`). The installed nightly configuration was left unchanged. The upgrade is prepared, NOT ACTIVE. Run the installer in the user's Terminal to activate it.
- The phone hostname did not resolve during this session. No live transfer, reconnect-arrival test, new unattended photo copy, changed-address test, person-presence detection or printing was verified. The unrelated local matcher edit was preserved. No commit or push.

## 2026-10-25: external photo-library migration prepared

- A subsequent readback confirms the two-minute launchd job is installed and loaded. A new transfer receipt records 98 phone images, 20 newly copied; all 98 saved files were independently rechecked against its checksums and sizes. Whether this particular run followed a deliberate Wi-Fi reconnect was not observed.
- At the author's request, added an external Pictures library organized by ISO week then camera-filename date, with an explicit unverified-date folder for the phone's bad clock. `organize_photos.py` copies and SHA-256-verifies every source before replacing old photo paths with compatibility links, and switches future batch/automatic transfers only after migration. It preserves non-photo files, prevents overwrites, uses the automatic-pull lock, and is safe to rerun.
- The real local inventory contains 132 distinct Nokia photos across the project's camera inbox/archive and an existing Pictures folder: 68 with usable recorded dates, 64 with unreliable dates. Migration was attempted but Pictures writes were denied. No original was moved or replaced and the external-library configuration is not active. A private migration plan was saved; run the organizer in the user's Terminal to finish.
- `scripts/check.sh` passes with 35 tests, including copy-corruption rejection, date/week boundaries, folder-escape refusal, collisions, migration locking, source-path preservation and an end-to-end synthetic transfer that skips migrated content and does not duplicate files on repeat runs. The scheduled job's actual access to Pictures and real external transfer remain unverified. No commit or push; the existing unrelated matcher edit was preserved.

## 2026-10-25: Pictures migration completed

- The author ran the organizer successfully. Independently checked all 132 external originals against their SHA-256 values and sizes, and all 132 compatibility links against their intended destinations. 68 photos use week/date folders and 64 retain unverified dates in their own folder. The external-library setting is active.
- A subsequent automatic job completed with all 98 phone photos already present in the external library and no duplicate downloads. The installed job remains on a 120-second interval with exit code 0. Actual copying of a new photo into Pictures by the scheduled job and a deliberate reconnect test remain unobserved. No code change or new test run was needed for this read-only verification.


## 2026-10-28: automatic import and archive comparison status

- A genuinely new phone photograph was automatically copied into the configured Pictures library on October 27. Its receipt checksum and size were independently checked; later scheduled receipts found it already present. No manual trigger was used for that verification. This establishes automatic import, not controlled reconnect behaviour or exact arrival latency; the Mac must be awake.
- A 905-image personal pilot used twelve supplied queries and the existing local CLIP model. Milind qualitatively accepted the reviewed pairings. Separately, six choices on an earlier local A/B sheet preferred CLIP over random. Those are distinct evidence and do not establish a Google Photos A/B rate or general benchmark.
- A first larger sample prompted an archive-direction correction: everyday photographs should recall past places, activities and people with visible context. A manually curated 165-image pool was expanded by forty eligible images to 205. Two images were excluded before ranking; originals were preserved. Same twelve queries/model; all twelve leading matches stayed unchanged. Old scores reproduced within 1e-7 and integrity checks passed. This does not demonstrate improved leading retrieval. New curated pairings remain unreviewed; no identities or emotional value inferred.
- Daily selection remains unimplemented, and the matcher requires a supplied photo. Printer not ordered as last reported; physical printing, the nightly ritual and separate person-presence checks remain unverified. Next archive step is human review. This update changes local documentation only; no new inference, download, implementation, commit or push. Private images, pairings and source records remain outside the public repository.

## 2026-10-28: audit fixes to the transfer

- Audit found two ways the two-minute check could fail or waste effort. (1) One phone file with an unusual name made the whole run fail; such files are now skipped and reported. (2) Each check made the phone checksum every photo and the Mac rehash the whole library; both sides now remember checksums (name, size and date on the phone; size and modified time on the Mac), and a check with nothing new writes no receipt.
- Added tests for the skip, the remembered checksums, the fallback to the old full checksum when the phone's listing is not understood, and a corrupted download leaving no photo. `scripts/check.sh` passes with 44 tests.
- NOT verified on the real phone: the phone was unreachable. The first live run rebuilds the phone cache with one full checksum pass; check `private/auto-pull.log` and the next receipt.
