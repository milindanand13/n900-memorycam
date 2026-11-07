#!/usr/bin/python
# Print the newest N900 photo straight to the Volcora V-WLPR5 (raw ESC/POS, TCP 9100). No Mac needed.
# Python 2.5 + PIL 1.1.6 only (what Maemo ships). Same look as Claude/print_slip.py:
# 576 dots, gamma 0.8, contrast 1.2, sharpen 50, Floyd-Steinberg, density 8, raw partial cut.
# Usage: print_latest.py [photo.jpg] [--dry out.bin] | --find   (--dry writes the bytes to a file, --find only looks for the printer)
import os, re, sys, time, socket, threading
import Image, ImageOps, ImageFilter

PRINTER = (None, 9100)  # no fixed address in the public copy: cached address first, then a search of the phone's network
IPFILE = "/home/user/.memorycam-printer-ip"  # last address that worked
MACFILE = "/home/user/.memorycam-printer-mac"  # printer's Wi-Fi hardware address (kept on the phone, not in the repo)
DCIM = "/home/user/MyDocs/DCIM"
W, GAMMA, CONTRAST, SHARPEN = 576, 0.8, 1.2, 50
STAMP = "/home/user/.memorycam-last-print"  # time the previous job should be finished
RUNNING = "/tmp/memorycam-print.running"    # blocks a double tap
FILT = getattr(Image, "LANCZOS", None) or Image.ANTIALIAS

def say(text):  # Maemo on-screen banner; harmless if it fails
    os.system("dbus-send --session --type=method_call --dest=org.freedesktop.Notifications "
              "/org/freedesktop/Notifications org.freedesktop.Notifications.SystemNoteInfoprint "
              "string:'%s' >/dev/null 2>&1" % text)

def reachable(ip, t):
    s = socket.socket()
    s.settimeout(t)
    try:
        s.connect((ip, PRINTER[1]))
        return True
    except Exception:
        return False
    finally:
        s.close()

def mac_of(ip):  # from the phone's ARP table, filled by the connect just made
    for line in open("/proc/net/arp").readlines()[1:]:
        f = line.split()
        if f and f[0] == ip:
            return f[3].lower()
    return None

def want_mac():
    return os.path.exists(MACFILE) and open(MACFILE).read().strip().lower() or None

def is_printer(ip):  # another device on 9100 (another network printer) must not win
    want = want_mac()
    return reachable(ip, 3.0) and (not want or mac_of(ip) == want)

def toint(ip):
    a = [int(x) for x in ip.split(".")]
    return (a[0] << 24) + (a[1] << 16) + (a[2] << 8) + a[3]

def tostr(n):
    return ".".join([str((n >> k) & 255) for k in (24, 16, 8, 0)])

def scan():  # every address on the phone's own Wi-Fi network (a hotspot has only 14), 32 at a time
    out = os.popen("ifconfig wlan0 2>/dev/null").read()
    m = re.search(r"inet addr:(\S+).*?Mask:(\S+)", out)
    if not m:
        return None
    me, mask = toint(m.group(1)), toint(m.group(2))
    net = me & mask
    ips = [tostr(net + i) for i in range(1, (~mask & 0xffffffff)) if net + i != me][:254]
    found = []
    want = want_mac()
    threading.stack_size(64 * 1024)
    for i in range(0, len(ips), 32):
        ts = [threading.Thread(target=lambda ip=ip: reachable(ip, 3.0) and found.append(ip)) for ip in ips[i:i + 32]]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        for ip in found:
            if want and mac_of(ip) == want:
                return ip
        if found and not want:
            break
    found.sort()  # no hardware-address match: the lowest address answering on 9100 wins
    return found and found[0] or None

def printer_ip():
    cached = os.path.exists(IPFILE) and open(IPFILE).read().strip() or None
    env = os.environ.get("PRINTER_IP")
    for ip in (env, cached, PRINTER[0]):
        if ip and (ip == env and reachable(ip, 3.0) or ip != env and is_printer(ip)):  # 3 s: first connect over the hotspot can take over 1 s
            break
    else:
        ip = scan()
    if ip and ip != cached:
        open(IPFILE, "w").write(ip)
    return ip

