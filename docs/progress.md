# Progress log

Only verified results are recorded here. Anything unconfirmed is marked as not yet verified.

## 2026-09-29: N900 connected, photos transferred

- **Hosting change.** The Oracle Cloud node was suspended by Oracle and cannot be restored. The model now runs locally on the Mac (Gemma 4 26B via Ollama). A cloud node is deferred to the course's self-hosted AI week.
- **SSH.** Mac → N900 login as root succeeded over a phone hotspot. The first attempt failed because the phone only offers `ssh-rsa` and `ssh-dss` host keys; adding `-o HostKeyAlgorithms=+ssh-rsa` fixed it. The phone runs BusyBox v1.10.2 on `armv7l`.
- **Existing photo transfer.** One photo was copied and its MD5 matched on both ends.
- **Fresh capture.** A new photo was taken on the N900 and transferred: 2576×1936 JPEG, MD5 matched.
- **Wrong phone clock.** The N900 reports January 2009, so the fresh photo's filename and EXIF date are wrong. The clock has not been changed yet.
- **Debugging with AI.** The first fresh-transfer attempt failed because a path with spaces broke SSH's `ControlPath` option. Codex switched to `ssh -S`, which fixed it.
- **Test archive.** 29 older N900 photos were copied into a private archive; every file's MD5 matched the phone's. They stay out of this repository.

Not yet verified: image analysis, matching, photo-pair layout, printing, automatic upload.
