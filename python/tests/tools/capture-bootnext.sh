#!/bin/sh
# Capture efibootmgr output while a BootNext entry is set.
# Sets BootNext WITHOUT rebooting, dumps the output into test-data, then clears it.
#
#   chmod a+x capture-bootnext.sh
#   sudo ./capture-bootnext.sh

set -e

OUT_DIR="$(cd "$(dirname "$0")" && pwd)/test-data"

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run as root: sudo $0" >&2
    exit 1
fi

echo "Current boot entries:"
efibootmgr | grep '^Boot[0-9A-Fa-f]\{4\}' || true
echo

printf "Enter the boot id to set as BootNext (e.g. 0004): "
read -r BOOT_ID

if ! echo "$BOOT_ID" | grep -qE '^[0-9A-Fa-f]{4}$'; then
    echo "'$BOOT_ID' is not a valid 4-hex-digit boot id." >&2
    exit 1
fi

echo "Setting BootNext to $BOOT_ID (no reboot happens)..."
efibootmgr -n "$BOOT_ID"

mkdir -p "$OUT_DIR"
efibootmgr -v > "$OUT_DIR/efibootmgr-verbose-bootnext.txt"
efibootmgr > "$OUT_DIR/efibootmgr-bootnext.txt"
echo "Saved:"
echo "  $OUT_DIR/efibootmgr-verbose-bootnext.txt"
echo "  $OUT_DIR/efibootmgr-bootnext.txt"
echo

printf "Clear BootNext now? [Y/n] "
read -r ANSWER
case "$ANSWER" in
    n|N)
        echo "Left BootNext set. The next reboot will boot $BOOT_ID once."
        echo "Clear it later with: sudo efibootmgr -N"
        ;;
    *)
        efibootmgr -N
        echo "BootNext cleared. Nothing will change on the next reboot."
        ;;
esac
