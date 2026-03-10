import streamlit as st
from core.video_selector import AutoMetaADS
from core.campaign_manager import CampaignManager
import os
import pandas as pd
import json
import re
from datetime import datetime

# 页面配置
st.set_page_config(page_title="Auto Meta ADS | 智能对话版", page_icon="🤖", layout="wide")

# 1. 状态初始化
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'last_candidates' not in st.session_state: st.session_state.last_candidates = None
if 'campaign_list' not in st.session_state: st.session_state.campaign_list = []

# 2. 核心模块初始化
def get_ads_module(): return AutoMetaADS()
def get_campaign_manager(): return CampaignManager()

ads_module = get_ads_module()
campaign_manager = get_campaign_manager()

def load_config():
    config_path = 'config/config.json'
    if not os.path.exists('config'): os.makedirs('config')
    default_template = {
        "default": {"country": "US", "daily_budget": 50, "optimization_goal": "APP_INSTALLS"},
        "strategy": {"CPI_THRESHOLD": 2.0, "ROI_THRESHOLD": 0.5, "HIGH_SPEND_LIMIT": 200.0, "ADJUST_LIMIT_VALUE": 100.0},
        "report": {"enabled": True, "send_time": "10:00", "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=c0a2c5dbbabbae8af4f9dbcc7d7877e403fe2d2b1737acdce0f7719520d00671", "last_sent": ""}
    }
    if not os.path.exists(config_path):
        with open(config_path, 'w') as f: json.dump(default_template, f, indent=2)
        return default_template
    with open(config_path, 'r') as f: return json.load(f)

# 4. 侧边栏
with st.sidebar:
    st.title("🚀 Meta ADS")
    page = st.radio("功能模式", ["💬 AI 投流助手", "📊 数据看板", "⚙️ 系统设置"], index=0)

# 5. 主区域内容
if page == "💬 AI 投流助手":
    st.title("💬 AI 投流助手")
    
    # 渲染历史记录
    for i, chat in enumerate(st.session_state.chat_history):
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
            if chat.get("ad_result"):
                res = chat["ad_result"]
                with st.form(f"f_{i}"):
                    st.write(f"确认投流: **{res.get('drama')}**")
                    if st.form_submit_button("🚀 启动并激活 Campaign"):
                        with st.spinner("执行中..."):
                            # 从素材详情中提取封面图
                            thumb_url = res.get('video_detail', {}).get('cover_url')
                            c_res = campaign_manager.create_campaign(res['drama'], res['video_link'], thumb_url)
                        if c_res.get('status') == 'success': st.success("✅ 投放已激活！")
                        else: st.error(f"❌ 失败: {c_res.get('error')}")

    # 输入逻辑
    if prompt := st.chat_input("输入剧名或编号..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        # --- 核心：记忆与选择逻辑 ---
        resolved_drama_name = prompt
        is_selection = False
        
        # 检查是否是数字选择 (1, 2, 第一个, 选1 等)
        digit_match = re.search(r'(\d+)', prompt)
        if digit_match and st.session_state.last_candidates:
            idx = int(digit_match.group(1)) - 1
            if 0 <= idx < len(st.session_state.last_candidates):
                resolved_drama_name = st.session_state.last_candidates[idx]['name']
                is_selection = True
        
        # 搜索逻辑
        with st.spinner("🔍 处理中..." if is_selection else "🔍 检索素材..."):
            # 如果是选择，直接传剧名给处理器
            success, result = ads_module.process_request(resolved_drama_name, enable_campaign=False)
        
        with st.chat_message("assistant"):
            if success:
                st.session_state.last_candidates = None # 清除记忆
                response = f"### ✅ 找到素材：{result['drama']}\n请确认并启动投放。"
                st.markdown(response)
                st.session_state.chat_history.append({"role": "assistant", "content": response, "ad_result": result})
            elif isinstance(result, dict) and result.get('error_type') == 'multiple_dramas':
                st.session_state.last_candidates = result['candidates'] # 保存名单
                response = result['message']
                st.markdown(response)
                st.session_state.chat_history.append({"role": "assistant", "content": response})
            else:
                response = f"❌ {result}"
                st.error(response)
                st.session_state.chat_history.append({"role": "assistant", "content": response})
        st.rerun()

elif page == "📊 数据看板":
    st.title("📊 广告效果数据中心")
    if st.button("🔄 同步数据"):
        st.session_state.campaign_list = campaign_manager.get_all_campaigns()
    if st.session_state.campaign_list:
        st.dataframe(pd.DataFrame(st.session_state.campaign_list))

elif page == "⚙️ 系统设置":
    st.title("⚙️ 系统设置")
    st.write("配置功能正常。")

st.markdown("<div style='text-align: center; color: #888; font-size: 12px;'>Auto Meta ADS v1.9.5 | 智能记忆版</div>", unsafe_allow_html=True)
