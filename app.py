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
if 'last_candidates' not in st.session_state: st.session_state.last_candidates = None
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
            "HIGH_SPEND_LIMIT": 200.0, "ADJUST_LIMIT_VALUE": 100.0
        },
        "report": {"enabled": True, "send_time": "10:00", "webhook_url": "", "last_sent": ""}
    }
    if not os.path.exists(config_path):
        with open(config_path, 'w') as f: json.dump(default_template, f, indent=2)
        return default_template
    with open(config_path, 'r') as f: user_cfg = json.load(f)
    # 自动补齐逻辑
    updated = False
    for k, v in default_template.items():
        if k not in user_cfg: user_cfg[k] = v; updated = True
        elif isinstance(v, dict):
            for sk, sv in v.items():
                if sk not in user_cfg[k]: user_cfg[k][sk] = sv; updated = True
    if updated:
        with open(config_path, 'w') as f: json.dump(user_cfg, f, indent=2)
    return user_cfg

def save_config(config):
    with open('config/config.json', 'w') as f: json.dump(config, f, indent=2)

# 4. 侧边栏
with st.sidebar:
    st.title("🚀 Meta ADS")
    page = st.radio("功能模式", ["💬 AI 投流助手", "📊 数据看板", "⚙️ 系统设置"], index=0)
    cfg = load_config()
    st.divider()
    st.caption(f"🌍 国家: `{cfg['default'].get('country')}` | 💰 预算: `${cfg['default'].get('daily_budget')}`")

