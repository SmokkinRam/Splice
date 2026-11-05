#!/bin/bash
cd "$(dirname "$0")"
source .venv/Scripts/activate
export HF_HUB_DISABLE_SYMLINKS_WARNING=1
export MIC=1
python -m assistant.main
