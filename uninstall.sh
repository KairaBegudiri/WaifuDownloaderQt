#!/bin/bash
set -e

echo "WaifuDownloaderQt kaldırılıyor..."

if [ -f /usr/bin/waifudownloaderqt ]; then
    sudo rm /usr/bin/waifudownloaderqt
fi

if [ -f "$HOME/.local/share/applications/waifudownloaderqt.desktop" ]; then
    rm "$HOME/.local/share/applications/waifudownloaderqt.desktop"
fi

if [ -f "$HOME/.local/share/icons/moe.nyarchlinux.waifudownloader.png" ]; then
    rm "$HOME/.local/share/icons/moe.nyarchlinux.waifudownloader.png"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database ~/.local/share/applications || true
fi
