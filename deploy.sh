#!/bin/bash
set -e

echo "🚀 Starting Deployment..."

# 1. Install 'uv' for fast dependency management (Fallback to pip if fails)
echo "📦 Installing uv for speed..."
curl -LsSf https://astral.sh/uv/install.sh | sh || pip install uv
source $HOME/.cargo/env || true

# 2. Install Dependencies using uv (much faster than pip)
echo "📥 Installing requirements..."
uv pip install --system -r requirements.txt

# 3. Start the Server
echo "🔥 Starting Uvicorn Server on Port 8080..."
# Using --workers 1 for the hackathon to avoid memory issues with large sheets
python main.py