def newest():  # by filename (YYYYMMDD_NNN.jpg), because the phone clock was wrong early on
    names = [n for n in os.listdir(DCIM) if n.lower().endswith(".jpg")]
    if not names:
        raise SystemExit("No photos in " + DCIM)
    names.sort()
    return os.path.join(DCIM, names[-1])

def raster(path):
    im = Image.open(path)
    try:
        orient = im._getexif().get(274, 1)
    except Exception:
        orient = 1
    im.draft("L", (W * 2, W * 2))  # decode at reduced size: the phone has ~25 MB of free RAM
    im = ImageOps.autocontrast(im.convert("L"), cutoff=1)
    im = im.resize((W, int(round(im.size[1] * W / float(im.size[0])))), FILT)
    turn = {3: Image.ROTATE_180, 6: Image.ROTATE_270, 8: Image.ROTATE_90}.get(orient)
    if turn is not None:  # rotate after the resize: cheaper. Rotated 90 degrees, it is no longer W wide.
        im = im.transpose(turn)
        if im.size[0] != W:
            im = im.resize((W, int(round(im.size[1] * W / float(im.size[0])))), FILT)
    im = im.point([int(round(255 * (v / 255.0) ** (1 / GAMMA))) for v in range(256)])
    h = im.histogram()  # PIL 1.1.6's ImageEnhance.Contrast darkens the image, so do it by hand (pivot = mean)
    mean = int(sum([i * h[i] for i in range(256)]) / float(sum(h)) + 0.5)
    im = im.point([max(0, min(255, int(mean + (v - mean) * CONTRAST + 0.5))) for v in range(256)])
    # PIL 1.1.6 has no UnsharpMask: blend(blur, im, 1 + pct/100) is the same thing (5x5 binomial blur)
    row = (1, 4, 6, 4, 1)
    blur = im.filter(ImageFilter.Kernel((5, 5), [a * b for a in row for b in row], 256))
    im = Image.blend(blur, im, 1 + SHARPEN / 100.0)
    return im.convert("1")  # PIL's default conversion is Floyd-Steinberg

def job(im):
    w, h = im.size
    inv = "".join([chr(255 - i) for i in range(256)])  # PIL: 1 = white; ESC/POS: 1 = black
    data = im.tostring().translate(inv)
    return ("\x1b@" + "\x1ba\x01" + "\x1d|\x05"  # reset, centre, density 8
            + "\x1dv0\x00" + chr((w // 8) % 256) + chr((w // 8) // 256) + chr(h % 256) + chr(h // 256)
            + data + "\n\n" + "\x1dV\x42\x40")  # raw partial cut

def main(argv):
    if "--find" in argv:  # prints the printer's address, sends nothing
        print printer_ip()
        return
    dry = None
    if "--dry" in argv:
        i = argv.index("--dry")
        dry = argv[i + 1]
        del argv[i:i + 2]
    path = argv[1] if len(argv) > 1 else newest()
    if not dry:
        if os.path.exists(RUNNING) and time.time() - os.path.getmtime(RUNNING) < 120:
            say("Memorycam: already printing")
            raise SystemExit("Already printing")
        open(RUNNING, "w").write("1")
    try:
        say("Memorycam: preparing photo")
        data = job(raster(path))
        if dry:
            open(dry, "wb").write(data)
            return
        if os.path.exists(STAMP):
            wait = float(open(STAMP).read()) - time.time()
            if wait > 0:
                time.sleep(wait)  # back-to-back jobs make the printer print garbage
        ip = printer_ip()
        if not ip:
            say("Memorycam: printer not found")
            raise SystemExit("Printer not found on this network")
        s = socket.socket()
        s.settimeout(60)  # per chunk: the iPhone hotspot can stall for many seconds (a 20 s stall cut a job mid-image on Nov 4)
        s.connect((ip, PRINTER[1]))
        sent = 0
        while sent < len(data):  # small chunks; on any error, raise and never resend (a cut job prints garbage)
            sent += s.send(data[sent:sent + 2048])
        h = len(data) // 72  # about image height in dots
        time.sleep(4 + h / 100.0)  # keep the connection open until the printer is done
        s.close()
        open(STAMP, "w").write(str(time.time() + 5))
        say("Memorycam: printed")
    except Exception:
        say("Memorycam: print failed")
        raise
    finally:
        if not dry and os.path.exists(RUNNING):
            os.remove(RUNNING)

if __name__ == "__main__":
    main(sys.argv)
