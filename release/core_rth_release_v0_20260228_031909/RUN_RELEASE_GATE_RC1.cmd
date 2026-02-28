@echo off
cd /d %~dp0
python scripts\release_gate_rc1.py --start-api-if-needed %*
