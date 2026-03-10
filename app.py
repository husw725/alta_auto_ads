import streamlit as st
from core.video_selector import AutoMetaADS
from core.campaign_manager import CampaignManager
import os
import pandas as pd
import json
import traceback

# 页面配置
st.set_page_config(page_title="Auto Meta ADS | 终极调试版", page_icon="🕵️", layout="wide")

# 1. 状态初始化
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'campaign_list' not in st.session_state: st.session_state.campaign_list = []

# 2. 核心模块初始化
@st.cache_resource
def get_ads_module(): return AutoMetaADS()
@st.cache_resource
def get_campaign_manager(): return CampaignManager()

ads_module = get_ads_module()
campaign_manager = get_campaign_manager()

# 3. 主区域内容
st.title("💬 AI 投流助手 (终极日志版)")
st.info("💡 提示：此版本会实时显示发送给 Meta 的每一个 Payload，帮助排查 'id' 缺失问题。")

# 渲染历史记录
for i, chat in enumerate(st.session_state.chat_history):
    with st.chat_message(chat["role"]):
        st.markdown(chat["content"])
        if chat.get("ad_result"):
            res = chat["ad_result"]
            with st.container(border=True):
                st.write(f"📁 剧集: **{res.get('drama')}**")
                v_url = res.get('video_link', '')
                st.write(f"🔗 素材: `{v_url[:60]}...`")
                
                # 核心：确保按钮点击时参数是干净的
                if st.button("🚀 启动 Campaign", key=f"btn_v2_{i}"):
                    with st.status("🚀 投流引擎启动中...", expanded=True) as status:
                        st.write("### 🛠️ 步骤 1: 参数校验")
                        st.json({"drama": res.get('drama'), "url": v_url})
                        
                        # 执行投流
                        st.write("### 🛰️ 步骤 2: 联络 Meta API...")
                        c_res = campaign_manager.create_campaign(res.get('drama'), v_url)
                        
                        if c_res.get('status') == 'success':
                            st.success(f"✅ 创建成功! ID: {c_res.get('campaign_id')}")
                            status.update(label="✅ 任务圆满完成", state="complete")
                        else:
                            st.error("❌ 任务在 API 层面中断")
                            st.markdown("#### 🔍 详细错误详情")
                            # 强制显示错误原因
                            err_msg = c_res.get('error', 'Unknown Error')
                            st.code(err_msg, language="text")
                            
                            # 如果有 traceback，说明是代码崩溃
                            if c_res.get('traceback'):
                                st.write("🐍 Python 调用栈:")
                                st.code(c_res.get('traceback'), language="python")
                            
                            status.update(label="❌ 任务中止", state="error")

# 输入框逻辑
if prompt := st.chat_input("输入剧名，开始诊断投流..."):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)
    with st.spinner("🔍 正在 XMP 中搜寻最优素材..."):
        success, result = ads_module.process_request(prompt, enable_campaign=False)
    
    if success:
        resp_text = f"### ✅ 命中剧集：{result['drama']}\n\n已为您匹配最佳视频素材，请点击下方确认启动。"
        st.session_state.chat_history.append({"role": "assistant", "content": resp_text, "ad_result": result})
    else:
        st.error(f"❌ 素材检索失败: {result}")
    st.rerun()

st.divider()
st.markdown("<div style='text-align: center; color: #888; font-size: 12px;'>Auto Meta ADS v1.8.5 | 调试墙模式</div>", unsafe_allow_html=True)
