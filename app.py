import streamlit as st
from core.video_selector import AutoMetaADS
from core.campaign_manager import CampaignManager
from daily_report_worker import run_job
import os
import pandas as pd
import json
import time
import threading
import re
from datetime import datetime, timedelta, timezone

# 页面配置
st.set_page_config(page_title="Auto Meta ADS | 龙虾AI", page_icon="🦞", layout="wide")

# 绝对路径锁定
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'config.json')

# --- 🚀 内部监控引擎 ---
@st.cache_resource
def start_background_monitor():
    def monitor_loop():
        log_file = os.path.join(BASE_DIR, "monitor_debug.log")
        user_tz = timezone(timedelta(hours=-8))
        last_trigger_fingerprint = "" 
        while True:
            try:
                now_user = datetime.now(user_tz)
                current_time = now_user.strftime("%H:%M")
                today = now_user.strftime("%Y-%m-%d")
                if not os.path.exists(CONFIG_PATH):
                    time.sleep(30); continue
                with open(CONFIG_PATH, 'r') as f: cfg = json.load(f)
                target_time = cfg.get('report', {}).get('send_time', '10:25')
                enabled = cfg.get('report', {}).get('enabled', True)
                current_fingerprint = f"{today}_{target_time}"
                if enabled and current_time == target_time and last_trigger_fingerprint != current_fingerprint:
                    run_job(is_test=False)
                    last_trigger_fingerprint = current_fingerprint
            except: pass
            time.sleep(20)
    threading.Thread(target=monitor_loop, daemon=True).start()
    return True

start_background_monitor()

# 状态初始化
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'last_candidates' not in st.session_state: st.session_state.last_candidates = None
if 'campaign_list' not in st.session_state: st.session_state.campaign_list = []
if 'yesterday_insights' not in st.session_state: st.session_state.yesterday_insights = {}
if 'pending_actions' not in st.session_state: st.session_state.pending_actions = []
if 'current_date_view' not in st.session_state: st.session_state.current_date_view = ""

# 核心模块
ads_module = AutoMetaADS()
campaign_manager = CampaignManager()

def load_config():
    if not os.path.exists('config'): os.makedirs('config')
    default_template = {"default": {"country": "US", "daily_budget": 50}, "strategy": {"CPI_THRESHOLD": 2.0, "ROI_THRESHOLD": 0.5, "MIN_SPEND_FOR_JUDGE": 10.0}, "report": {"enabled": True, "send_time": "10:25", "webhook_url": "", "last_sent": ""}}
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'w') as f: json.dump(default_template, f, indent=2)
        return default_template
    with open(CONFIG_PATH, 'r') as f: return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, 'w') as f: json.dump(config, f, indent=2)

# 侧边栏
with st.sidebar:
    st.title("🚀 Meta ADS")
    page = st.radio("功能模式", ["💬 AI 投流助手", "📊 数据看板", "⚙️ 系统设置"], index=0)
    cfg = load_config()
    st.divider()
    st.caption(f"🌍 {cfg['default'].get('country')} | 💰 ${cfg['default'].get('daily_budget')}")

