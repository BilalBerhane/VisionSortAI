#!/usr/bin/env python3
"""Generates a printable QR code pointing at the web interface.

This is meant to be printed ONCE and taped/stuck near the Pi -- it's a
static image, not regenerated per run. It only needs to change if the Pi's
hostname changes.

Usage:
    python generate_qr.py --url http://analyze-and-backup.local:5000
    python generate_qr.py --url http://analyze-and-backup.local:5000 --out qr_sign.png --caption "Scan to see your photos"

Why a hostname, not a raw IP: IP addresses handed out by DHCP can change
every time the Pi reconnects to a network. A stable hostname avoids needing
to reprint the sign. On Raspberry Pi OS, avahi-daemon (usually installed by
default) automatically makes the Pi reachable at <hostname>.local on any
network that supports mDNS -- set the hostname with `sudo raspi-config`
(System Options > Hostname) or by editing /etc/hostname and /etc/hosts.
Devices must be on the same local network as the Pi; this does not work
over the open internet.
"""
from __future__ import annotations

import argparse

import qrcode
from PIL import Image, ImageDraw, ImageFont


def build_qr_sign(url: str, caption: str, size_px: int = 900) -> Image.Image:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,  # quiet zone -- required for reliable scanning, don't shrink this
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_img = qr_img.resize((size_px, size_px), Image.NEAREST)

    caption_height = 120
    canvas = Image.new("RGB", (size_px, size_px + caption_height), "white")
    canvas.paste(qr_img, (0, 0))

    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
        url_font = ImageFont.truetype("DejaVuSans.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
        url_font = font

    bbox = draw.textbbox((0, 0), caption, font=font)
    text_w = bbox[2] - bbox[0]
    draw.text(((size_px - text_w) / 2, size_px + 20), caption, fill="black", font=font)

    bbox2 = draw.textbbox((0, 0), url, font=url_font)
    text_w2 = bbox2[2] - bbox2[0]
    draw.text(((size_px - text_w2) / 2, size_px + 70), url, fill="#555555", font=url_font)

    return canvas


def main():
    parser = argparse.ArgumentParser(description="Generate a printable QR code for the web interface")
    parser.add_argument("--url", required=True, help="Full URL to encode, e.g. http://analyze-and-backup.local:5000")
    parser.add_argument("--out", default="qr_sign.png", help="Output image path")
    parser.add_argument("--caption", default="Scan to see your photos", help="Caption printed below the QR code")
    parser.add_argument("--size", type=int, default=900, help="QR code size in pixels (square)")
    args = parser.parse_args()

    sign = build_qr_sign(args.url, args.caption, args.size)
    sign.save(args.out)
    print(f"Saved {args.out} ({sign.width}x{sign.height}px) encoding: {args.url}")
    print("Print this once and stick it near the Pi. Re-run this script only if the URL changes.")


if __name__ == "__main__":
    main()
