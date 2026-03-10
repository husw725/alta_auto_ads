#!/bin/bash
echo "🚀 Starting Auto Meta ADS..."

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt > /dev/null 2>&1

# --- 注入环境变量逻辑 ---
if [ -f ".env" ]; then
    echo "🔑 Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
fi

# 如果 .env 中没有设置端口，默认使用 8501
PORT=${STREAMLIT_SERVER_PORT:-8501}

echo "✨ Launching Streamlit on port $PORT..."
streamlit run app.py --server.port $PORT
