@echo off
echo 🚀 Starting Auto Meta ADS...

:: 1. 检查虚拟环境
if not exist ".venv" (
    echo 📦 Creating virtual environment...
    python -m venv .venv
)

:: 2. 激活并同步依赖
call .venv\Scripts\activate
echo 🔧 Checking dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

:: 3. 检查 .env
if not exist ".env" (
    echo ⚠️ .env file not found, creating from template...
    copy .env.example .env
    echo 💡 Please edit .env with your credentials.
)

:: 4. 启动系统
echo ✨ Launching Streamlit...
streamlit run app.py
