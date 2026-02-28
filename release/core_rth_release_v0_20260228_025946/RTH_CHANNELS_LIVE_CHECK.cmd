@echo off
cd /d %~dp0
python scripts\channels_live_final_check.py %*
