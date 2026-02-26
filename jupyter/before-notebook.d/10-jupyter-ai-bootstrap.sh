#!/usr/bin/env bash
# This hook is sourced by start.sh; isolate shell options to avoid side effects.
(
  set -euo pipefail
  bash /opt/training/scripts/jupyter_ai_bootstrap.sh || true
)
