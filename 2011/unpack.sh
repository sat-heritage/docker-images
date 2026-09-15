#!/bin/bash
# Unpack the downloaded archive into /src.  The 2011 sources also come as plain
# tar, tar.bz2 and 7z, and some submissions need companion files (the organizers
# compile scripts, patches, other archives) listed as EXTRA_ASSETS in setup.json:
# they are downloaded next to the unpacked sources, as in the competition tree.
set -ex
asset="$1"
name="$(basename "$asset")"
case "$asset" in
    *.tar.gz|*.tgz) tar xzf "$asset" ;;
    *.tar.xz) tar xJf "$asset" ;;
    *.tar.bz2) apt-get install -y --no-install-recommends bzip2 >/dev/null 2>&1 || apt-get update >/dev/null && apt-get install -y --no-install-recommends bzip2; tar xjf "$asset" ;;
    *.tar) tar xf "$asset" ;;
    *.zip) unzip -q "$asset" ;;
    *.7z) apt-get update >/dev/null && apt-get install -y --no-install-recommends p7zip-full >/dev/null && 7z x "$asset" ;;
    *) echo "unknown archive type: $asset" >&2; exit 1 ;;
esac
# companion files of this archive, from the entry of /setup.json that downloads it
base="${2:-$(grep -o "https://[^\"]*/${name}\"" /setup.json | head -1 | sed "s|/${name}\"||")}"
extras="$(tr -d "\n" < /setup.json | grep -o "\"download_url\": *\"[^\"]*/${name}\"[^}]*" | grep -o "\"EXTRA_ASSETS\": *\"[^\"]*\"" | head -1 | sed "s/.*: *\"//; s/\"$//")"
for extra in $extras; do
    [ -e "$extra" ] || curl -fsSL -o "$extra" "${base}/${extra}"
done
cp "$asset" . 2>/dev/null || true   # the organizers scripts re-extract the archive from the working directory
ls -la
