# n900-memorycam

A Nokia N900 becomes a daily camera for a reflective journal. Each new photo is used to search my personal photo archive for an older image connected to it by look, meaning, time, season or place. Later that evening, a thermal printer prints the old photo next to the new one. The AI chooses which past moment to bring back; I decide what the connection means.

Built for *Small Linux Devices, Large Language Models* (Parsons, Fall 2026).

> Photo of the device: coming once the printed pair exists.

## Status

| Part | State |
|---|---|
| N900 → Mac over SSH | ✅ Working over a phone hotspot |
| Fresh photo transfer with checksum check | ✅ Working (`scripts/n900-fetch-photo.sh`) |
| Test archive (29 older N900 photos, kept private) | ✅ Imported and checksum-verified |
| Local model (Gemma 4 26B via Ollama on the Mac) | ✅ Installed |
| Photo matching | ⏳ Next |
| Printable photo pair | ⏳ Not started |
| Thermal printing | ⏳ Not started |
| Automatic upload and evening print queue | ⏳ Not started |

See [docs/progress.md](docs/progress.md) for the verified log.

## How it works (planned)

```
N900 camera ──SSH──▶ Mac: match against archive ──▶ photo pair layout ──▶ thermal printer (evening)
                          (image embeddings + Gemma 4)
```

The N900 is the camera and client. With 256 MB of RAM it cannot run the model, so matching runs on the Mac. Moving the model to a self-hosted cloud node is planned for later in the course.

## Setup

You need a Mac, a Nokia N900 with a root shell and OpenSSH installed, and both on the same network.

1. On the N900, install **OpenSSH client and server** from the Application Manager and set a root password. If the catalogue is missing, add `http://maemo.viniciuspaes.com/extras/` (distribution `fremantle`, components `free non-free`).
2. Find the phone's IP address and test the connection. The N900's old SSH server needs one legacy option:
   ```bash
   ssh -o HostKeyAlgorithms=+ssh-rsa root@<phone-ip>
   ```
3. Take a photo on the N900, then copy it to the Mac:
   ```bash
   N900_HOST=<phone-ip> scripts/n900-fetch-photo.sh
   ```
   It fetches the one photo on the phone that isn't already on the Mac and saves it in `private/inbox/`, which git ignores. Set `MEMORYCAM_ARCHIVE` to a folder of photos you've already imported so those are skipped too. Pass a filename to fetch a specific photo.

## Known behaviour

- The N900's clock is set to 2009, so photo filenames, EXIF dates and file times are wrong: a new photo can look older than a 2012 one. The fetch script therefore picks the photo that isn't on the Mac yet instead of the newest one.
- Modern macOS SSH refuses the N900's host key without `HostKeyAlgorithms=+ssh-rsa`.
- Paths containing spaces broke SSH's `ControlPath` option during development; the script avoids connection sharing for this reason.
- `scripts/n900-fetch-photo.sh` uses macOS's `md5` command, so it runs on macOS only.

## Privacy

Personal photos never go in this repository. They stay in `private/`, which is ignored by git. Examples in the docs use non-personal images.

## AI co-authorship

This project is co-authored with AI models, as the course requires. See [ATTRIBUTION.md](ATTRIBUTION.md).

- **GPT-6.1 Sol** (via OpenAI Codex): N900 SSH setup, transfer scripts and debugging
- **Claude Opus 5.5** (via Claude Code): repository setup, documentation and planning
- **Gemma 4 26B** (local, via Ollama): image analysis at run time (planned)

## License

[MIT](LICENSE). I chose it because this is a learning project: anyone should be able to reuse the N900 scripts, and the course's own materials use MIT too.
