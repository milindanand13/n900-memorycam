#!/usr/bin/python
# Thumbnail grid of the camera folder (newest first). Tap a photo, confirm, and it prints (same path as print_latest.py).
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gtk, gobject, hildon, Image
import print_latest

T = 150  # thumbnail size in pixels
names = sorted([n for n in os.listdir(print_latest.DCIM) if n.lower().endswith(".jpg")], reverse=True)
chosen = []

def thumb(name):  # PIL decodes the JPEG at 1/8 size, so this is fast on the phone
    im = Image.open(os.path.join(print_latest.DCIM, name))
    try:
        orient = im._getexif().get(274, 1)
    except Exception:
        orient = 1
    im.draft("RGB", (T, T))
    im = im.convert("RGB")
    turn = {3: Image.ROTATE_180, 6: Image.ROTATE_270, 8: Image.ROTATE_90}.get(orient)
    if turn is not None:
        im = im.transpose(turn)
    w, h = im.size
    s = T / float(min(w, h))
    im = im.resize((max(T, int(w * s + 0.5)), max(T, int(h * s + 0.5))))
    l, t = (im.size[0] - T) // 2, (im.size[1] - T) // 2
    im = im.crop((l, t, l + T, t + T))
    return gtk.gdk.pixbuf_new_from_data(im.tostring(), gtk.gdk.COLORSPACE_RGB, False, 8, T, T, T * 3)

store = gtk.ListStore(gtk.gdk.Pixbuf, str)
blank = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, T, T)
blank.fill(0x333333ff)
for n in names:
    store.append([blank, n])

todo = list(range(len(names)))
def load_next():  # one thumbnail per idle tick, so the grid shows at once and fills in
    if not todo:
        return False
    i = todo.pop(0)
    try:
        store[i][0] = thumb(names[i])
    except Exception:
        pass
    return True

def tapped(view, path):
    name = store[path][1]
    ask = gtk.MessageDialog(win, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, "Print %s?" % name)
    ok = ask.run() == gtk.RESPONSE_YES
    ask.destroy()
    if ok:
        chosen.append(os.path.join(print_latest.DCIM, name))
        gtk.main_quit()

win = hildon.StackableWindow()
win.set_title("Choose photo to print")
view = gtk.IconView(store)
view.set_pixbuf_column(0)
view.set_columns(4)
view.set_margin(4)
view.set_spacing(2)
view.connect("item-activated", tapped)
area = hildon.PannableArea()
area.add(view)
win.add(area)
win.connect("destroy", gtk.main_quit)
win.show_all()
gobject.idle_add(load_next)
gtk.main()
if chosen:
    print_latest.main(["print_latest.py", chosen[0]])
