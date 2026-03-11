import streamlit as st
from core.video_selector import AutoMetaADS
from core.campaign_manager import CampaignManager
import os
import pandas as pd
import json
import pytz
import re
import platform
import subprocess
from datetime import datetime

# 页面配置
st.set_page_config(page_title="Auto Meta ADS | 旗舰版", page_icon="🦞", layout="wide")

# --- 🚀 系统定时任务全自动初始化逻辑 ---
def setup_auto_scheduler():
    """根据操作系统自动注册定时日报任务"""
    try:
        current_dir = os.path.abspath(os.path.dirname(__file__))
        send_time = "10:25" # 锁定 10:25
        system_type = platform.system()
        
        if system_type == "Windows":
            # 1. 确保 BAT 文件存在
            bat_path = os.path.join(current_dir, "run_daily_report.bat")
            if not os.path.exists(bat_path):
                with open(bat_path, "w") as f:
                    f.write(f"@echo off\ncd /d {current_dir}\npython daily_report_worker.py\nexit")
            
            # 2. 检查并创建任务 (schtasks)
            check_cmd = f'schtasks /query /tn "AutoMetaAdsReport"'
            if subprocess.run(check_cmd, shell=True, capture_output=True).returncode != 0:
                create_cmd = f'schtasks /create /tn "AutoMetaAdsReport" /tr "{bat_path}" /sc daily /st {send_time} /f'
                subprocess.run(create_cmd, shell=True)
                print(f"✅ Windows 任务计划已注册: {send_time}")
        
        elif system_type in ["Darwin", "Linux"]:
            # 1. 构建 Cron 指令
            python_path = subprocess.check_output("which python3", shell=True).decode().strip()
            cron_cmd = f"25 10 * * * cd {current_dir} && {python_path} daily_report_worker.py >> {current_dir}/report.log 2>&1"
            
            # 2. 检查是否存在
            existing_cron = subprocess.run("crontab -l", shell=True, capture_output=True).stdout.decode()
            if "daily_report_worker.py" not in existing_cron:
                os.system(f'(crontab -l 2>/dev/null; echo "{cron_cmd}") | crontab -')
                print(f"✅ macOS/Linux Cron 已注册: {send_time}")
    except Exception as e:
        print(f"⚠️ 自动初始化定时任务失败: {e}")

# 启动即运行自检
setup_auto_scheduler()

# 1. 状态初始化
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'last_candidates' not in st.session_state: st.session_state.last_candidates = None
if 'campaign_list' not in st.session_state: st.session_state.campaign_list = []
if 'yesterday_insights' not in st.session_state: st.session_state.yesterday_insights = {}
if 'pending_actions' not in st.session_state: st.session_state.pending_actions = []

# 2. 核心模块初始化
ads_module = AutoMetaADS()
campaign_manager = CampaignManager()