# 主区域内容
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
                            c_res = campaign_manager.create_campaign(res['drama'], res['video_link'], res.get('video_detail', {}).get('cover_url'))
                        if c_res.get('status') == 'success': st.success("✅ 已激活！")
                        else: st.error(f"❌ 失败: {c_res['error']}")

    if prompt := st.chat_input("输入剧名或编号..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        res_name = prompt
        if st.session_state.last_candidates:
            m = re.search(r'(\d+)', prompt)
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(st.session_state.last_candidates): res_name = st.session_state.last_candidates[idx]['name']
        with st.spinner("🔍 检索素材..."):
            success, result = ads_module.process_request(res_name, enable_campaign=False)
        with st.chat_message("assistant"):
            if success:
                st.session_state.last_candidates = None
                st.markdown(f"### ✅ 找到素材：{result['drama']}")
                st.session_state.chat_history.append({"role": "assistant", "content": f"### ✅ 找到素材：{result['drama']}", "ad_result": result})
            elif isinstance(result, dict) and result.get('error_type') == 'multiple_dramas':
                st.session_state.last_candidates = result['candidates']
                st.markdown(result['message']); st.session_state.chat_history.append({"role": "assistant", "content": result['message']})
            else:
                st.error(f"❌ {result}"); st.session_state.chat_history.append({"role": "assistant", "content": f"❌ {result}"})
        st.rerun()

elif page == "📊 数据看板":
    st.title("📊 广告效果数据中心")
    user_tz = timezone(timedelta(hours=-8))
    today_user = datetime.now(user_tz)
    
    date_col1, date_col2 = st.columns([1, 4])
    selected_day = date_col1.selectbox("查看日期", ["昨天", "今天"], index=1)
    target_date = (today_user - timedelta(days=1)) if selected_day == "昨天" else today_user
    date_str = target_date.strftime('%Y-%m-%d')
    date_col2.info(f"📅 正在展示 {selected_day} ({date_str}) 的投放数据 (UTC-8)")

    if st.session_state.current_date_view != date_str or not st.session_state.campaign_list:
        with st.spinner(f"拉取 {date_str} 数据..."):
            st.session_state.campaign_list = campaign_manager.get_all_campaigns()
            st.session_state.yesterday_insights = campaign_manager.get_yesterday_insights(date_str)
            st.session_state.current_date_view = date_str

    # --- 🌟 [MANDATORY] 顶部 KPI 汇总项 ---
    if st.session_state.yesterday_insights:
        ins_map = st.session_state.yesterday_insights
        total_spend = sum(ins.get('spend', 0) for ins in ins_map.values())
        total_installs = sum(ins.get('installs', 0) for ins in ins_map.values())
        avg_roi = sum(ins.get('roi', 0) for ins in ins_map.values()) / len(ins_map) if ins_map else 0
        avg_cpi = total_spend / total_installs if total_installs > 0 else 0

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric(f"{selected_day}总消耗", f"${total_spend:,.2f}")
        kpi2.metric(f"{selected_day}总安装", f"{int(total_installs):,}")
        kpi3.metric("平均 ROI", f"{avg_roi:.2f}")
        kpi4.metric("平均 CPI", f"${avg_cpi:.2f}")

    st.subheader("🤖 智能调优建议")
    c1, c2 = st.columns([1, 1])
    if c1.button("🔍 扫描分析风险项", type="primary", width='stretch'):
        with st.spinner("分析中..."):
            history = campaign_manager.get_historical_insights()
            st.session_state.pending_actions = campaign_manager.evaluate_optimization_rules(st.session_state.campaign_list, st.session_state.yesterday_insights, history)
    
    if st.session_state.pending_actions:
        safe_actions = [a for a in st.session_state.pending_actions if not a.get('risk')]
        if safe_actions and c2.button(f"⚡ 一键执行 {len(safe_actions)} 项安全优化", width='stretch'):
            for act in safe_actions: campaign_manager.execute_action(act)
            st.success(f"已执行 {len(safe_actions)} 项优化！"); st.session_state.pending_actions = []; st.rerun()

        for i, act in enumerate(st.session_state.pending_actions):
            risk_text = "⚠️ [高支出需审批]" if act.get('risk') else "💡 [建议执行]"
            with st.expander(f"{risk_text} {act['type']}: {act['name']}", expanded=True):
                st.write(f"原因: {act['reason']}")
                if st.button("✅ 批准执行", key=f"pact_{i}"):
                    if campaign_manager.execute_action(act): st.success("已执行"); st.session_state.pending_actions.pop(i); st.rerun()
    else: st.info("当前运行平稳。")

    st.divider()
    if st.button("🔄 手动刷新 Meta 详细数据", width='stretch'):
        st.session_state.campaign_list = campaign_manager.get_all_campaigns()
        st.session_state.yesterday_insights = campaign_manager.get_yesterday_insights(date_str)
        st.rerun()

    if st.session_state.campaign_list:
        rows = []
        insights = st.session_state.yesterday_insights
        for c in st.session_state.campaign_list:
            cid, ins = c.get('id'), insights.get(c.get('id'), {})
            raw_time = c.get('start_time', '')[:16].replace('T', ' ')
            rows.append({
                "广告id": cid, "广告名称": c.get('name'), "状态": c.get('effective_status'), "创建时间": raw_time, "投放日期": raw_time.split()[0] if raw_time else '-',
                "花费spend": ins.get('spend', 0), "预算budget": float(c.get('daily_budget', 0)) / 100, "点击click": ins.get('clicks', 0),
                "点击率ctr": f"{ins.get('ctr', 0)*100:.2f}%", "安装install": ins.get('installs', 0), "ROI": f"{ins.get('roi', 0):.2f}",
                "转化率cvr": f"{ins.get('cvr', 0)*100:.2f}%", "CPM": f"${ins.get('cpm', 0):.2f}", "CPC": f"${ins.get('cpc', 0):.2f}",
                "CPI": f"${ins.get('cpi', 0):.2f}", "CPP": f"${ins.get('cpp', 0):.2f}"
            })
        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)

        st.subheader("⚙️ 生命周期管理")
        for index, row in pd.DataFrame(rows).iterrows():
            cid, name, status = row['广告id'], row['广告名称'], row['状态']
            cl1, cl2, cl3, cl4 = st.columns([3, 1, 1, 1])
            with cl1: st.write(f"**{name}**")
            with cl2:
                if st.button("🟢 激活", key=f"act_{cid}", disabled=(status=='ACTIVE')):
                    if campaign_manager.update_campaign_status(cid, "ACTIVE"): st.rerun()
            with cl3:
                if st.button("🟡 暂停", key=f"pau_{cid}", disabled=(status=='PAUSED')):
                    if campaign_manager.update_campaign_status(cid, "PAUSED"): st.rerun()
            with cl4:
                del_k = f"del_{cid}"
                if st.session_state.get(del_k):
                    if st.button("🔥 删", key=f"fdel_{cid}", type="primary"): 
                        if campaign_manager.delete_campaign(cid): st.rerun()
                    if st.button("返", key=f"rdel_{cid}"): st.session_state[del_k] = False; st.rerun()
                elif st.button("🗑️ 删", key=f"pre_{cid}"): st.session_state[del_k] = True; st.rerun()
            st.divider()

