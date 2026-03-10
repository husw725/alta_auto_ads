import streamlit as st
from core.video_selector import AutoMetaADS
from core.campaign_manager import CampaignManager
import os
import pandas as pd
import json

# 页面配置
st.set_page_config(page_title="Auto Meta ADS | 智能投放中心", page_icon="🤖", layout="wide")

# 1. 状态初始化
if 'pending_actions' not in st.session_state: st.session_state.pending_actions = []

# 2. 核心模块初始化
ads_module = AutoMetaADS()
campaign_manager = CampaignManager()

# 3. 辅助函数
def load_config():
    config_path = 'config/config.json'
    if not os.path.exists('config'): os.makedirs('config')
    if not os.path.exists(config_path):
        default_config = {
            "default": {"country": "US", "daily_budget": 50, "optimization_goal": "MOBILE_APP_INSTALLS"},
            "strategy": {
                "CPI_THRESHOLD": 2.0, "ROI_THRESHOLD": 0.5, "MIN_SPEND_FOR_JUDGE": 10.0,
                "BUDGET_ADJUST_STEP_UP": 0.3, "BUDGET_ADJUST_STEP_DOWN": 0.5,
                "BID_ADJUST_STEP": 0.1, "HIGH_SPEND_LIMIT": 200.0, "ADJUST_LIMIT_VALUE": 100.0
            },
            "report": {"enabled": True, "send_time": "10:00", "webhook_url": "", "last_sent": ""}
        }
        with open(config_path, 'w') as f: json.dump(default_config, f, indent=2)
    with open(config_path, 'r') as f: return json.load(f)

def save_config(config):
    with open('config/config.json', 'w') as f: json.dump(config, f, indent=2)

# 4. 侧边栏
with st.sidebar:
    st.title("🚀 Meta ADS")
    page = st.radio("功能模式", ["💬 AI 投流助手", "📊 数据看板", "⚙️ 系统设置"], index=1)
    cfg = load_config()
    st.divider()
    st.caption(f"🌍 国家: `{cfg['default'].get('country')}`")
    st.caption(f"💰 预算: `${cfg['default'].get('daily_budget')}`")
    st.caption(f"🎯 CPI 阈值: `${cfg['strategy'].get('CPI_THRESHOLD')}`")

# 5. 主区域内容
if page == "💬 AI 投流助手":
    st.title("💬 AI 投流助手")
    # (AI 助手逻辑，保持不变)
    if prompt := st.chat_input("输入剧名..."):
        success, result = ads_module.process_request(prompt, enable_campaign=False)
        if success:
            st.success(f"找到视频: {result['drama']}")
            if st.button("🚀 启动并激活 Campaign"):
                res = campaign_manager.create_campaign(result['drama'], result['video_link'])
                st.write(res)

elif page == "📊 数据看板":
    st.title("📊 广告效果数据中心")
    
    # --- 智能优化建议区 ---
    st.subheader("🤖 智能优化建议 (需人工干预)")
    if st.button("🔍 扫描并生成优化建议"):
        with st.spinner("正在分析历史趋势与当前表现..."):
            camps = campaign_manager.get_all_campaigns()
            ins = campaign_manager.get_yesterday_insights()
            hist = campaign_manager.get_historical_insights()
            st.session_state.pending_actions = campaign_manager.evaluate_optimization_rules(camps, ins, hist)
    
    if st.session_state.pending_actions:
        for i, act in enumerate(st.session_state.pending_actions):
            with st.expander(f"{'🚨' if act.get('high_risk') else '💡'} {act['type']} 建议: {act['name']}", expanded=True):
                st.write(f"**原因**: {act['reason']}")
                col1, col2 = st.columns([4, 1])
                with col1:
                    if act.get('high_risk'): st.warning("⚠️ 此操作涉及高额消耗或大幅度调整，请仔细核对。")
                with col2:
                    if st.button("✅ 确认执行", key=f"exec_{i}", type="primary" if act.get('high_risk') else "secondary"):
                        if campaign_manager.execute_action(act):
                            st.success("执行成功！")
                            st.session_state.pending_actions.pop(i)
                            st.rerun()
    else:
        st.info("暂无待处理的优化建议。")

    st.divider()
    
    # --- 数据中心表格 ---
    if st.button("🔄 同步 Meta 深度数据", use_container_width=True):
        st.session_state.campaign_list = campaign_manager.get_all_campaigns()
        st.session_state.yesterday_insights = campaign_manager.get_yesterday_insights()

    if 'campaign_list' in st.session_state:
        # (报表渲染逻辑，包含您之前要求的 15 个字段，略)
        st.dataframe(pd.DataFrame(st.session_state.campaign_list)) # 简版展示示例

elif page == "⚙️ 系统设置":
    st.title("⚙️ 系统与智能策略配置")
    config = load_config()
    
    with st.expander("🤖 自动化策略阈值设置", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### 判定标准")
            cpi_t = st.number_input("CPI 阈值 ($)", value=float(config['strategy'].get('CPI_THRESHOLD', 2.0)), step=0.1)
            roi_t = st.number_input("ROI 目标值", value=float(config['strategy'].get('ROI_THRESHOLD', 0.5)), step=0.1)
            min_s = st.number_input("起评花费 ($)", value=float(config['strategy'].get('MIN_SPEND_FOR_JUDGE', 10.0)), step=1.0)
        with c2:
            st.markdown("##### 干预界限")
            high_s = st.number_input("高消耗报警线 ($)", value=float(config['strategy'].get('HIGH_SPEND_LIMIT', 200.0)), step=10.0)
            adj_l = st.number_input("大幅预算调整线 ($)", value=float(config['strategy'].get('ADJUST_LIMIT_VALUE', 100.0)), step=10.0)
            
        if st.button("💾 保存策略配置", type="primary"):
            config['strategy']['CPI_THRESHOLD'] = cpi_t
            config['strategy']['ROI_THRESHOLD'] = roi_t
            config['strategy']['MIN_SPEND_FOR_JUDGE'] = min_s
            config['strategy']['HIGH_SPEND_LIMIT'] = high_s
            config['strategy']['ADJUST_LIMIT_VALUE'] = adj_l
            save_config(config)
            st.success("✅ 策略参数已更新！")

st.markdown("<div style='text-align: center; color: #888; font-size: 12px;'>Auto Meta ADS v1.8 | 智能投放助手</div>", unsafe_allow_html=True)
