#!/usr/bin/env bash
set -euo pipefail

echo "== ping =="
wandctl ping

echo "== providers =="
wandctl providers

echo "== games =="
wandctl games

echo "== proton tools =="
wandctl protons

echo "== persisted sessions =="
wandctl sessions

echo
echo "Next:"
echo "  wandctl inspect APPID"
echo "  wandctl start-session APPID /path/to/Trainer.exe"
