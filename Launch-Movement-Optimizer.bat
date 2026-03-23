@echo off
title Movement Optimizer
echo ================================================
echo   Movement Optimizer
echo ================================================
echo.

set "PYTHON="

:: 1. Check common direct-install paths first
for %%V in (313 312 311 310 39) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
        set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
        goto :found
    )
)

:: 2. Check Program Files
for %%V in (313 312 311 310 39) do (
    if exist "C:\Python%%V\python.exe" (
        set "PYTHON=C:\Python%%V\python.exe"
        goto :found
    )
)
for %%V in (313 312 311 310 39) do (
    if exist "%ProgramFiles%\Python%%V\python.exe" (
        set "PYTHON=%ProgramFiles%\Python%%V\python.exe"
        goto :found
    )
)

:: 3. Try "py" launcher
where py >nul 2>nul
if %errorlevel%==0 (
    py --version >nul 2>nul
    if %errorlevel%==0 (
        set "PYTHON=py"
        goto :found
    )
)

:: 4. Try "python" (verify not Store stub)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set "PYVER=%%i"
echo %PYVER% | findstr /i "Python 3" >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON=python"
    goto :found
)

:: 5. Try "python3"
for /f "tokens=*" %%i in ('python3 --version 2^>^&1') do set "PYVER=%%i"
echo %PYVER% | findstr /i "Python 3" >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON=python3"
    goto :found
)

echo.
echo ERROR: Python was not found on your system.
echo.
echo To fix this:
echo   1. Go to https://www.python.org/downloads/
echo   2. Download the latest Python 3.x
echo   3. Run the installer
echo   4. IMPORTANT: Check "Add python.exe to PATH"
echo   5. Click "Install Now"
echo   6. Restart your computer
echo.
goto :end

:found
echo Found Python:
%PYTHON% --version
echo.
echo Installing/checking required packages...
%PYTHON% -m pip install numpy scipy matplotlib PyQt6 --quiet 2>nul
if %errorlevel% neq 0 (
    echo.
    echo Note: pip install had issues. Trying with --user flag...
    %PYTHON% -m pip install numpy scipy matplotlib PyQt6 --user --quiet 2>nul
)

:: Optional: build Rust extension if Rust is available
where cargo >nul 2>nul
if %errorlevel%==0 (
    echo.
    echo Rust found -- building native accelerator...
    %PYTHON% -m pip install maturin --quiet 2>nul
    cd /d "%~dp0rust_core"
    maturin develop --release --quiet 2>nul
    cd /d "%~dp0"
    if %errorlevel%==0 (
        echo Native accelerator built successfully.
    ) else (
        echo Note: Rust build failed, using Python fallback.
    )
) else (
    echo Note: Rust not found, using Python fallback (still fast).
)

echo.
echo Launching Movement Optimizer...
echo.
cd /d "%~dp0"
set PYTHONPATH=%~dp0src;%PYTHONPATH%
%PYTHON% -m movement_optimizer

:end
echo.
pause
