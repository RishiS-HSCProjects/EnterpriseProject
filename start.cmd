@echo off

:: Change to the directory where the batch file is located
cd /d %~dp0

call .venv\Scripts\activate.bat

set FLASK_APP=run.py
set FLASK_ENV=development

python run.py

pause
