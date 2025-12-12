#!/bin/bash
set -e

TMPDIR=$(mktemp -d)

wget -O "$TMPDIR/waifudownloaderqt" \
  https://github.com/KairaBegudiri/WaifuDownloaderQt/releases/download/v1.5.0/waifudownloaderqt
chmod +x "$TMPDIR/waifudownloaderqt"
sudo mv "$TMPDIR/waifudownloaderqt" /usr/bin/waifudownloaderqt

mkdir -p ~/.local/share/applications
wget -O ~/.local/share/applications/waifudownloaderqt.desktop \
  https://github.com/KairaBegudiri/WaifuDownloaderQt/releases/download/v1.5.0/waifudownloaderqt.desktop

mkdir -p ~/.local/share/icons
wget -O ~/.local/share/icons/moe.nyarchlinux.waifudownloader.png \
  https://raw.githubusercontent.com/NyarchLinux/WaifuDownloader/master/data/icons/moe.nyarchlinux.waifudownloader.png

rm -rf "$TMPDIR"
