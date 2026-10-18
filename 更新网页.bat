@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo ==========================================================
echo   AI Book - rebuild the website from  src\book.md
echo   (this only rearranges text into a web page; no internet)
echo ==========================================================
echo.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "build\make.py"
) else (
    python "build\make.py"
)
echo.
echo ----------------------------------------------------------
echo   Finished. You can now open index.html
echo ----------------------------------------------------------
pause