elif page == "⚙️ 系统设置":
    st.title("⚙️ 系统与策略配置")
    config = load_config()
    with st.expander("🚀 基础策略", expanded=True):
        c1, c2 = st.columns(2)
        d_country = c1.selectbox("国家", ["US", "UK", "CA", "AU"], index=0)
        d_budget = c1.number_input("默认预算 ($)", value=int(config['default'].get('daily_budget', 50)))
        if st.button("💾 保存基础"):
            config['default'].update({"country": d_country, "daily_budget": d_budget}); save_config(config); st.success("已保存"); st.rerun()
    with st.expander("🤖 智能风控", expanded=True):
        c1, c2 = st.columns(2)
        cpi_t = c1.slider("CPI 阈值 ($)", 0.5, 10.0, float(config['strategy'].get('CPI_THRESHOLD', 2.0)))
        min_s = c2.number_input("最小判定消耗", value=float(config['strategy'].get('MIN_SPEND_FOR_JUDGE', 10.0)))
        if st.button("💾 保存风控"):
            config['strategy'].update({"CPI_THRESHOLD": cpi_t, "MIN_SPEND_FOR_JUDGE": min_s}); save_config(config); st.success("已生效"); st.rerun()
    with st.expander("📅 定时日报设置", expanded=True):
        last_sent = config['report'].get('last_sent', '无记录')
        st.write(f"**任务状态**: ⚡ 正常运行 (上次成功: {last_sent})")
        if st.button("🧪 立即测试日报发送", width='stretch'): run_job(is_test=True); st.success("指令已发出！")
        webhook = st.text_input("钉钉 Webhook", value=config['report'].get('webhook_url', ''))
        send_time = st.text_input("时间 (HH:mm)", value=config['report'].get('send_time', '10:25'))
        if st.button("💾 保存日报"):
            config['report'].update({"webhook_url": webhook, "send_time": send_time}); save_config(config); st.success("已保存"); st.rerun()

st.markdown("<div style='text-align: center; color: #888; font-size: 12px;'>Auto Meta ADS v2.8.3 | 零回退稳定版</div>", unsafe_allow_html=True)
