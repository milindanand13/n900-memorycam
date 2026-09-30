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

Not yet verified: Gemma inference, image analysis, matching, photo-pair layout, printing, automatic upload.
