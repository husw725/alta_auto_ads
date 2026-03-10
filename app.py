import streamlit as st
from core.video_selector import AutoMetaADS
from core.campaign_manager import CampaignManager
import os
import re
import pandas as pd
import json

# 页面配置
st.set_page_config(
    page_title="Auto Meta ADS 投流系统",
    page_icon="🚀",
    layout="wide"
)

# 1. 状态初始化
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'candidates' not in st.session_state:
    st.session_state.candidates = None
if 'campaign_list' not in st.session_state:
    st.session_state.campaign_list = []
if 'yesterday_insights' not in st.session_state:
    st.session_state.yesterday_insights = {}

# 2. 核心模块初始化
@st.cache_resource
def init_ads_module():
    return AutoMetaADS()

def init_campaign_manager():
    return CampaignManager()

ads_module = init_ads_module()
campaign_manager = init_campaign_manager()

# 3. 辅助函数
def load_config():
    config_path = 'config/config.json'
    config_dir = 'config'
    
    # 自动创建目录
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
        
    # 如果文件不存在，自动初始化默认配置
    if not os.path.exists(config_path):
        default_config = {
            "default": {
                "country": "US",
                "daily_budget": 50,
                "optimization_goal": "MOBILE_APP_INSTALLS"
            },
            "report": {
                "enabled": True,
                "send_time": "10:00",
                "webhook_url": "",
                "last_sent": ""
            }
        }
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
            
    with open(config_path, 'r') as f:
        return json.load(f)

def save_config(config):
    with open('config/config.json', 'w') as f:
        json.dump(config, f, indent=2)

def handle_ads_logic(user_input):
    with st.spinner("🔍 正在查询 XMP 系统..."):
        success, result = ads_module.process_request(user_input, enable_campaign=False)
    if success:
        st.session_state.candidates = None
        output = f"### ✅ 找到视频！\n**📁 剧集**：{result['drama']} | **🗣️ 语言**：{result['language']}  \n**🎬 视频**：{result['video']}  \n**🔗 [点击预览]({result['video_link']})**"
        return output, result
    else:
        if isinstance(result, dict) and result.get('error_type') == 'multiple_dramas':
            st.session_state.candidates = result['candidates']
            drama_list = "\n".join([f"{i+1}. **{c['name']}**" for i, c in enumerate(result['candidates'])])
            msg = f"❓ **找到多个匹配：**\n\n{drama_list}\n\n👉 请直接输入 **数字编号** 选择。"
            return msg, None
        return f"❌ 错误：{result}", None

def process_input(prompt):
    clean_prompt = prompt.strip()
    if st.session_state.candidates and clean_prompt.isdigit():
        idx = int(clean_prompt) - 1
        if 0 <= idx < len(st.session_state.candidates):
            selected_drama = st.session_state.candidates[idx]['name']
            return handle_ads_logic(f"我要投 {selected_drama}")
    return handle_ads_logic(prompt)

# 4. 侧边栏
with st.sidebar:
    st.title("🚀 Meta ADS")
    st.markdown("---")
    page = st.radio("功能模式", ["💬 AI 投流助手", "📊 数据看板", "⚙️ 系统设置"], index=0)
    
    st.divider()
    if st.session_state.candidates:
        if st.button("取消选择"):
            st.session_state.candidates = None
            st.rerun()
    
    st.markdown("### 📋 当前默认配置")
    cfg = load_config().get('default', {})
    st.caption(f"🌍 国家: `{cfg.get('country')}`")
    st.caption(f"💰 预算: `${cfg.get('daily_budget')}`")
    st.caption(f"🎯 优化: `{cfg.get('optimization_goal')}`")

