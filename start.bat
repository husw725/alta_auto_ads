@echo off
echo 🚀 Starting Auto Meta ADS...

if not exist ".venv" (
    echo 📦 Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate
pip install -r requirements.txt > /dev/null 2>&1

:: --- 注入环境变量逻辑 (Windows版) ---
if exist ".env" (
    echo 🔑 Loading environment variables from .env...
    for /f "tokens=*" %%i in ('type .env ^| findstr /v "^#"') do set %%i
)

:: 如果没有设置端口，默认使用 8501
if "%STREAMLIT_SERVER_PORT%"=="" set STREAMLIT_SERVER_PORT=8501

echo ✨ Launching Streamlit on port %STREAMLIT_SERVER_PORT%...
streamlit run app.py --server.port %STREAMLIT_SERVER_PORT%
