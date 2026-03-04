#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$HOME/ai-fund-monitor}"
PYTHON_BIN="${2:-python3}"

echo "[1/6] Installing system packages..."
sudo apt-get update
sudo apt-get install -y git python3-venv python3-pip

echo "[2/6] Enter project dir: ${PROJECT_DIR}"
cd "${PROJECT_DIR}/worker"

echo "[3/6] Creating virtual environment..."
${PYTHON_BIN} -m venv .venv
source .venv/bin/activate

echo "[4/6] Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "[5/6] Preparing runtime folders..."
mkdir -p runtime/models

echo "[6/6] Initializing SQLite schema..."
python scripts/init_db.py

echo "Done. Next:"
echo "1) Copy worker/.env.example to worker/.env and fill secrets"
echo "2) Run: python scripts/run_once.py"
echo "3) Configure cron from worker/deploy/cron.example"

