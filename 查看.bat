@echo off
rem 查看最近 20 条剪贴板记录
cd /d "%~dp0"
python src\main.py --dump 20
pause
