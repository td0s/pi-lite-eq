#!/bin/sh
# Install the Pi-Lite EQ meter as a service (Ubuntu or Raspberry Pi OS).
# Run from the project folder: ./install.sh
set -e
cd "$(dirname "$0")"

sudo apt-get install -y python3-numpy python3-serial alsa-utils

sed -e "s|@DIR@|$PWD|" -e "s|@USER@|$(id -un)|" systemd/pilite-eq.service \
  | sudo tee /etc/systemd/system/pilite-eq.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now pilite-eq

echo "Installed. Check it with: systemctl status pilite-eq"
