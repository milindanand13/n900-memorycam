# Mac-side check: decode the ESC/POS bytes made by print_latest.py back into a PNG, and optionally
# compare with the Mac printer's output. Usage: python check_bytes.py job.bin out.png [photo.jpg]
# (the comparison needs Claude/print_slip.py and Pillow; it prints the share of differing dots)
import sys
from PIL import Image
d = open(sys.argv[1], "rb").read()
i = d.index(b"\x1dv0\x00")
w, h = (d[i + 4] + 256 * d[i + 5]) * 8, d[i + 6] + 256 * d[i + 7]
body = d[i + 8:i + 8 + w // 8 * h]
assert len(body) == w // 8 * h and d.endswith(b"\n\n\x1dV\x42\x40") and d.startswith(b"\x1b@"), "bad ESC/POS framing"
img = Image.frombytes("1", (w, h), bytes(255 - b for b in body))
img.save(sys.argv[2])
print("decoded", w, "x", h)
if len(sys.argv) > 3:
    sys.path.insert(0, "../../../../Claude")
    from print_slip import prepare
    ref = prepare(sys.argv[3], 1.2, 0.8, "fs", 50)
    print("mac", ref.size)
    if ref.size == img.size:
        a, b = ref.convert("L").tobytes(), img.convert("L").tobytes()
        print("differing dots: %.1f%%" % (100.0 * sum(x != y for x, y in zip(a, b)) / len(a)))
        ref.save(sys.argv[2].replace(".png", "-mac.png"))
