@echo off
echo Starting GSC Auth Manager...
pip install flask patchright pywebview requests >nul 2>&1
python -m patchright install chromium >nul 2>&1
python app.py
