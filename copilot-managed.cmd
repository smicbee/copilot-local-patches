@echo off
python "%~dp0patch-appjs.py" %*
exit /b %errorlevel%
