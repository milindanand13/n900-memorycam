# Direct print from the N900 (option B)

One tap on the phone prints its newest photo on the Volcora V-WLPR5. The Mac is not involved.

- `print_latest.py`: Python 2.5 + PIL 1.1.6 (both already on the phone). Picks the newest `*.jpg` in `/home/user/MyDocs/DCIM` by filename, applies the same settings as `Claude/print_slip.py` (576 dots, gamma 0.8, contrast 1.2, sharpen 50, Floyd-Steinberg, density 8, raw partial cut), and sends raw ESC/POS to port 9100. It waits for the previous job to finish before starting, and ignores a second tap while one is printing.
- `memorycam-print.desktop`: launcher "Print photo" (newest photo).
- `print_pick.py` + `memorycam-pick.desktop`: launcher "Print photo (choose)". Shows a thumbnail grid of the camera folder (newest first, fills in over about 20 s), tap a photo, confirm Yes, it prints.
- `check_bytes.py`: Mac-side check that decodes a job's bytes back to a PNG and compares with the Mac printer's output.

## Install (on the phone, one time)
```sh
scp print_latest.py print_pick.py root@PHONE:/home/user/memorycam/      # make the folder first: ssh root@PHONE mkdir -p /home/user/memorycam
scp memorycam-print.desktop memorycam-pick.desktop root@PHONE:/usr/share/applications/hildon/
```
Then the "Print photo" and "Print photo (choose)" icons appear in the phone's application menu (it can be dragged to the desktop).

## If the printer's address changes
Nothing to edit. The script tries the last address that worked, and if that does not answer it searches the phone's own Wi-Fi network for a device listening on port 9100 (a few seconds; a hotspot has only 14 addresses). The address found is remembered in `/home/user/.memorycam-printer-ip`. `print_latest.py --find` prints it without printing. If two devices listen on 9100 the lowest address wins. If nothing is found the phone shows "printer not found". The printer itself must have joined the same Wi-Fi as the phone (one-time setup per network).

## Moving the printer to another Wi-Fi (for example the iPhone hotspot)
The printer remembers only one network. Joining a new one makes it forget the old one (for example the home network).
1. Turn the printer on. On the Mac, Wi-Fi menu: join "WIFI Printer" (password in the owner's private notes). The Mac loses internet while on it.
2. In a browser open `http://10.10.100.254` (login in the same private notes). Click "STA Setting".
3. SSID: the network name, exactly (for an iPhone hotspot, the phone's name exactly, including any curly ’ apostrophe; paste it rather than type it. If the printer will not join, rename the phone in Settings > General > About > Name to one without an apostrophe, then use that). Password: type it yourself. DHCP: Enable. Click Save (and Restart if the page offers it).
4. Mac Wi-Fi back to the same network. Wait about a minute, then on the phone run `python /home/user/memorycam/print_latest.py --find`; it prints the printer's address.
- Switch back to home: same steps, your home network name (2.4 GHz) and its password.
- Easier way that worked on Nov 4 (no network switching): iPhone Settings > Personal Hotspot > Maximize Compatibility ON (the printer only does 2.4 GHz; the hotspot is 5 GHz without it). Then in the PrinterConfigure app pick device "ZYBT001", type the Wi-Fi name on the iPhone keyboard and the password, and wait for the green tick. It joined the hotspot as 172.20.10.8. The first try that night, with Maximize Compatibility off, said "Device not responding" and left the printer on no network, with its own "WIFI Printer" network gone.
- To go back to the home network: same app, the home Wi-Fi name with its exact capitals (names are case-sensitive; on Nov 5 it was saved in lowercase and never joined despite a green tick). Check with the self-test slip (power on holding FEED, let go after the beep): STA SSID must match the network name exactly.

## Differences from the Mac version
- No `UnsharpMask` and a buggy `ImageEnhance.Contrast` in PIL 1.1.6: both are done by hand (same maths). The JPEG is decoded at reduced size to fit the phone's RAM, so the slip is a little softer.
- The phone's own Wi-Fi must be on the same network as the printer.

## Verified (Nov 4, 2026)
- Auto-find: on the iPhone hotspot (172.20.10.x) the phone found a stand-in listener on port 9100 in about 3 s and reported "not found" when none existed. Real printer on the hotspot (Nov 4, night): `--find` printed `172.20.10.8`, but the first try said `None`, because the phone's first connection to the printer took longer than the 1 s the search waits. Fixed later that night: the search now waits 3 s per address and found the printer on the first try (3.5 s).
- Hotspot printing (Nov 4, night): the job is now sent in 2 KB pieces with up to 60 s per piece and is never resent (one 20 s `sendall` had timed out mid-image and the printer printed the rest as garbage text). After the fix, one launcher print sent without error in 19 s, but the photo came out in 2 to 3 bursts with 3 to 4 lines across it. The printer answers pings in about 1 s on the hotspot, so data arrives slower than it prints. On the home network the same job prints clean. Not solved yet.
- Picking the right printer (Nov 4, night): if `/home/user/.memorycam-printer-mac` on the phone holds the printer's Wi-Fi hardware (MAC) address, the script only accepts an address whose hardware address matches (cached, default and searched addresses alike), so another device on port 9100 cannot win. Without that file, or with no match, the lowest address answering on 9100 wins as before. Tested on the hotspot: right match, wrong-address fallback, and a stale cached address (recovered in about 7 s). Not yet tested on the home network next to the other network printer.
- Phone has Python 2.5.4 and PIL 1.1.6. Dry run of the script on the phone (about 4 s, no network): the bytes decode to a 576 x 766 image, the same size and orientation as the Mac version, average tone within about 1 of 255, same look by eye (about 13% of dots differ, which is dither noise).
- Milind confirmed a real slip printed from the launcher, and that the thumbnail picker works (Nov 4). Whether the Mac was fully off was not checked.
- No AI picks the photo here: "Print photo" prints the newest filename.
