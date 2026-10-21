# n900-memorycam

A Nokia N900 becomes a deliberate daily camera for a reflective journal. At a set time each night, when I am home and the N900 is home, the system picks one photo from my day and searches my personal photo archive for an older image connected to it. A thermal printer then prints the new photo and the old one as two separate slips. There is no generated caption or journal question: the two images are the prompt. The AI chooses which past moment to bring back; I decide what the connection means.

Built for *Small Linux Devices, Large Language Models* (Parsons, Fall 2026).

> Photo of the device: coming once the printed pair exists.

## Status

| Part | State |
|---|---|
| N900 → Mac over SSH | ✅ Working over a phone hotspot |
| Single photo transfer with checksum check | ✅ Working (`scripts/n900-fetch-photo.sh`) |
| Copy all new photos with checksum checks | ✅ Working when started by hand (`scripts/transfer_photos.py`): 131/131 files verified on the real phone on Oct 9, before the script moved into this repository; not rerun on the phone since the move |
| Test archive (29 older N900 photos, kept private) | ✅ Imported and checksum-verified |
| Local visual matching | ✅ Prototype (`scripts/match_archive.py`): five hand-picked N900 photos matched against 603 of my portfolio photos; I accepted those pairs. Not yet tested on my full personal archive |
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

The N900 is the camera and SSH server; the Mac pulls photos from it and runs matching. With 256 MB of RAM, the N900 cannot run the selected model. Matching uses CLIP image features only, so captions, filenames and dates do not affect which photo comes back. A private five-query experiment ranked 603 unique photos (my portfolio photos, standing in for the full archive) per query; I accepted those sample pairings as good enough for this prototype stage. This was a qualitative review, not a general benchmark or a claim that every result will be meaningful.

The next hardware milestone is two separate physical photo prints after a printer is available. Daily selection, unattended transfer, scheduling, and separate checks that Milind and the N900 are home remain unfinished.

## Checks

From a fresh checkout, run:

```bash
scripts/check.sh
```

This public check needs only Python 3 and NumPy (`python3 -m pip install numpy`): no photographs, phone, model, or printer. It validates the repository structure, shell and Python syntax, whitespace, and the public/private file boundary, and runs the offline tests in `tests/`:

- **Transfer:** the phone's file list is parsed strictly (unsafe paths, non-photos and repeats are refused), a reused filename never overwrites an existing photo, identical content is not saved twice, image headers must match the file type, and photos can only be saved under `private/`.
- **Matching:** the closest image ranks first, copies of the query photo are left out, ties come out in the same order every run, broken image features are refused, exact duplicates in the archive count once, and results can only be saved under `private/`.

It does not connect to the N900, run CLIP on real photos, judge whether a pair is meaningful, or test a printer.

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

### Copy all new photos

`scripts/transfer_photos.py` copies every photo on the phone that is not already in `private/inbox/` or `private/archive/`, compared by content rather than filename. You open the SSH connection yourself so the password is typed only in your terminal:

```bash
mkdir -p private/ssh-session && chmod 700 private/ssh-session
ssh -M -S private/ssh-session/control -fN -o HostKeyAlgorithms=+ssh-rsa root@PHONE_IP
python3 scripts/transfer_photos.py --host PHONE_IP
ssh -S private/ssh-session/control -O exit root@PHONE_IP
```

Each photo is checked against the phone's MD5 and its JPEG/PNG header before it gets its final name. If a filename is already taken by a different photo, the new one is saved with its checksum added to the name; nothing is overwritten and nothing is deleted from the phone. Every run writes a receipt to `private/transfers/`. Use `--source-root` for another photo folder on the phone (for example `/home/user/MyDocs/.images`).

### Find matches in your archive

Install the matching dependencies once with `python3 -m pip install -r requirements.txt`. The first run needs `--download-model` to save CLIP (about 600 MB) into `private/models/`; later runs work offline:

```bash
python3 scripts/match_archive.py --download-model \
  --query private/inbox/20261009_017.jpg --archive /path/to/older/photos
```

The archive folder is searched recursively and read in place; photos are never moved, changed or uploaded. Results go to a new folder under `private/matches/`: `result.json` holds the full ranking, and `review.html` shows the query, the six closest matches and one random pick for comparison. Image features are cached in `private/features/`, so later runs against the same archive only process new photos. If your photos already live outside the repository, you can make `private` a symlink to that folder.

## Known behaviour

- The N900's clock was set to 2009 during the first fresh capture. It appears corrected after a later capture produced `20260929_001.jpg`, but earlier filenames, EXIF dates and file times remain unreliable. The fetch script selects a photo absent from the local inbox/archive instead of relying on dates.
- Modern macOS SSH refuses the N900's host key without `HostKeyAlgorithms=+ssh-rsa`.
- Paths containing spaces broke SSH's `ControlPath` option during development; the script avoids connection sharing for this reason.
- `scripts/n900-fetch-photo.sh` uses macOS's `md5` command, so live transfer runs on macOS only. `scripts/transfer_photos.py` computes checksums in Python instead.
- Matching only removes exact byte-for-byte duplicates. Near-identical frames (two shots of the same scene) can both rank near the top, and different queries can return the same archive photo.
- A high match score means the images look alike to CLIP. It is not a probability, and it says nothing about whether the pair means anything to me.
- Choosing the day's photo is still done by hand.

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
