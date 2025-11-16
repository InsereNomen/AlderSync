@echo off
REM ============================================================================
REM AlderSync Client - Windows Build Script
REM
REM This script builds the AlderSync client into a standalone executable
REM using PyInstaller, then packages it into a distributable ZIP file.
REM
REM Usage:
REM     build.bat
REM
REM Output:
REM     dist/aldersync-windows.zip - Contains executable and README
REM ============================================================================

echo ======================================================================
echo AlderSync Client - Windows Build Script
echo ======================================================================
echo.

REM Check if virtual environment is activated
if not defined VIRTUAL_ENV (
    echo [WARNING] Virtual environment not detected.
    echo Please activate your virtual environment before building.
    echo.
    echo Run: venv\Scripts\activate
    echo.
    pause
    exit /b 1
)

echo [1/5] Checking PyInstaller installation...
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller
        pause
        exit /b 1
    )
) else (
    echo [OK] PyInstaller is installed
)

echo.
echo [2/5] Cleaning previous build artifacts...
echo.

REM Clean previous build artifacts
if exist "build" rd /s /q "build"
if exist "dist" rd /s /q "dist"

echo [OK] Cleaned previous builds
echo.
echo [3/5] Building executable with PyInstaller...
echo.

REM Build executable
pyinstaller aldersync.spec

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo.
echo [OK] Build complete
echo.
echo [4/5] Verifying executable...
echo.

if not exist "dist\aldersync.exe" (
    echo [ERROR] Executable not found at dist\aldersync.exe
    pause
    exit /b 1
)

echo [OK] Executable created: dist\aldersync.exe
echo.
echo [5/5] Creating distribution package...
echo.

REM Check if README exists
if not exist "README_CLIENT.md" (
    echo [WARNING] README_CLIENT.md not found - package will not include README
)

REM Create distribution package
cd dist

REM Use PowerShell to create zip file
powershell -Command "Compress-Archive -Path aldersync.exe -DestinationPath aldersync-windows.zip -Force"

if exist "README_CLIENT.md" (
    powershell -Command "Compress-Archive -Path aldersync.exe, ..\README_CLIENT.md -DestinationPath aldersync-windows.zip -Force"
)

cd ..

echo [OK] Distribution package created: dist\aldersync-windows.zip
echo.
echo ======================================================================
echo Build Complete!
echo ======================================================================
echo.
echo Output:
echo   - Executable: dist\aldersync.exe
echo   - Package:    dist\aldersync-windows.zip
echo.
echo File size:
dir "dist\aldersync.exe" | find "aldersync.exe"
dir "dist\aldersync-windows.zip" | find "aldersync-windows.zip"
echo.
echo ======================================================================
echo.
pause
