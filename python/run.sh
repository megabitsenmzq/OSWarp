#!/bin/bash
# Open the window. Pass kdialog, zenity, or yad alone to choose that dialog.
# pkexec runs this same script again with the boot id and the boot setting.
# A checkout keeps the package beside this script. The installed copy uses /usr/local/share/oswarp.
root=$(cd "$(dirname "$0")" && pwd)
if [ -d "$root/oswarp" ]; then
  export PYTHONPATH="$root${PYTHONPATH:+:$PYTHONPATH}"
else
  export PYTHONPATH="/usr/local/share/oswarp${PYTHONPATH:+:$PYTHONPATH}"
fi

python3=""
for candidate in /usr/local/bin/python3 /usr/bin/python3 /bin/python3; do
  if [ -x "$candidate" ]; then
    python3=$candidate
    break
  fi
done
if [ -z "$python3" ]; then
  python3=$(command -v python3 || true)
fi
if [ -z "$python3" ]; then
  echo "Could not find python3." >&2
  exit 1
fi
exec "$python3" -m oswarp "$@"
