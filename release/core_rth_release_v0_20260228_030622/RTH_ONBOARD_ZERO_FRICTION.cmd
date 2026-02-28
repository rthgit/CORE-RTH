@echo off
cd /d %~dp0
python scripts\onboard_zero_friction.py --start-api-if-needed --start-llama-if-needed %*
