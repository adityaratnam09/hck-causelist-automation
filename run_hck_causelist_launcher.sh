# ==============================================================================
# FILE: run_hck_causelist_launcher.sh
# DESCRIPTION: PyInstaller Workspace Build Utility
# ------------------------------------------------------------------------------
# Handles binary compilation maintenance. It automatically purges stale
# workspace caching artifacts, structural build directories, and dynamic .spec
# layout maps before running PyInstaller to compress and compile the graphical
# user interface module into a clean, standalone Apple Silicon .app package.
# ==============================================================================

#!/bin/bash

# Navigate to the directory where this script is saved
cd "$(dirname "$0")"

echo "========================================================="
echo "INITIALIZING PYINSTALLER COMPILATION"
echo "========================================================="

# Clean up previous build directories to ensure a fresh compilation
echo "Clearing old build artifacts..."
rm -rf build dist HCKCauseListAutomationSetup.spec

echo "Running PyInstaller compilation..."
# Execute your exact target compilation rule
pyinstaller --noconsole --onefile --name="HCKCauseListAutomationSetup" hck_causelist_launcher.py

# Check if compilation succeeded
if [ $? -eq 0 ]; then
    echo "========================================================="
    echo "[SUCCESS] Build completed successfully!"
    echo "Standalone executable located at: dist/HCKCauseListAutomationSetup"
    echo "========================================================="
else
    echo "========================================================="
    echo "[ERROR] PyInstaller encountered an issue during compilation."
    echo "========================================================="
    exit 1
fi