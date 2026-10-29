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
| Local visual matching | ✅ Prototype (`scripts/match_archive.py`): five initial queries against 603 portfolio photos, then twelve supplied queries against a 905-image personal sample. I accepted the reviewed samples; later curated comparisons await review. Full library not indexed |
| Daily photo selection | 🟡 Written and tested offline (`scripts/daily_choice.py`), dry-run on real photos; not yet run unattended or with a printer. The rule is untuned and untested for quality |
| Printable photo pair | ⏳ Not started |
| Thermal printing | ⏳ Not started |
| Passwordless pull when the phone is on the same Wi-Fi | ✅ New photos copied through launchd on Oct 22; unattended overnight run on Oct 23 completed with no new photos |
| Arrival checks every two minutes | ✅ 120-second launchd job installed; a new receipt on Oct 25 records 20 newly copied photos. A deliberate Wi-Fi reconnect test remains pending |
| Photos stored in Pictures by week/date | ✅ 132 originals migrated and independently verified; subsequent scheduled lookup found all 98 phone photos there without duplicates. A genuinely new photo copied automatically into Pictures on Oct 27; later checks found it already present |
| Separate person-presence check and print schedule | ⏳ Not started |

See [docs/progress.md](docs/progress.md) for the verified log.

## How it works (planned)

```
N900 camera ──SSH──▶ Mac: match against archive ──▶ two photo slips ──▶ thermal printer (evening)
                          (local image features)
```

The N900 is the camera and SSH server; the Mac pulls photos from it and runs matching. With 256 MB of RAM, the N900 cannot run the selected model. Matching uses CLIP image features only, so captions, filenames and dates do not affect which photo comes back. The initial five-query experiment used 603 portfolio photos. A later twelve-query comparison used 905 personal stills; I accepted the reviewed sample pairings. Six separate local A/B preferences favoured CLIP over random, but do not establish a Google Photos preference rate. The latest manually curated archive has 205 images; adding 40 eligible images left all twelve leading results unchanged. New pairings await my review. None of these convenience samples establishes full-library reliability or memory value. Matching still requires an explicitly supplied query.

The next hardware milestone is two separate physical photo prints after a printer is available. A two-minute and nightly transfer job is installed. A new scheduled photo import into Pictures was verified October 27; exact arrival latency remains untested. Daily selection, print scheduling, and separate checks that Milind and the N900 are home remain unfinished.

## Checks

From a fresh checkout, run:

```bash
scripts/check.sh
```

This public check needs only Python 3 and NumPy (`python3 -m pip install numpy`): no photographs, phone, model, or printer. It validates the repository structure, shell and Python syntax, whitespace, and the public/private file boundary, and runs the offline tests in `tests/`:

- **Transfer:** the phone's file list is parsed strictly (unsafe paths, non-photos and repeats are refused), a reused filename never overwrites an existing photo, identical content is not saved twice, image headers must match the file type, and destinations are restricted to `private/` or the explicitly configured external library. Organization checks cover calendar week boundaries, unreliable dates, copy verification, collision preservation, the scheduler lock, old-path compatibility and repeated future transfers.
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

`scripts/transfer_photos.py` copies every photo on the phone that is not already in the configured Pictures library or legacy `private/inbox/` and `private/archive/`, compared by content rather than filename. You open the SSH connection yourself so the password is typed only in your terminal:

```bash
mkdir -p private/ssh-session && chmod 700 private/ssh-session
ssh -M -S private/ssh-session/control -fN -o HostKeyAlgorithms=+ssh-rsa root@PHONE_IP
python3 scripts/transfer_photos.py --host PHONE_IP
ssh -S private/ssh-session/control -O exit root@PHONE_IP
```

Each photo is checked against the phone's MD5 and its JPEG/PNG header before it gets its final name. If a filename is already taken by a different photo, the new one is saved with its checksum added to the name; nothing is overwritten and nothing is deleted from the phone. A run that copies something, or fails, writes a receipt to `private/transfers/`; a check that finds nothing new writes none. A phone file with an unusual name (spaces, odd characters, not a photo) is skipped and listed in the receipt and output, so it cannot block the other photos. To keep the two-minute check light, the phone is asked only for names and sizes, and for checksums of photos it has not seen before; checksums are remembered in ignored `private/md5-cache.json` (delete it to force a full recheck). Use `--source-root` for another photo folder on the phone (for example `/home/user/MyDocs/.images`).

