#!/usr/bin/env bash
# Regenerate screenshots with headless Chrome (needs ./run.sh on port 4262).
cd "$(dirname "$0")"
U=http://127.0.0.1:${PORT:-4262}/
mkdir -p screenshots
shot(){ local d; d=$(mktemp -d); google-chrome --headless=new --no-sandbox --disable-gpu --hide-scrollbars --user-data-dir="$d" --virtual-time-budget=4000 --window-size="$1" --force-device-scale-factor="$2" --screenshot="screenshots/$3" "$4" >/dev/null 2>&1; rm -rf "$d"; }
shot 1440,1600 1 00-best-home.png "$U"
shot 1440,1400 1 desktop-02-kids-filter.png "${U}?area=kids"
shot 1440,1500 1 desktop-03-build-night-shelf.png "${U}?view=shelf"
shot 1440,1400 1 desktop-04-attention.png "${U}?area=attention"
shot 390,1800 2 phone-01-top.png "$U"
shot 390,1600 2 phone-02-search-tutor.png "${U}?q=tutor"
shot 390,1800 2 phone-03-snapshot-family.png "file://$PWD/dist/bot-launcher-snapshot.html?area=family"
ls -la screenshots
