@echo off
REM Rebuilds the calendar locally and sends the new Excel / blocked dates to GitHub.
REM Needs Python (with openpyxl) and Git installed, and this folder cloned from your GitHub repository.
cd /d %~dp0
python build.py --no-fetch
if errorlevel 1 goto :end
git add data config.json
git commit -m "Update prices / blocked dates"
git push
:end
pause
