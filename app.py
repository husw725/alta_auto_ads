import streamlit as st
from core.video_selector import AutoMetaADS
from core.campaign_manager import CampaignManager
import os
import pandas as pd
import json
import pytz
import re
from datetime import datetime

# 页面配置
st.set_page_config(page_title="Auto Meta ADS | 智能投放中心", page_icon="🤖", layout="wide")

# 1. 状态初始化
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'campaign_list' not in st.session_state: st.session_state.campaign_list = []
if 'yesterday_insights' not in st.session_state: st.session_state.yesterday_insights = {}
if 'pending_actions' not in st.session_state: st.session_state.pending_actions = []

# 2. 核心模块初始化
def get_ads_module(): return AutoMetaADS()
def get_campaign_manager(): return CampaignManager()

ads_module = get_ads_module()
campaign_manager = get_campaign_manager()

# 3. 辅助函数
def load_config():
    config_path = 'config/config.json'
    if not os.path.exists('config'): os.makedirs('config')
    default_template = {
        "default": {"country": "US", "daily_budget": 50, "optimization_goal": "APP_INSTALLS"},
        "strategy": {
            "CPI_THRESHOLD": 2.0, "ROI_THRESHOLD": 0.5, "MIN_SPEND_FOR_JUDGE": 10.0,
            "BUDGET_ADJUST_STEP_UP": 0.3, "BUDGET_ADJUST_STEP_DOWN": 0.5,
            "BID_ADJUST_STEP": 0.1, "HIGH_SPEND_LIMIT": 200.0, "ADJUST_LIMIT_VALUE": 100.0
        },
        "report": {"enabled": True, "send_time": "10:00", "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=c0a2c5dbbabbae8af4f9dbcc7d7877e403fe2d2b1737acdce0f7719520d00671", "last_sent": ""}
    }
    if not os.path.exists(config_path):
        with open(config_path, 'w') as f: json.dump(default_template, f, indent=2)
        return default_template
    with open(config_path, 'r') as f: user_cfg = json.load(f)
    return user_cfg

def save_config(config):
    with open('config/config.json', 'w') as f: json.dump(config, f, indent=2)

# 4. 侧边栏
with st.sidebar:
    st.title("🚀 Meta ADS")
    page = st.radio("功能模式", ["💬 AI 投流助手", "📊 数据看板", "⚙️ 系统设置"], index=0)
    cfg = load_config()

# 5. 主区域内容
if page == "💬 AI 投流助手":
    st.title("💬 AI 投流助手")
    
    # 渲染历史记录
    for i, chat in enumerate(st.session_state.chat_history):
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
            # 投流确认表单
            if chat.get("ad_result"):
                res = chat["ad_result"]
                with st.form(f"confirm_{i}"):
                    st.write(f"📁 确认投流剧集: **{res.get('drama')}**")
                    st.write(f"🔗 [素材预览]({res.get('video_link')})")
                    if st.form_submit_button("🚀 启动并激活 Campaign"):
                        with st.spinner("正在创建并激活..."):
                            c_res = campaign_manager.create_campaign(res['drama'], res['video_link'])
                        if c_res.get('status') == 'success':
                            st.success(f"✅ 投放已激活！ID: {c_res.get('campaign_id')}")
                        else:
                            st.error(f"❌ 失败: {c_res.get('error')}")

    # 输入框
    if prompt := st.chat_input("输入剧名..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        # 搜索逻辑
        with st.spinner("🔍 检索 XMP 素材..."):
            success, result = ads_module.process_request(prompt, enable_campaign=False)
        
        with st.chat_message("assistant"):
            if success:
                response = f"### ✅ 找到素材：{result['drama']}\n匹配到最佳视频，请确认并启动。"
                st.markdown(response)
                st.session_state.chat_history.append({"role": "assistant", "content": response, "ad_result": result})
            elif isinstance(result, dict) and result.get('error_type') == 'multiple_dramas':
                # 处理多个匹配
                response = result['message']
                st.markdown(response)
                st.session_state.chat_history.append({"role": "assistant", "content": response})
            else:
                response = f"❌ 检索失败: {result}"
                st.error(response)
                st.session_state.chat_history.append({"role": "assistant", "content": response})
        st.rerun()

elif page == "📊 数据看板":
    st.title("📊 广告效果数据中心")
    if st.button("🔄 同步 Meta 深度数据", use_container_width=True):
        st.session_state.campaign_list = campaign_manager.get_all_campaigns()
        st.session_state.yesterday_insights = campaign_manager.get_yesterday_insights()
    
    if st.session_state.campaign_list:
        st.dataframe(pd.DataFrame(st.session_state.campaign_list), use_container_width=True, hide_index=True)

elif page == "⚙️ 系统设置":
    st.title("⚙️ 系统设置")
    st.write("配置管理功能正常。")

st.markdown("<div style='text-align: center; color: #888; font-size: 12px;'>Auto Meta ADS v1.9.4 | 搜索功能修复版</div>", unsafe_allow_html=True)
