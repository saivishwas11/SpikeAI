#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# SpikeAI Deployment Script
#
# Responsibilities:
# - Ensure we run from the project root
# - Create and/or reuse a local virtual environment
# - Install Python dependencies from requirements.txt
# - Start the FastAPI app (which in turn initializes agents and uses all modules)
#
# Usage (Linux/Unix):
#   chmod +x deploy.sh
#   ./deploy.sh
#
# Environment variables (optional):
#   PYTHON_BIN  - Python executable to use (default: python3, falls back to python)
#   HOST        - Host interface for the API (default: 0.0.0.0)
#   PORT        - Port for the API (default: 8080, must stay 8080 in some platforms)
###############################################################################

echo "Starting SpikeAI deployment..."

### 1. Move to project root (directory containing this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Working directory: $(pwd)"

### 2. Detect Python
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="${PYTHON_BIN:-python3}"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="${PYTHON_BIN:-python}"
else
  echo "Error: python3 or python is required but not found on PATH."
  exit 1
fi

echo "Using Python: $PYTHON_BIN"

### 3. Create / activate virtual environment
VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment in $VENV_DIR..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

echo "Activating virtual environment..."
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

### 4. Install dependencies
echo "Installing Python dependencies from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

### 5. Start the FastAPI application
# NOTE:
# - We use `python main.py` instead of `uvicorn main:app` because `main.py`
#   contains startup logic (SEO agent initialization) guarded by __main__.
# - main.py internally runs uvicorn on PORT (default 8080).
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8080}"

echo "Starting API server on ${HOST}:${PORT}..."
exec "$PYTHON_BIN" main.py
