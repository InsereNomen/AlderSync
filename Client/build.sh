#!/bin/bash
# ============================================================================
# AlderSync Client - Mac/Linux Build Script
#
# This script builds the AlderSync client into a standalone executable
# using PyInstaller, then packages it into a distributable ZIP file.
#
# Usage:
#     ./build.sh
#
# Output:
#     dist/aldersync-mac.zip (macOS) or dist/aldersync-linux.zip (Linux)
# ============================================================================

echo "======================================================================"
echo "AlderSync Client - Mac/Linux Build Script"
echo "======================================================================"
echo ""

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "[WARNING] Virtual environment not detected."
    echo "Please activate your virtual environment before building."
    echo ""
    echo "Run: source venv/bin/activate"
    echo ""
    exit 1
fi

echo "[1/5] Checking PyInstaller installation..."
echo ""

# Check if PyInstaller is installed
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "PyInstaller not found. Installing..."
    pip install pyinstaller
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to install PyInstaller"
        exit 1
    fi
else
    echo "[OK] PyInstaller is installed"
fi

echo ""
echo "[2/5] Cleaning previous build artifacts..."
echo ""

# Clean previous build artifacts
rm -rf build dist
echo "[OK] Cleaned previous builds"

echo ""
echo "[3/5] Building executable with PyInstaller..."
echo ""

# Build executable
pyinstaller aldersync.spec

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Build failed"
    exit 1
fi

echo ""
echo "[OK] Build complete"
echo ""
echo "[4/5] Verifying executable..."
echo ""

# Detect platform
if [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="mac"
    EXPECTED_OUTPUT="dist/AlderSync.app"
else
    PLATFORM="linux"
    EXPECTED_OUTPUT="dist/aldersync"
fi

if [ ! -e "$EXPECTED_OUTPUT" ]; then
    echo "[ERROR] Executable not found at $EXPECTED_OUTPUT"
    exit 1
fi

echo "[OK] Executable created: $EXPECTED_OUTPUT"
echo ""
echo "[5/5] Creating distribution package..."
echo ""

# Check if README exists
if [ ! -f "README_CLIENT.md" ]; then
    echo "[WARNING] README_CLIENT.md not found - package will not include README"
fi

# Create distribution package
cd dist

if [[ "$PLATFORM" == "mac" ]]; then
    # Mac: Zip the .app bundle
    if [ -f "../README_CLIENT.md" ]; then
        zip -r aldersync-mac.zip AlderSync.app ../README_CLIENT.md
    else
        zip -r aldersync-mac.zip AlderSync.app
    fi
    PACKAGE="aldersync-mac.zip"
else
    # Linux: Zip the executable
    if [ -f "../README_CLIENT.md" ]; then
        zip aldersync-linux.zip aldersync ../README_CLIENT.md
    else
        zip aldersync-linux.zip aldersync
    fi
    PACKAGE="aldersync-linux.zip"
fi

cd ..

echo "[OK] Distribution package created: dist/$PACKAGE"
echo ""
echo "======================================================================"
echo "Build Complete!"
echo "======================================================================"
echo ""
echo "Output:"
echo "  - Executable: $EXPECTED_OUTPUT"
echo "  - Package:    dist/$PACKAGE"
echo ""
echo "File sizes:"
du -h "$EXPECTED_OUTPUT"
du -h "dist/$PACKAGE"
echo ""
echo "======================================================================"
echo ""
