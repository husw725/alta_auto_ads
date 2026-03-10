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
st.set_page_config(page_title="Auto Meta ADS | 旗舰版", page_icon="🤖", layout="wide")

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

def load_config():
    config_path = 'config/config.json'
    if not os.path.exists('config'): os.makedirs('config')
    default_template = {
        "default": {"country": "US", "daily_budget": 50, "optimization_goal": "APP_INSTALLS"},
        "strategy": {"CPI_THRESHOLD": 2.0, "ROI_THRESHOLD": 0.5, "MIN_SPEND_FOR_JUDGE": 10.0},
        "report": {"enabled": True, "send_time": "10:00", "webhook_url": "", "last_sent": ""}
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
    st.divider()
    st.caption(f"🌍 {cfg['default'].get('country')} | 💰 ${cfg['default'].get('daily_budget')}")

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
        
        res_name = prompt
        if st.session_state.last_candidates:
            m = re.search(r'(\d+)', prompt)
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(st.session_state.last_candidates): res_name = st.session_state.last_candidates[idx]['name']

        with st.spinner("🔍 处理中..."):
            success, result = ads_module.process_request(res_name, enable_campaign=False)
        
        with st.chat_message("assistant"):
            if success:
                st.session_state.last_candidates = None
                st.markdown(f"### ✅ 找到素材：{result['drama']}\n请确认并启动投放。")
                st.session_state.chat_history.append({"role": "assistant", "content": f"### ✅ 找到素材：{result['drama']}", "ad_result": result})
            elif isinstance(result, dict) and result.get('error_type') == 'multiple_dramas':
                st.session_state.last_candidates = result['candidates']
                st.markdown(result['message'])
                st.session_state.chat_history.append({"role": "assistant", "content": result['message']})
            else:
                st.error(f"❌ {result}"); st.session_state.chat_history.append({"role": "assistant", "content": f"❌ {result}"})
        st.rerun()

elif page == "📊 数据看板":
    st.title("📊 广告效果数据中心")
    
    st.subheader("🤖 智能优化建议")
    if st.button("🔍 扫描分析账号", type="primary"):
        with st.spinner("正在分析数据..."):
            camps = campaign_manager.get_all_campaigns()
            insights = campaign_manager.get_yesterday_insights()
            st.session_state.pending_actions = campaign_manager.evaluate_optimization_rules(camps, insights)
    
    if st.session_state.pending_actions:
        for i, act in enumerate(st.session_state.pending_actions):
            with st.expander(f"💡 {act['type']}: {act['name']}", expanded=True):
                st.write(f"原因: {act['reason']}")
                if st.button("✅ 批准执行", key=f"exec_{i}"):
                    if campaign_manager.execute_action(act): st.success("已执行！"); st.session_state.pending_actions.pop(i); st.rerun()
    else: st.info("暂无优化建议。")

    st.divider()

    if st.button("🔄 同步 Meta 详细表现 (昨日)", use_container_width=True):
        st.session_state.campaign_list = campaign_manager.get_all_campaigns()
        st.session_state.yesterday_insights = campaign_manager.get_yesterday_insights()

    if st.session_state.campaign_list:
        rows = []
        insights = st.session_state.yesterday_insights
        for c in st.session_state.campaign_list:
            cid = c.get('id')
            ins = insights.get(cid, {})
            rows.append({
                "广告ID": cid, "广告名称": c.get('name'), "状态": c.get('effective_status'),
                "创建时间": c.get('start_time', '')[:16], "花费": ins.get('spend', 0),
                "预算": float(c.get('daily_budget', 0))/100, "点击": ins.get('clicks', 0),
                "CTR": f"{ins.get('ctr', 0)*100:.2f}%", "安装": ins.get('installs', 0),
                "ROI": f"{ins.get('roi', 0):.2f}", "CVR": f"{ins.get('cvr', 0)*100:.2f}%",
                "CPM": f"${ins.get('cpm', 0):.2f}", "CPC": f"${ins.get('cpc', 0):.2f}",
                "CPI": f"${ins.get('cpi', 0):.2f}", "CPP": f"${ins.get('cpp', 0):.2f}"
            })
        
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.subheader("⚙️ 状态管理")
        for index, row in df.iterrows():
            c1, c2, c3, c4 = st.columns([4, 2, 1, 1])
            with c1: st.write(f"**{row['广告名称']}**")
            with c2: st.caption(f"ID: `{row['广告ID']}` | `{row['状态']}`")
            with c3:
                if st.button("🟢 激活", key=f"on_{row['广告ID']}", disabled=(row['状态']=='ACTIVE')):
                    if campaign_manager.update_campaign_status(row['广告ID'], "ACTIVE"): st.rerun()
            with c4:
                if st.button("🟡 暂停", key=f"off_{row['广告ID']}", disabled=(row['状态']=='PAUSED')):
                    if campaign_manager.update_campaign_status(row['广告ID'], "PAUSED"): st.rerun()

elif page == "⚙️ 系统设置":
    st.title("⚙️ 系统与策略配置")
    config = load_config()
    with st.expander("🚀 基础策略", expanded=True):
        c1, c2 = st.columns(2)
        d_country = c1.selectbox("国家", ["US", "UK", "CA", "AU", "DE", "FR", "JP", "KR"], index=0)
        d_budget = c1.number_input("预算 ($)", value=int(config['default'].get('daily_budget', 50)))
        if st.button("💾 保存基础"):
            config['default'].update({"country": d_country, "daily_budget": d_budget})
            save_config(config); st.success("已保存")

    with st.expander("🤖 智能风控", expanded=True):
        c1, c2 = st.columns(2)
        cpi_t = c1.slider("CPI 阈值", 0.5, 10.0, float(config['strategy'].get('CPI_THRESHOLD', 2.0)))
        min_s = c2.number_input("最小消耗", value=float(config['strategy'].get('MIN_SPEND_FOR_JUDGE', 10.0)))
        if st.button("💾 保存风控"):
            config['strategy'].update({"CPI_THRESHOLD": cpi_t, "MIN_SPEND_FOR_JUDGE": min_s})
            save_config(config); st.success("已生效")

st.markdown("<div style='text-align: center; color: #888; font-size: 12px;'>Auto Meta ADS v2.3.0 | 全指标专业版</div>", unsafe_allow_html=True)
