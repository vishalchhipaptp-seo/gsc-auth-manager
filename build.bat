@echo off
echo Building GSC Auth Manager...
pip install -r requirements.txt
python -m patchright install chromium
pyinstaller --onefile --windowed --name "GSC Auth Manager" --add-data "templates;templates" --add-data "static;static" app.py
echo.
echo Done! The exe is in: dist\GSC Auth Manager.exe
pause
