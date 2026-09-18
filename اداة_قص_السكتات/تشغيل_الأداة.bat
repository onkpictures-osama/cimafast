@echo off
chcp 65001 >nul
where python >nul 2>&1
if %errorlevel% neq 0 goto :no_python
python "%~dp0launcher.py"
goto :eof

:no_python
echo Python is not installed on your PC.
echo Please install it first from: https://www.python.org/downloads/
echo IMPORTANT: check "Add Python to PATH" during setup.
pause