# 5. 主区域内容
if page == "💬 AI 投流助手":
    st.title("💬 AI 投流助手")
    for i, chat in enumerate(st.session_state.chat_history):
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
            if chat.get("ad_result"):
                res = chat["ad_result"]
                with st.form(f"f_{i}"):
                    st.write(f"确认投流: **{res.get('drama')}**")
                    if st.form_submit_button("🚀 启动并激活 Campaign"):
                        with st.spinner("执行中..."):
                            thumb_url = res.get('video_detail', {}).get('cover_url')
                            c_res = campaign_manager.create_campaign(res['drama'], res['video_link'], thumb_url)
                        if c_res.get('status') == 'success': st.success(f"✅ 投放已激活！ID: {c_res.get('campaign_id')}")
                        else: st.error(f"❌ 失败: {c_res.get('error')}")

    if prompt := st.chat_input("输入剧名或编号..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        resolved_drama_name = prompt
        if st.session_state.last_candidates:
            digit_match = re.search(r'(\d+)', prompt)
            if digit_match:
                idx = int(digit_match.group(1)) - 1
                if 0 <= idx < len(st.session_state.last_candidates):
                    resolved_drama_name = st.session_state.last_candidates[idx]['name']

        with st.spinner("🔍 处理中..."):
            success, result = ads_module.process_request(resolved_drama_name, enable_campaign=False)
        
        with st.chat_message("assistant"):
            if success:
                st.session_state.last_candidates = None
                response = f"### ✅ 找到素材：{result['drama']}\n请确认并启动投放。"
                st.markdown(response)
                st.session_state.chat_history.append({"role": "assistant", "content": response, "ad_result": result})
            elif isinstance(result, dict) and result.get('error_type') == 'multiple_dramas':
                st.session_state.last_candidates = result['candidates']
                response = result['message']
                st.markdown(response)
                st.session_state.chat_history.append({"role": "assistant", "content": response})
            else:
                st.error(f"❌ {result}"); st.session_state.chat_history.append({"role": "assistant", "content": f"❌ {result}"})
        st.rerun()

elif page == "📊 数据看板":
    st.title("📊 广告效果数据中心")
    
    # 智能优化建议
    st.subheader("🤖 智能优化建议")
    if st.button("🔍 扫描分析账号", type="primary"):
        with st.spinner("正在分析昨日表现..."):
            camps = campaign_manager.get_all_campaigns()
            insights = campaign_manager.get_yesterday_insights()
            st.session_state.pending_actions = campaign_manager.evaluate_optimization_rules(camps, insights)
    
    if st.session_state.pending_actions:
        for i, act in enumerate(st.session_state.pending_actions):
            with st.expander(f"💡 {act['type']}: {act['name']}", expanded=True):
                st.write(f"原因: {act['reason']}")
                if st.button("✅ 批准执行", key=f"exec_{i}"):
                    if campaign_manager.execute_action(act):
                        st.success("指令执行成功！")
                        st.session_state.pending_actions.pop(i); st.rerun()
    else: st.info("当前暂无待处理的优化建议。")

    st.divider()

    # 数据报表
    if st.button("🔄 同步详细表现 (昨日)", use_container_width=True):
        st.session_state.campaign_list = campaign_manager.get_all_campaigns()
        st.session_state.yesterday_insights = campaign_manager.get_yesterday_insights()

    if st.session_state.campaign_list:
        rows = []
        insights = st.session_state.yesterday_insights
        tz_beijing = pytz.timezone('Asia/Shanghai')
        for c in st.session_state.campaign_list:
            cid = c.get('id')
            ins = insights.get(cid, {})
            # 兼容 CBO 预算
            budget = float(c.get('daily_budget', 0)) / 100
            rows.append({
                "ID": cid, "名称": c.get('name'), "状态": c.get('effective_status'),
                "消耗": ins.get('spend', 0), "预算": budget, "安装": ins.get('installs', 0), 
                "ROI": ins.get('roi', 0), "CPI": ins.get('cpi', 0)
            })
        
        df = pd.DataFrame(rows)
        # KPI 总览
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("昨日总消耗", f"${df['消耗'].sum():,.2f}")
        m2.metric("昨日总安装", f"{int(df['安装'].sum()):,}")
        m3.metric("平均 ROI", f"{df[df['消耗']>0]['ROI'].mean():.2f}")
        m4.metric("平均 CPI", f"${(df['消耗'].sum()/df['安装'].sum() if df['安装'].sum()>0 else 0):.2f}")
        
        st.divider()
        st.dataframe(df, use_container_width=True, hide_index=True)

elif page == "⚙️ 系统设置":
    st.title("⚙️ 系统与策略配置")
    config = load_config()
    
    with st.expander("🚀 投流基础策略", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            d_country = st.selectbox("默认投放国家", ["US", "UK", "CA", "AU", "DE", "FR", "JP", "KR"], 
                                     index=["US", "UK", "CA", "AU", "DE", "FR", "JP", "KR"].index(config['default'].get('country', 'US')))
            d_budget = st.number_input("默认每日预算 ($)", value=int(config['default'].get('daily_budget', 50)), min_value=10)
        with c2:
            st.info("当前优化目标固定为: `APP_INSTALLS`")
        if st.button("💾 保存基础配置"):
            config['default'].update({"country": d_country, "daily_budget": d_budget})
            save_config(config); st.success("✅ 配置已更新！")

    with st.expander("🤖 智能风控策略", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            cpi_t = st.slider("CPI 报警阈值 ($)", 0.5, 10.0, float(config['strategy'].get('CPI_THRESHOLD', 2.0)))
            roi_t = st.slider("ROI 报警阈值", 0.1, 5.0, float(config['strategy'].get('ROI_THRESHOLD', 0.5)))
        with c2:
            min_s = st.number_input("判断所需最小消耗 ($)", value=float(config['strategy'].get('MIN_SPEND_FOR_JUDGE', 10.0)))
        if st.button("💾 保存风控策略"):
            config['strategy'].update({"CPI_THRESHOLD": cpi_t, "ROI_THRESHOLD": roi_t, "MIN_SPEND_FOR_JUDGE": min_s})
            save_config(config); st.success("✅ 风控策略已生效！")

    with st.expander("📅 定时日报设置", expanded=False):
        webhook = st.text_input("钉钉 Webhook", value=config['report'].get('webhook_url', ''))
        send_time = st.text_input("推送时间 (HH:mm)", value=config['report'].get('send_time', '10:00'))
        if st.button("💾 保存日报设置"):
            config['report'].update({"webhook_url": webhook, "send_time": send_time})
            save_config(config); st.success("✅ 日报设置已保存！")

st.markdown("<div style='text-align: center; color: #888; font-size: 12px;'>Auto Meta ADS v2.2.7 | 完整功能旗舰版</div>", unsafe_allow_html=True)
