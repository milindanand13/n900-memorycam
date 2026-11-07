#!/bin/sh
# Memorycam: ask the Mac print desk to print the newest N900 photo. The Mac checks every 2 minutes.
cd /home/user/MyDocs/DCIM || exit 1
newest=$(ls -t *.jpg *.JPG 2>/dev/null | head -n 1)
note() {
  dbus-send --type=method_call --dest=org.freedesktop.Notifications /org/freedesktop/Notifications \
    org.freedesktop.Notifications.SystemNoteInfoprint string:"$1"
}
if [ -z "$newest" ]; then note "Memorycam: no photo to print"; exit 1; fi
# Write then rename, so the Mac never reads a half-written request.
echo "$(date +%s) $newest" > /home/user/MyDocs/.memorycam-print.tmp &&
  mv /home/user/MyDocs/.memorycam-print.tmp /home/user/MyDocs/.memorycam-print &&
  note "Memorycam: $newest will print within 2 minutes"
