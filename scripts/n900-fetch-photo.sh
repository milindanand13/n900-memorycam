#!/bin/sh
# Copy one photo from a Nokia N900 to this Mac over SSH, verified by MD5.
#
# Usage:
#   N900_HOST=<phone-ip> scripts/n900-fetch-photo.sh              # newest photo
#   N900_HOST=<phone-ip> scripts/n900-fetch-photo.sh 20090119_004.jpg
#
# SSH asks for the N900 root password in your terminal; this script never
# reads or stores it. Photos land in private/inbox/, which git ignores.
# The newest photo is chosen by file order on the phone, not by its date,
# because the N900's clock may be wrong.
set -eu

host=${N900_HOST:?Set N900_HOST to the N900 IP address, e.g. N900_HOST=172.20.10.6}
repo_root=$(cd "$(dirname "$0")/.." && pwd)
inbox=${MEMORYCAM_INBOX:-"$repo_root/private/inbox"}
name=${1:-}

case "$name" in
    *[!A-Za-z0-9._-]*|.*) printf 'Unexpected photo filename: %s\n' "$name" >&2; exit 1 ;;
esac

mkdir -p "$inbox"
payload=$(mktemp "$inbox/.n900-transfer.XXXXXX")
image_part=$(mktemp "$inbox/.n900-image.XXXXXX")
trap 'rm -f "$payload" "$image_part"' EXIT

# Runs in the N900's BusyBox shell: print the filename, its checksum, then its bytes.
remote_command="cd /home/user/MyDocs/DCIM || exit 1
f='$name'
[ -n \"\$f\" ] || f=\$(ls -t *.jpg *.JPG 2>/dev/null | head -n 1)
[ -f \"\$f\" ] || { echo 'No photo found on the N900.' >&2; exit 1; }
echo \"\$f\"
md5sum \"\$f\"
cat \"\$f\""

printf 'Step 1: Connect to the N900 at %s. Enter its root password if prompted.\n' "$host"
if ! ssh -o ConnectTimeout=10 -o HostKeyAlgorithms=+ssh-rsa \
    "root@$host" "$remote_command" > "$payload"; then
    printf 'Transfer failed. No photo saved.\n' >&2
    exit 1
fi

IFS= read -r photo < "$payload"
case "$photo" in
    ''|.*|*[!A-Za-z0-9._-]*) printf 'Unexpected photo filename from the N900.\n' >&2; exit 1 ;;
esac
checksum_line=$(sed -n '2p' "$payload")
expected_checksum=${checksum_line%% *}
case "$expected_checksum" in
    ''|*[!0-9a-fA-F]*) printf 'Invalid checksum response.\n' >&2; exit 1 ;;
esac
[ "${#expected_checksum}" -eq 32 ] || { printf 'Invalid checksum length.\n' >&2; exit 1; }
tail -n +3 "$payload" > "$image_part"

printf 'Step 2: Verify the copied bytes against the phone checksum.\n'
actual_checksum=$(md5 -q "$image_part")
if [ "$actual_checksum" != "$expected_checksum" ]; then
    printf 'Checksum mismatch. No photo saved.\n' >&2
    exit 1
fi

destination="$inbox/$photo"
if [ -e "$destination" ]; then
    printf 'Already have %s. Nothing overwritten.\n' "$destination" >&2
    exit 1
fi
mv -n "$image_part" "$destination"
printf 'Step 3: Transfer verified.\nFile: %s\nMD5: %s\n' "$destination" "$actual_checksum"
