@echo off
REM =============================================================================
REM build.bat — Build MatTherm Profiler into a single .exe
REM Run this from the project root (where matthermprofiler.py lives)
REM Requires: pip install pyinstaller pyvisa pyvisa-py pyusb pyserial minimalmodbus matplotlib numpy
REM =============================================================================

echo [1/4] Running pip install for dependencies...
pip install -r requirements.txt

echo [2/4] Cleaning previous build...
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist

echo [3/4] Running PyInstaller...
pyinstaller matthermprofiler.spec

echo [4/4] Done.
if exist dist\MatThermProfiler.exe (
    echo.
    echo  SUCCESS: dist\MatThermProfiler.exe
    echo  Size:
    for %%A in (dist\MatThermProfiler.exe) do echo    %%~zA bytes
) else (
    echo.
    echo  BUILD FAILED — check output above for errors.
    exit /b 1
)
pause