def load_config():
    config_path = 'config/config.json'
    if not os.path.exists('config'): os.makedirs('config')
    default_template = {
        "default": {"country": "US", "daily_budget": 50, "optimization_goal": "APP_INSTALLS"},
        "strategy": {"CPI_THRESHOLD": 2.0, "ROI_THRESHOLD": 0.5, "MIN_SPEND_FOR_JUDGE": 10.0},
        "report": {"enabled": True, "send_time": "10:25", "webhook_url": "", "last_sent": ""}
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

# 5. 主区域内容 (保持原有逻辑...)
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
                        if c_res.get('status') == 'success': st.success(f"✅ 已激活！ID: {c_res.get('campaign_id')}")
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
                st.markdown(result['message'])
                st.session_state.chat_history.append({"role": "assistant", "content": result['message']})
            else:
                st.error(f"❌ {result}"); st.session_state.chat_history.append({"role": "assistant", "content": f"❌ {result}"})
        st.rerun()

elif page == "📊 数据看板":
    st.title("📊 广告效果数据中心")
    if not st.session_state.campaign_list:
        with st.spinner("同步 Meta 表现..."):
            st.session_state.campaign_list = campaign_manager.get_all_campaigns()
            st.session_state.yesterday_insights = campaign_manager.get_yesterday_insights()

    st.subheader("🤖 智能调优建议")
    if st.button("🔍 扫描分析风险项", type="primary"):
        with st.spinner("正在分析数据..."):
            history = campaign_manager.get_historical_insights()
            st.session_state.pending_actions = campaign_manager.evaluate_optimization_rules(st.session_state.campaign_list, st.session_state.yesterday_insights, history)
    
    if st.session_state.pending_actions:
        for i, act in enumerate(st.session_state.pending_actions):
            risk_text = "⚠️ [高支出需审批]" if act.get('risk') else "💡 [建议执行]"
            with st.expander(f"{risk_text} {act['type']}: {act['name']}", expanded=True):
                st.markdown(f"原因: {act['reason']}")
                if st.button("✅ 批准执行", key=f"pact_{i}"):
                    if campaign_manager.execute_action(act):
                        st.success("指令已执行"); st.session_state.pending_actions.pop(i); st.rerun()
    else: st.info("当前运行平稳，暂无建议。")

    st.divider()
    if st.session_state.campaign_list:
        ins_map = st.session_state.yesterday_insights
        total_spend = sum(ins.get('spend', 0) for ins in ins_map.values())
        total_installs = sum(ins.get('installs', 0) for ins in ins_map.values())
        avg_roi = sum(ins.get('roi', 0) for ins in ins_map.values()) / len(ins_map) if ins_map else 0
        avg_cpi = total_spend / total_installs if total_installs > 0 else 0
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("昨日总消耗", f"${total_spend:,.2f}")
        m2.metric("昨日总安装", f"{int(total_installs):,}")
        m3.metric("平均 ROI", f"{avg_roi:.2f}")
        m4.metric("平均 CPI", f"${avg_cpi:.2f}")

    if st.button("🔄 手动刷新详细数据", use_container_width=True):
        st.session_state.campaign_list = campaign_manager.get_all_campaigns()
        st.session_state.yesterday_insights = campaign_manager.get_yesterday_insights()
        st.rerun()

    if st.session_state.campaign_list:
        rows = []
        insights = st.session_state.yesterday_insights
        for c in st.session_state.campaign_list:
            cid, ins = c.get('id'), insights.get(c.get('id'), {})
            raw_time = c.get('start_time', '')[:16].replace('T', ' ')
            rows.append({
                "广告id": cid, "广告名称": c.get('name'), "状态": c.get('effective_status'),
                "创建时间": raw_time, "投放日期": raw_time.split()[0] if raw_time else '-',
                "广告花费spend": ins.get('spend', 0), "广告预算budget": float(c.get('daily_budget', 0)) / 100,
                "点击量click": ins.get('clicks', 0), "点击率ctr": f"{ins.get('ctr', 0)*100:.2f}%",
                "安装量install": ins.get('installs', 0), "投资回报率roi": f"{ins.get('roi', 0):.2f}",
                "转化率 cvr": f"{ins.get('cvr', 0)*100:.2f}%", "千次展示费用cpm": f"${ins.get('cpm', 0):.2f}",
                "单次点击成本cpc": f"${ins.get('cpc', 0):.2f}", "单次安装成本cpi": f"${ins.get('cpi', 0):.2f}",
                "单次购物成本cpp": f"${ins.get('cpp', 0):.2f}"
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.subheader("⚙️ 生命周期管理")
        for index, row in pd.DataFrame(rows).iterrows():
            cid, name, status = row['广告id'], row['广告名称'], row['状态']
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            with c1: st.write(f"**{name}**")
            with c2:
                if st.button("🟢 激活", key=f"act_{cid}", disabled=(status=='ACTIVE')):
                    if campaign_manager.update_campaign_status(cid, "ACTIVE"): st.rerun()
            with c3:
                if st.button("🟡 暂停", key=f"pau_{cid}", disabled=(status=='PAUSED')):
                    if campaign_manager.update_campaign_status(cid, "PAUSED"): st.rerun()
            with c4:
                del_key = f"del_confirm_{cid}"
                if st.session_state.get(del_key):
                    if st.button("🔥 确认删除", key=f"fdel_{cid}", type="primary"):
                        if campaign_manager.delete_campaign(cid): st.rerun()
                    if st.button("取消", key=f"cdel_{cid}"):
                        st.session_state[del_key] = False; st.rerun()
                else:
                    if st.button("🗑️ 删除", key=f"pre_{cid}"):
                        st.session_state[del_key] = True; st.rerun()
            st.divider()

elif page == "⚙️ 系统设置":
    st.title("⚙️ 系统与策略配置")
    config = load_config()
    with st.expander("🚀 投流基础策略", expanded=True):
        c1, c2 = st.columns(2)
        d_country = c1.selectbox("国家", ["US", "UK", "CA", "AU"], index=0)
        d_budget = c1.number_input("默认预算 ($)", value=int(config['default'].get('daily_budget', 50)))
        if st.button("💾 保存基础"):
            config['default'].update({"country": d_country, "daily_budget": d_budget}); save_config(config); st.success("已保存")
    with st.expander("🤖 智能风控策略", expanded=True):
        c1, c2 = st.columns(2)
        cpi_t = c1.slider("CPI 阈值 ($)", 0.5, 10.0, float(config['strategy'].get('CPI_THRESHOLD', 2.0)))
        min_s = c2.number_input("最小判定消耗", value=float(config['strategy'].get('MIN_SPEND_FOR_JUDGE', 10.0)))
        if st.button("💾 保存风控"):
            config['strategy'].update({"CPI_THRESHOLD": cpi_t, "MIN_SPEND_FOR_JUDGE": min_s}); save_config(config); st.success("已生效")
    with st.expander("📅 定时日报设置", expanded=True):
        last_sent = config['report'].get('last_sent', '无记录')
        st.write(f"**任务健康度**: {'🟢 正常' if '2026' in last_sent else '🔴 待检查'} (上次成功: {last_sent})")
        webhook = st.text_input("钉钉 Webhook", value=config['report'].get('webhook_url', ''))
        send_time = st.text_input("推送时间 (HH:mm)", value=config['report'].get('send_time', '10:25'))
        if st.button("💾 保存日报"):
            config['report'].update({"webhook_url": webhook, "send_time": send_time}); save_config(config); st.success("✅ 设置已保存！")

st.markdown("<div style='text-align: center; color: #888; font-size: 12px;'>Auto Meta ADS v2.4.5 | 跨平台自动化环境版</div>", unsafe_allow_html=True)
