@echo off
rem 运行剪贴板历史监听程序（阶段1，命令行版；关闭此窗口即停止）
cd /d "%~dp0"
python src\main.py
pause
