@echo off
title NMD Transformer Analysis Dashboard
echo ========================================================
echo Starting NMD Transformer Analysis Dashboard...
echo ========================================================
set PYTHON_EXE=C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe

if not exist "%PYTHON_EXE%" (
    echo Python 3.12 was not found at %PYTHON_EXE%
    echo Falling back to system python...
    python -m streamlit run app.py
) else (
    "%PYTHON_EXE%" -m streamlit run app.py
)
pause

