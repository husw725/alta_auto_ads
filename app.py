import streamlit as st
from core.video_selector import AutoMetaADS
from core.campaign_manager import CampaignManager
import os
import pandas as pd
import json
import pytz
from datetime import datetime

# 页面配置
st.set_page_config(page_title="Auto Meta ADS | 调试版", page_icon="🤖", layout="wide")

# 1. 状态初始化
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'campaign_list' not in st.session_state: st.session_state.campaign_list = []
if 'yesterday_insights' not in st.session_state: st.session_state.yesterday_insights = {}

# 2. 核心模块
@st.cache_resource
def get_ads_module(): return AutoMetaADS()
@st.cache_resource
def get_campaign_manager(): return CampaignManager()

ads_module = get_ads_module()
campaign_manager = get_campaign_manager()

def load_config():
    config_path = 'config/config.json'
    if not os.path.exists('config'): os.makedirs('config')
    default_template = {
        "default": {"country": "US", "daily_budget": 50, "optimization_goal": "MOBILE_APP_INSTALLS"},
        "strategy": {"CPI_THRESHOLD": 2.0, "ROI_THRESHOLD": 0.5, "HIGH_SPEND_LIMIT": 200.0, "ADJUST_LIMIT_VALUE": 100.0},
        "report": {"enabled": True, "send_time": "10:00", "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=c0a2c5dbbabbae8af4f9dbcc7d7877e403fe2d2b1737acdce0f7719520d00671", "last_sent": ""}
    }
    if not os.path.exists(config_path):
        with open(config_path, 'w') as f: json.dump(default_template, f, indent=2)
        return default_template
    with open(config_path, 'r') as f: user_cfg = json.load(f)
    return user_cfg

# 4. 侧边栏
with st.sidebar:
    st.title("🚀 Meta ADS")
    page = st.radio("功能模式", ["💬 AI 投流助手", "📊 数据看板", "⚙️ 系统设置"], index=0)
    cfg = load_config()

# 5. 主区域内容
if page == "💬 AI 投流助手":
    st.title("💬 AI 投流助手 (调试版)")
    
    for i, chat in enumerate(st.session_state.chat_history):
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
            if chat.get("ad_result"):
                res = chat["ad_result"]
                with st.container(border=True):
                    st.write(f"📁 待投剧集: **{res['drama']}**")
                    st.write(f"🔗 视频链接: `{res['video_link'][:60]}...`")
                    if st.button("🚀 确认并启动 Campaign", key=f"btn_{i}"):
                        log_container = st.empty()
                        with st.status("🚀 正在执行投流任务...", expanded=True) as status:
                            st.write("1. 正在初始化 Meta 会话...")
                            c_res = campaign_manager.create_campaign(res['drama'], res['video_link'])
                            
                            if c_res['status'] == 'success':
                                st.success(f"✅ 创建成功！Campaign ID: {c_res['campaign_id']}")
                                status.update(label="✅ 投流任务完成", state="complete", expanded=False)
                            else:
                                st.error("❌ 投流任务失败")
                                st.markdown("### 🔍 错误诊断报告")
                                st.code(f"错误类型: {c_res.get('error')}", language="text")
                                if 'traceback' in str(c_res):
                                    st.write("🐍 Python 堆栈追踪:")
                                    st.code(c_res.get('error'), language="python")
                                status.update(label="❌ 任务中止", state="error")
    
    if prompt := st.chat_input("输入剧名..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.spinner("🔍 检索 XMP 素材..."):
            success, result = ads_module.process_request(prompt, enable_campaign=False)
        if success:
            response = f"### ✅ 找到素材！\n**剧集**：{result['drama']} | [点击预览]({result['video_link']})"
            st.session_state.chat_history.append({"role": "assistant", "content": response, "ad_result": result})
        else:
            st.error(f"❌ 未找到素材: {result}")
        st.rerun()

elif page == "📊 数据看板":
    st.title("📊 广告效果数据中心")
    if st.button("🔄 同步 Meta 数据"):
        st.session_state.campaign_list = campaign_manager.get_all_campaigns()
        st.session_state.yesterday_insights = campaign_manager.get_yesterday_insights()
    
    if st.session_state.campaign_list:
        st.dataframe(pd.DataFrame(st.session_state.campaign_list))

elif page == "⚙️ 系统设置":
    st.title("⚙️ 系统设置")
    st.write("配置管理功能正常。")

st.markdown("<div style='text-align: center; color: #888; font-size: 12px;'>Auto Meta ADS v1.8.4 | 深度诊断版</div>", unsafe_allow_html=True)
