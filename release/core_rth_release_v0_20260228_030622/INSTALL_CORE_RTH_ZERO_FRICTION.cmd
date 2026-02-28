@echo off
cd /d %~dp0
python scripts\install_zero_friction_local.py --start-api --start-llama %*