### Keep Nokia photographs in Pictures

Run `python3 scripts/organize_photos.py` once in your Terminal. The default destination is `~/Pictures/Personal/Nokia-N900/`, with ISO Monday-to-Sunday week folders above daily folders, for example `2026-W43/2026-10-22/`. A date comes from the camera filename, rather than the transfer date. Dates before the clock correction on September 29, 2026, invalid dates, future dates and photos without a dated camera filename go under `Date-unverified/`; originals and metadata are not rewritten.

The migration includes existing photos in the project's inbox/archive/nokia-images and the user's `Pictures/Nokia` folder. It verifies SHA-256 before replacing old photo files with links to the organized originals. Non-photo files are preserved; old experiment paths still work. All sources must copy successfully before old paths are switched. It takes the same lock as the automatic pull, so they cannot run simultaneously. A partial migration is safe to retry.

Only after the migration succeeds does it save ignored `private/photo-library.json`. Both manual batch transfers and the existing scheduled pull read this setting every run, deduplicate against the whole library and place new files in the same week/date layout. No scheduler reinstall is necessary. With no configuration, the old destination remains in use. Transfer receipts and code stay in the project. To use a different external folder, pass `--library /absolute/path`; do not put it inside the repository. The real Pictures migration was independently verified October 25, and a scheduled new-photo copy there was verified October 27. A different installation still needs its own live verification.

### Pull automatically when the phone is home

`scripts/auto_pull.py` is for a scheduler to run. It asks whether the phone answers on SSH port 22; if not, it logs `phone not home` and exits quietly. If it does, it runs the same checked copy as above, using a dedicated passwordless key instead of an open connection, and only one run can happen at a time. Set the key up once:

```sh
ssh-keygen -t rsa -b 3072 -N "" -f ~/.ssh/n900_memorycam
ssh -o HostKeyAlgorithms=+ssh-rsa root@PHONE 'mkdir -p /root/.ssh && cat >> /root/.ssh/authorized_keys && chmod 700 /root/.ssh && chmod 600 /root/.ssh/authorized_keys' < ~/.ssh/n900_memorycam.pub
```

Then run `python3 scripts/auto_pull.py --host PHONE --key ~/.ssh/n900_memorycam`. The phone's old SSH server needs an RSA key; the key has no passphrase, so keep it private and on this Mac only. A line per run goes to `private/auto-pull.log`.

#### Upgrade an existing nightly Mac job to arrival checks

The scheduler belongs to macOS (`launchd`), and the transfer code belongs to this repository. ChatGPT, Codex, an internet service, and a language model are not needed to run it.

If `com.milind.memorycam.autopull` is already installed in your user's `Library/LaunchAgents` folder, run this from the repository root, using the Python interpreter specified in that job:

```sh
python3 scripts/install_autopull.py
```

This preserves the existing phone hostname, SSH key, log paths and nightly slots. It adds a check every 120 seconds while the Mac is awake and a check when the job loads at login. `caffeinate -i` prevents idle sleep only while a check/transfer is running. There is no permanent sleep prevention and no change to the phone or its Wi-Fi settings. New photos normally arrive on the next check after the phone becomes reachable; its own Wi-Fi reconnection can add a delay. The existing pinned SSH host key still verifies the device before any transfer.

The installer saves the previous configuration and a preview in ignored `private/autopull-setup/`. `--prepare-only` prepares these without changing the live job. An active transfer is left alone; retry the installer after it finishes. If the new job cannot load, the installer attempts to restore the previous configuration and schedule. A denied file write leaves the installed schedule alone.

The Mac must be powered on, logged in, awake and able to reach the N900. Sleep pauses interval checks; calendar jobs missed during sleep can run on waking. A closed or sleeping laptop is not a reliable immediate receiver. Use a computer that stays on at home if transfer must work while the laptop is away or closed. Reachability does not independently establish that the photographer is home and does not trigger printing.

To verify activation, inspect `launchctl print gui/$(id -u)/com.milind.memorycam.autopull` for the 120-second interval. Then take a new N900 photo, reconnect it to home Wi-Fi, leave the Mac awake, and check `private/auto-pull.log` and the latest receipt in `private/transfers/`. A repeated check should report no new copies. Offline checks do not establish a live arrival transfer.

