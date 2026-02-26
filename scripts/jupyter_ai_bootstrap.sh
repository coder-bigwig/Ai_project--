#!/usr/bin/env bash
set -euo pipefail

cd /opt/training
python scripts/jupyter_ai_write_config.py
python scripts/patch_jupyter_ai_branding.py || true
