@echo off
rem ============================================================
rem 剪贴板历史 - 打包脚本
rem 生成：dist\ClipboardHistory.exe（单个 exe，免安装）
rem 用法：双击本文件，或在命令行运行 build.bat
rem ============================================================
cd /d "%~dp0\.."

echo [1/3] 生成图标 icon.ico ...
python 打包脚本\gen_icon.py
if errorlevel 1 ( echo 图标生成失败 & pause & exit /b 1 )

echo [2/3] 开始打包（PyInstaller onefile, 约 2~5 分钟）...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name ClipboardHistory --icon icon.ico ^
  --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick ^
  --exclude-module PySide6.QtWebEngineCore ^
  src\main.py
if errorlevel 1 ( echo 打包失败 & pause & exit /b 1 )

echo [3/3] 完成！exe 位置：dist\ClipboardHistory.exe
pause
