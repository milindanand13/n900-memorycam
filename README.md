# n900-memorycam

A Nokia N900 becomes a daily camera for a reflective journal. Each new photo is used to search my personal photo archive for an older image connected to it by look, meaning, time, season or place. Later that evening, a thermal printer produces the old and new photos as two separate slips. The AI chooses which past moment to bring back; I decide what the connection means.

Built for *Small Linux Devices, Large Language Models* (Parsons, Fall 2026).

> Photo of the device: coming once the printed pair exists.

## Status

| Part | State |
|---|---|
| N900 → Mac over SSH | ✅ Working over a phone hotspot |
| Fresh photo transfer with checksum check | ✅ Working (`scripts/n900-fetch-photo.sh`) |
| Test archive (29 older N900 photos, kept private) | ✅ Imported and checksum-verified |
| Local visual matching | ✅ Five-query CLIP sample accepted for the prototype; not a general benchmark |
| Daily photo selection | ⏳ Not started |
| Printable photo pair | ⏳ Not started |
| Thermal printing | ⏳ Not started |
| Unattended transfer, presence checks and scheduling | ⏳ Not started |

See [docs/progress.md](docs/progress.md) for the verified log.

## How it works (planned)

```
N900 camera ──SSH──▶ Mac: match against archive ──▶ two photo slips ──▶ thermal printer (evening)
                          (local image features)
```

The N900 is the camera and SSH server; the Mac pulls photos from it and runs matching. With 256 MB of RAM, the N900 cannot run the selected model. A private five-query experiment ranked 603 unique archive images per query with CLIP image features; Milind accepted those sample pairings as sufficient for this prototype stage. This was a qualitative review, not a general benchmark or a claim that every result will be meaningful.

The next hardware milestone is two separate physical photo prints after a printer is available. Daily selection, unattended transfer, scheduling, and separate checks that Milind and the N900 are home remain unfinished.

## Checks

From a fresh checkout, run:

```bash
scripts/check.sh
```

This public check needs no photographs, phone, model, or printer. It validates the repository structure, shell syntax, whitespace, and public/private file boundary. It does not reproduce the private visual-matching experiment or establish hardware behavior.

## Setup

You need a Mac, a Nokia N900 with a root shell and OpenSSH installed, and both on the same network. Run these commands from the repository root. Replace `PHONE_IP` with the phone's current IP address and the example photo filename with the one you want to fetch.

1. On the N900, install **OpenSSH client and server** from the Application Manager and set a root password. If the catalogue is missing, add `http://maemo.viniciuspaes.com/extras/` (distribution `fremantle`, components `free non-free`).
2. Find the phone's IP address and test the connection. The N900's old SSH server needs one legacy option:
   ```bash
   ssh -o HostKeyAlgorithms=+ssh-rsa root@PHONE_IP
   ```
3. For the first transfer, choose a filename explicitly. You can list the phone's photo folder with:
   ```bash
   ssh -o HostKeyAlgorithms=+ssh-rsa root@PHONE_IP 'ls /home/user/MyDocs/DCIM'
   ```
   Then fetch the chosen photo:
   ```bash
   N900_HOST="PHONE_IP" scripts/n900-fetch-photo.sh 20260929_001.jpg
   ```
   It saves the photo in `private/inbox/`, which git ignores, and refuses to overwrite an existing file.
4. To identify the sole unimported phone photo automatically, the inbox and archive must already contain every other photo on the phone. This is a transfer safeguard, not the unfinished daily photo-selection rule. If those imports live elsewhere, point the script at their existing folders:
   ```bash
   N900_HOST="PHONE_IP" \
     MEMORYCAM_INBOX="/absolute/path/to/inbox" \
     MEMORYCAM_ARCHIVE="/absolute/path/to/archive" \
     scripts/n900-fetch-photo.sh
   ```
   With no filename, the script transfers only when exactly one phone photo is absent from those folders. It stops without saving if there are zero or multiple candidates. A fresh checkout with an empty inbox will therefore need a named transfer or an existing imported archive; fetching one named photo does not mark the others as imported.

## Known behaviour

- The N900's clock was set to 2009 during the first fresh capture. It appears corrected after a later capture produced `20260929_001.jpg`, but earlier filenames, EXIF dates and file times remain unreliable. The fetch script selects a photo absent from the local inbox/archive instead of relying on dates.
- Modern macOS SSH refuses the N900's host key without `HostKeyAlgorithms=+ssh-rsa`.
- Paths containing spaces broke SSH's `ControlPath` option during development; the script avoids connection sharing for this reason.
- `scripts/n900-fetch-photo.sh` uses macOS's `md5` command, so live transfer runs on macOS only.

## Privacy

Personal photos never go in this repository. They stay in `private/`, which is ignored by git. Examples in the docs use non-personal images.

## AI co-authorship

This project is co-authored with AI models, as the course requires. See [ATTRIBUTION.md](ATTRIBUTION.md).

- **GPT-6.1 Sol** (via OpenAI Codex): N900 SSH setup, transfer scripts and debugging
- **GPT-6** (via OpenAI Codex): repository review and documentation corrections
- **Claude Opus 5.5** (via Claude Code): repository setup, documentation and planning
- **CLIP ViT-B/32** (local): direct image-feature matching in the accepted five-query prototype sample
- **Gemma 4 26B** (local, via Ollama): earlier planned image analysis; not used in the accepted CLIP sample

## License

[MIT](LICENSE). I chose it because this is a learning project: anyone should be able to reuse the N900 scripts, and the course's own materials use MIT too.
