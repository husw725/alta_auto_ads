import streamlit as st
from core.video_selector import AutoMetaADS
from core.campaign_manager import CampaignManager
import os
import json
import traceback

# 页面配置
st.set_page_config(page_title="Auto Meta ADS | 调试版", page_icon="🕵️", layout="wide")

# 1. 状态初始化
if 'chat_history' not in st.session_state: st.session_state.chat_history = []

# 2. 核心模块初始化 (不再使用 cache_resource，确保代码改动立即生效)
def get_ads_module(): return AutoMetaADS()
def get_campaign_manager(): return CampaignManager()

ads_module = get_ads_module()
campaign_manager = get_campaign_manager()

# 3. 主区域内容
st.title("💬 AI 投流助手 (深度诊断版)")

# 渲染历史记录
for i, chat in enumerate(st.session_state.chat_history):
    with st.chat_message(chat["role"]):
        st.markdown(chat["content"])
        if chat.get("ad_result"):
            res = chat["ad_result"]
            with st.container(border=True):
                st.write(f"📁 剧集: **{res.get('drama')}**")
                v_url = res.get('video_link', '')
                
                if st.button("🚀 启动 Campaign", key=f"btn_diag_{i}"):
                    with st.status("🚀 联络 Meta 投流引擎...", expanded=True) as status:
                        st.write("### 🛠️ 步骤 1: 检查参数")
                        st.json({"drama": res.get('drama'), "url": v_url})
                        
                        # 执行投流
                        st.write("### 🛰️ 步骤 2: 发送请求...")
                        try:
                            c_res = campaign_manager.create_campaign(res.get('drama'), v_url)
                            
                            if c_res.get('status') == 'success':
                                st.success(f"✅ 创建成功! ID: {c_res.get('campaign_id')}")
                                status.update(label="✅ 任务完成", state="complete")
                            else:
                                st.error("❌ 任务在 API 层面中止")
                                st.markdown("#### 🔍 Meta API 返回的原始错误详情：")
                                st.json(c_res.get('error')) # 强制以 JSON 格式展示错误
                                if c_res.get('traceback'):
                                    st.write("🐍 代码堆栈:")
                                    st.code(c_res.get('traceback'))
                                status.update(label="❌ 任务失败", state="error")
                        except Exception as e:
                            st.error(f"⚠️ UI 层级捕获到未知异常: {str(e)}")
                            st.code(traceback.format_exc())
                            status.update(label="⚠️ 崩溃", state="error")

# 输入框逻辑
if prompt := st.chat_input("输入剧名..."):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)
    with st.spinner("🔍 正在 XMP 中搜寻素材..."):
        success, result = ads_module.process_request(prompt, enable_campaign=False)
    
    if success:
        resp_text = f"### ✅ 找到素材：{result['drama']}\n\n请点击下方按钮启动投放。"
        st.session_state.chat_history.append({"role": "assistant", "content": resp_text, "ad_result": result})
    else:
        st.error(f"❌ 检索失败: {result}")
    st.rerun()

st.markdown("<div style='text-align: center; color: #888; font-size: 12px;'>Auto Meta ADS v1.8.6 | 深度诊断版</div>", unsafe_allow_html=True)
