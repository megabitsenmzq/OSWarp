#!/bin/bash
# Install missing dependencies and add an application menu entry.
set -euo pipefail
self=$(readlink -f "$0")
cd "$(dirname "$self")"
if [ "$(id -u)" -ne 0 ]; then
  exec sudo --preserve-env=XDG_CURRENT_DESKTOP,XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS "$self" "$@"
fi

install_pkgs() {
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y "$@"
    return
  fi
  if command -v dnf >/dev/null 2>&1; then
    dnf install -y "$@"
    return
  fi
  if command -v pacman >/dev/null 2>&1; then
    pacman -S --needed --noconfirm "$@"
    return
  fi
  echo "apt, dnf, or pacman was not found. Install these first: $*" >&2
  exit 1
}

need=()
if ! command -v python3 >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1 || command -v dnf >/dev/null 2>&1 || ! command -v pacman >/dev/null 2>&1; then
    need+=(python3)
  else
    need+=(python)
  fi
fi
command -v efibootmgr >/dev/null 2>&1 || need+=(efibootmgr)
if ! command -v pkexec >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    need+=(pkexec)
  else
    need+=(polkit)
  fi
fi
desktop=$(printf '%s' "${XDG_CURRENT_DESKTOP:-}" | tr '[:upper:]' '[:lower:]')
case ":${desktop}:" in
  *:kde:*)
    command -v kdialog >/dev/null 2>&1 || need+=(kdialog)
    ;;
  *:gnome:*)
    command -v zenity >/dev/null 2>&1 || need+=(zenity)
    ;;
  *)
    command -v yad >/dev/null 2>&1 || need+=(yad)
    ;;
esac
if [ "${#need[@]}" -gt 0 ]; then
  install_pkgs "${need[@]}"
fi

install -d /usr/local/share/oswarp
rm -rf /usr/local/share/oswarp/oswarp
cp -r --no-preserve=ownership oswarp /usr/local/share/oswarp/
cp --no-preserve=ownership Icon.png /usr/local/share/oswarp/Icon.png
chown -R root:root /usr/local/share/oswarp
chmod -R u=rwX,go=rX /usr/local/share/oswarp
install -d /usr/local/bin
install -m 755 run.sh /usr/local/bin/oswarp
install -d /usr/local/share/applications /usr/share/polkit-1/actions
cp oswarp.desktop /usr/local/share/applications/oswarp.desktop
cp com.oswarp.policy /usr/share/polkit-1/actions/com.oswarp.policy
chmod 644 /usr/local/share/applications/oswarp.desktop /usr/share/polkit-1/actions/com.oswarp.policy
if command -v kbuildsycoca6 >/dev/null 2>&1 && [ -n "${SUDO_USER:-}" ]; then
  if ! sudo -u "$SUDO_USER" --preserve-env=XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS kbuildsycoca6 --noincremental; then
    echo "If OSWarp does not appear in the application menu, refresh the cache manually."
  fi
fi
echo "Installed. Open OSWarp from the application menu, or run oswarp."
