#!/bin/zsh

# 1. Check if --clean was passed as an argument to this script
CLEAN_ARG=""
if [[ "$*" == *"--clean"* ]]; then
    CLEAN_ARG="--clean"
fi

source .venv/bin/activate

# 2. Run PyInstaller with the optional clean flag
pyinstaller $CLEAN_ARG --onedir --windowed --icon=icon.icns --noconfirm main.py

echo "---"
echo "Build complete. Copy to /Applications folder? (y/n)"
read answer

if [[ $answer == "y" ]]; then
    # Remove the old version
    rm -rf /Applications/ch2anki.app
    
    # Use ditto instead of cp -r
    # -V gives you a status line, though you can omit it
    ditto dist/main.app /Applications/ch2anki.app
    
    echo "Successfully copied to /Applications/ch2anki.app using ditto"
else
    echo "Build kept in ./dist folder."
fi