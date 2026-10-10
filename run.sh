#!/usr/bin/env bash
# Start Bot Launcher on port 4262 (4261 is used by Bot Island 3D) (rebuilds catalog + snapshot first).
cd "$(dirname "$0")"
PORT="${PORT:-4262}"
if [ -f data/server.pid ] && kill -0 "$(cat data/server.pid)" 2>/dev/null; then kill "$(cat data/server.pid)"; sleep 0.5; fi
PORT=$PORT nohup python3 server.py > data/server.log 2>&1 &
echo $! > data/server.pid
for i in $(seq 1 20); do curl -fs "http://127.0.0.1:$PORT/healthz" | grep -q bot-launcher && break; sleep 0.3; done
echo "Bot Launcher: http://127.0.0.1:$PORT/  (pid $(cat data/server.pid))"
echo "Snapshot: $PWD/dist/bot-launcher-snapshot.html"
curl -fs "http://127.0.0.1:$PORT/healthz" | grep -q bot-launcher || { echo "ERROR: server not healthy on $PORT; see data/server.log"; exit 1; }
