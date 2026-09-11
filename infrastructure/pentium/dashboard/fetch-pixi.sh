#!/usr/bin/env bash
set -euo pipefail

VERSION="8.20.1"
SHA256="9948591083793305468d73915a3ea85032dcf8e32eee7a1328585050d7a14d53"
URL="https://github.com/pixijs/pixijs/releases/download/v${VERSION}/pixi.min.js"
TARGET="${1:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/pixi.min.js}"
TMP="${TARGET}.tmp"

rm -f "$TMP"
curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 --max-time 60 "$URL" -o "$TMP"
printf '%s  %s\n' "$SHA256" "$TMP" | sha256sum --check --status
install -m 0644 "$TMP" "$TARGET"
rm -f "$TMP"
printf 'PIXIJSHASH=%s\n' "$SHA256"
