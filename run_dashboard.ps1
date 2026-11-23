# NMD Transformer Analysis Dashboard PowerShell Launcher
$pythonPath = "C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe"

if (Test-Path $pythonPath) {
    & $pythonPath -m streamlit run app.py
} else {
    python -m streamlit run app.py
}

