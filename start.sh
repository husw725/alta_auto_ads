#!/bin/bash
echo "🚀 Starting Auto Meta ADS..."

# 1. 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# 2. 激活并同步依赖
source .venv/bin/activate
echo "🔧 Checking dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 3. 检查 .env
if [ ! -f ".env" ]; then
    echo "⚠️ .env file not found, creating from template..."
    cp .env.example .env
    echo "💡 Please edit .env with your credentials."
fi

# 4. 启动系统
echo "✨ Launching Streamlit..."
streamlit run app.py
