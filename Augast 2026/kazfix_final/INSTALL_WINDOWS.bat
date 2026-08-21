@echo off
setlocal
echo Installing a compatible geemap stack for this application...
python -m pip install --upgrade pip
python -m pip install --force-reinstall "geemap==0.36.6" "python-box>=7.0,<8.0"
python -m pip install -r requirements.txt
echo.
echo Installation complete.
echo Run: streamlit run app.py
pause