# 5. 主区域内容
if page == "💬 AI 投流助手":
    st.title("💬 AI 投流助手")
    for i, chat in enumerate(st.session_state.chat_history):
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
            if chat.get("ad_result"):
                res = chat["ad_result"]
                with st.form(f"form_{i}"):
                    st.write(f"确认投流: **{res['drama']}** (根据系统预设)")
                    if st.form_submit_button("🚀 启动 Campaign"):
                        with st.spinner("🚀 创建中..."):
                            c_res = campaign_manager.create_campaign(res['drama'], res['video_link'])
                        if c_res['status'] == 'success': st.success("✅ 投流成功！")
                        else: st.error(f"❌ 失败: {c_res['error']}")

    if prompt := st.chat_input("输入剧名或数字编号..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        response, ad_result = process_input(prompt)
        with st.chat_message("assistant"):
            st.markdown(response)
            if ad_result:
                with st.form("form_new"):
                    if st.form_submit_button("🚀 启动 Campaign"):
                        with st.spinner("🚀 创建中..."):
                            c_res = campaign_manager.create_campaign(ad_result['drama'], ad_result['video_link'])
                        if c_res['status'] == 'success': st.success("✅ 投流成功！")
                        else: st.error(f"❌ 失败: {c_res['error']}")
        st.session_state.chat_history.append({"role": "assistant", "content": response, "ad_result": ad_result})
        st.rerun()

elif page == "📊 数据看板":
    st.title("📊 广告数据看板")
    col1, col2 = st.columns([3, 1])
    with col1: search_query = st.text_input("🔍 搜索广告", placeholder="输入剧名...")
    with col2:
        st.write("")
        if st.button("🔄 刷新数据", use_container_width=True):
            with st.spinner("同步中..."):
                st.session_state.campaign_list = campaign_manager.get_all_campaigns()
                st.session_state.yesterday_insights = campaign_manager.get_yesterday_insights()

    if st.session_state.campaign_list:
        df = pd.DataFrame(st.session_state.campaign_list)
        if search_query: df = df[df['name'].str.contains(search_query, case=False)]
        
        # 汇总
        insights = st.session_state.yesterday_insights
        total_spend = sum(ins['spend'] for ins in insights.values())
        total_conv = sum(ins['conversions'] for ins in insights.values())
        m1, m2, m3 = st.columns(3)
        m1.metric("昨日消耗", f"${total_spend:.2f}")
        m2.metric("昨日转化", total_conv)
        m3.metric("平均 CPI", f"${(total_spend/total_conv if total_conv>0 else 0):.2f}")

        st.divider()
        for index, row in df.iterrows():
            c1, c2, c3, c4 = st.columns([4, 1, 1, 1])
            cid, ins = row['id'], insights.get(row['id'], {'spend':0, 'conversions':0, 'cpi':0})
            with c1:
                st.markdown(f"**{row['name']}**")
                st.caption(f"昨日: **${ins['spend']:.2f}** ({ins['conversions']} 转化)")
            with c2:
                status = row['effective_status']
                st.markdown(f":{('green' if status=='ACTIVE' else 'orange' if status=='PAUSED' else 'grey')}[{status}]")
            with c3:
                if st.button("🟢 激活", key=f"act_{cid}", use_container_width=True, disabled=(status=="ACTIVE")):
                    if campaign_manager.update_campaign_status(cid, "ACTIVE"): st.rerun()
            with c4:
                if st.button("🟡 暂停", key=f"pas_{cid}", use_container_width=True, disabled=(status=="PAUSED")):
                    if campaign_manager.update_campaign_status(cid, "PAUSED"): st.rerun()
            st.markdown("---")

elif page == "⚙️ 系统设置":
    st.title("⚙️ 系统与策略配置")
    config = load_config()
    
    with st.expander("🚀 投流默认策略设置", expanded=True):
        st.markdown("#### 核心参数")
        d_country = st.selectbox("默认投放国家", ["US", "UK", "CA", "AU", "DE", "FR", "JP", "KR"], 
                                 index=["US", "UK", "CA", "AU", "DE", "FR", "JP", "KR"].index(config['default'].get('country', 'US')))
        d_budget = st.number_input("默认每日预算 ($)", value=config['default'].get('daily_budget', 50), min_value=10)
        d_goal = st.selectbox("默认优化目标", ["MOBILE_APP_INSTALLS", "CONTENT_VIEW"], 
                              index=0 if config['default'].get('optimization_goal') == "MOBILE_APP_INSTALLS" else 1)
        
        if st.button("💾 保存策略配置", type="primary"):
            config['default']['country'] = d_country
            config['default']['daily_budget'] = d_budget
            config['default']['optimization_goal'] = d_goal
            save_config(config)
            st.success("✅ 策略已更新！后续投流将按此配置执行。")

    with st.expander("📅 定时日报推送设置", expanded=False):
        st.markdown("#### 推送策略")
        enabled = st.toggle("开启推送", value=config['report'].get('enabled', True))
        webhook = st.text_input("Webhook", value=config['report'].get('webhook_url', ''))
        send_time = st.text_input("时间 (HH:mm)", value=config['report'].get('send_time', '10:00'))
        if st.button("💾 保存日报配置"):
            config['report']['enabled'] = enabled
            config['report']['webhook_url'] = webhook
            config['report']['send_time'] = send_time
            save_config(config)
            st.success("✅ 报表配置已保存。")

st.markdown("<div style='text-align: center; color: #888; font-size: 12px;'>Auto Meta ADS v1.6</div>", unsafe_allow_html=True)
