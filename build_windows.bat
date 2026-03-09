@echo off
echo Building Suno Backup for Windows...

:: Ensure dependencies are installed
pip install -r requirements.txt

:: Build the executable
pyinstaller --noconsole --name "Suno Backup" --icon="icon.png" --add-data "ui;ui" --add-data "config.py;." --add-data "vault.py;." --add-data "suno_backup.py;." --add-data "scanner.py;." gui_qt.py

echo.
echo Build Complete! Check the "dist" folder for the executable.
pause