### Find matches in your archive

Install the matching dependencies once with `python3 -m pip install -r requirements.txt`. The first run needs `--download-model` to save CLIP (about 600 MB) into `private/models/`; later runs work offline:

```bash
python3 scripts/match_archive.py --download-model \
  --query private/inbox/20261009_017.jpg --archive /path/to/older/photos
```

The archive folder is searched recursively and read in place; photos are never moved, changed or uploaded. Results go to a new folder under `private/matches/`: `result.json` holds the full ranking, and `review.html` shows the query, the six closest matches and one random pick for comparison. Image features are cached in `private/features/`, so later runs against the same archive only process new photos. If your photos already live outside the repository, you can make `private` a symlink to that folder.

### Choose the day's photo

```bash
python3 scripts/daily_choice.py --date 2026-10-24
```

A dry run: it prints the chosen photo and every photo it considered, and saves nothing. The rule: take the photos whose camera filename has that date; drop any that are near-black, too blurry or a near copy of a later shot that day; then pick the one CLIP scores as most scene-like (a place, an activity, people in context, not a mirror selfie or object close-up). CLIP sees dark photos lifted to a readable brightness, and a dark photo loses a little score so a lit one wins when the two are close. If every photo fails those checks, the best one is still used. On a day with no photo, the stand-in is the best usable older photo in the library that has never been chosen. Exit status 2 means the library has nothing left. It uses the CLIP model and feature cache from `match_archive.py`, plus the CLIP tokenizer files in `private/models/clip-tokenizer/` (a local copy of the same BPE vocabulary; the model download does not include them). Add `--record` only when the choice is really used: it appends to ignored `private/daily-choice.json`, so the same photo is never chosen twice and a repeated run on the same date returns the same photo. The stand-in pool excludes photos with unverified dates, except filename dates listed in `CLOCK_FIXES` (a few wrong-clock dates from the N900's September clock reset that were checked against other photos).

## Known behaviour

- The N900's clock was set to 2009 during the first fresh capture. It appears corrected after a later capture produced `20260929_001.jpg`, but earlier filenames, EXIF dates and file times remain unreliable. The fetch script selects a photo absent from the local inbox/archive instead of relying on dates.
- Modern macOS SSH refuses the N900's host key without `HostKeyAlgorithms=+ssh-rsa`.
- Paths containing spaces broke SSH's `ControlPath` option during development; the script avoids connection sharing for this reason.
- `scripts/n900-fetch-photo.sh` uses macOS's `md5` command, so live transfer runs on macOS only. `scripts/transfer_photos.py` computes checksums in Python instead.
- Matching only removes exact byte-for-byte duplicates. Near-identical frames (two shots of the same scene) can both rank near the top, and different queries can return the same archive photo.
- A high match score means the images look alike to CLIP. It is not a probability, and it says nothing about whether the pair means anything to me.
- `scripts/daily_choice.py` chooses the day's photo (see below). Its blur, brightness and near-copy limits and its CLIP "scene-like" score are untuned first guesses, and no one has judged whether its picks are good.

## Privacy

Personal photos never go in Git. They live in the configured external Pictures library after migration; earlier imports and compatibility links are under ignored `private/`. Model caches, receipts and private configuration stay under `private/`. Examples in the docs use non-personal images.

## AI co-authorship

This project is co-authored with AI models, as the course requires. See [ATTRIBUTION.md](ATTRIBUTION.md).

- **GPT-6.1 Sol** (via OpenAI Codex): N900 SSH setup, transfer scripts and debugging
- **GPT-6** (via OpenAI Codex): repository review and documentation corrections
- **Claude Opus 5.5** (via Claude Code): repository setup, documentation and planning
- **Claude Sonnet 5.5** (via Claude Code): passwordless pull script, its tests and documentation
- **CLIP ViT-B/32** (local): direct image-feature matching in the accepted five-query prototype sample
- **Gemma 4 26B** (local, via Ollama): earlier planned image analysis; not used in the accepted CLIP sample

## License

[MIT](LICENSE). I chose it because this is a learning project: anyone should be able to reuse the N900 scripts, and the course's own materials use MIT too.
