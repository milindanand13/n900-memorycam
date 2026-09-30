#!/bin/sh
# Copy one photo from a Nokia N900 to this Mac over SSH, verified by MD5.
#
# Usage:
#   N900_HOST=<phone-ip> scripts/n900-fetch-photo.sh              # the new photo
#   N900_HOST=<phone-ip> scripts/n900-fetch-photo.sh 20090119_004.jpg
#
# SSH asks for the N900 root password in your terminal; this script never
# reads or stores it. Photos land in private/inbox/, which git ignores.
# With no name, it fetches the one photo on the phone that is not already in
# the inbox (or in MEMORYCAM_ARCHIVE, if set). It does not use dates or file
# times, because the N900's clock is wrong and old photos can look newer.
set -eu

host=${N900_HOST:?Set N900_HOST to the N900 IP address, e.g. N900_HOST=172.20.10.6}
repo_root=$(cd "$(dirname "$0")/.." && pwd)
inbox=${MEMORYCAM_INBOX:-"$repo_root/private/inbox"}
archive=${MEMORYCAM_ARCHIVE:-}
name=${1:-}

case "$name" in
    *[!A-Za-z0-9._-]*|.*) printf 'Unexpected photo filename: %s\n' "$name" >&2; exit 1 ;;
esac

mkdir -p "$inbox"

# Photo names already on the Mac. Only safe characters are kept, so the list
# can be quoted into the remote command.
known=$(for dir in "$inbox" ${archive:+"$archive"}; do
    [ -d "$dir" ] && ls "$dir"
done | grep -E '^[A-Za-z0-9._-]+$' | tr '\n' ' ')

payload=$(mktemp "$inbox/.n900-transfer.XXXXXX")
image_part=$(mktemp "$inbox/.n900-image.XXXXXX")
trap 'rm -f "$payload" "$image_part"' EXIT

# Runs in the N900's BusyBox shell: print the filename, its checksum, then its bytes.
remote_command="cd /home/user/MyDocs/DCIM || exit 1
f='$name'
if [ -z \"\$f\" ]; then
    known=' $known '
    count=0
    for c in *.jpg *.JPG; do
        [ -f \"\$c\" ] || continue
        case \"\$known\" in *\" \$c \"*) continue ;; esac
        count=\$((count + 1))
        f=\"\$c\"
        echo \"New on phone: \$c\" >&2
    done
    [ \"\$count\" -eq 1 ] || { echo \"Found \$count photos not yet on the Mac; expected exactly 1. Pass a filename to choose one.\" >&2; exit 1; }
fi
[ -f \"\$f\" ] || { echo \"Photo not found on the N900: \$f\" >&2; exit 1; }
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
