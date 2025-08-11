@echo off
REM Multi-File Dynamic Runner Batch Script
REM Easy execution for Windows users

echo Multi-File Dynamic Runner
echo =========================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python first.
    pause
    exit /b 1
)

REM Check if multi_runner.py exists
if not exist "multi_runner.py" (
    echo ERROR: multi_runner.py not found in current directory.
    pause
    exit /b 1
)

REM Default settings
set PATTERN=*.py
set MODE=process
set DIRECTORY=.

REM Show usage if help requested
if "%1"=="help" goto :help
if "%1"=="--help" goto :help
if "%1"=="/?" goto :help

REM Parse basic arguments
if not "%1"=="" set PATTERN=%1
if not "%2"=="" set MODE=%2
if not "%3"=="" set DIRECTORY=%3

echo Running files with pattern: %PATTERN%
echo Execution mode: %MODE%
echo Directory: %DIRECTORY%
echo.

REM Execute the runner
python multi_runner.py --directory "%DIRECTORY%" --pattern "%PATTERN%" --mode "%MODE%" --validate

if errorlevel 1 (
    echo.
    echo ERROR: Execution failed!
    pause
    exit /b 1
)

echo.
echo Execution completed successfully!
pause
goto :end

:help
echo Usage: run_multiple.bat [pattern] [mode] [directory]
echo.
echo Examples:
echo   run_multiple.bat                    - Run all *.py files in current directory
echo   run_multiple.bat "1.py,2.py,3.py"  - Run specific files
echo   run_multiple.bat "*.py" thread     - Run all .py files in thread mode
echo   run_multiple.bat "*.py" process "C:\mydir" - Run files in specific directory
echo.
echo Modes: process, thread, module, sequential
pause

:end
