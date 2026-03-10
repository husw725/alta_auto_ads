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
st.set_page_config(page_title="Auto Meta ADS | 旗舰版", page_icon="🦞", layout="wide")

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
    
    # 自动加载
    if not st.session_state.campaign_list:
        with st.spinner("首次进入，正在同步 Meta 表现..."):
            st.session_state.campaign_list = campaign_manager.get_all_campaigns()
            st.session_state.yesterday_insights = campaign_manager.get_yesterday_insights()

    # 智能优化建议
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

    # 顶部 KPI (4项汇总)
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

    # --- 🌟 全指标表格 (补全所有 15 个字段) ---
    if st.session_state.campaign_list:
        rows = []
        insights = st.session_state.yesterday_insights
        for c in st.session_state.campaign_list:
            cid = c.get('id')
            ins = insights.get(cid, {})
            # 解析时间
            raw_time = c.get('start_time', '')[:16].replace('T', ' ')
            delivery_date = raw_time.split()[0] if raw_time else '-'
            
            rows.append({
                "广告id": cid, 
                "广告名称": c.get('name'),
                "状态": c.get('effective_status'),
                "创建时间": raw_time,
                "投放日期": delivery_date,
                "广告花费spend": ins.get('spend', 0),
                "广告预算budget": float(c.get('daily_budget', 0)) / 100,
                "点击量click": ins.get('clicks', 0),
                "点击率ctr": f"{ins.get('ctr', 0)*100:.2f}%",
                "安装量install": ins.get('installs', 0),
                "投资回报率roi": f"{ins.get('roi', 0):.2f}",
                "转化率 cvr": f"{ins.get('cvr', 0)*100:.2f}%",
                "千次展示费用cpm": f"${ins.get('cpm', 0):.2f}",
                "单次点击成本cpc": f"${ins.get('cpc', 0):.2f}",
                "单次安装成本cpi": f"${ins.get('cpi', 0):.2f}",
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
    with st.expander("🚀 投流策略", expanded=True):
        c1, c2 = st.columns(2)
        d_country = c1.selectbox("国家", ["US", "UK", "CA", "AU"], index=0)
        d_budget = c1.number_input("默认预算 ($)", value=int(config['default'].get('daily_budget', 50)))
        cpi_t = c2.slider("CPI 阈值 ($)", 0.5, 10.0, float(config['strategy'].get('CPI_THRESHOLD', 2.0)))
        if st.button("💾 保存配置"):
            config['default'].update({"country": d_country, "daily_budget": d_budget})
            config['strategy'].update({"CPI_THRESHOLD": cpi_t})
            save_config(config); st.success("已保存")

st.markdown("<div style='text-align: center; color: #888; font-size: 12px;'>Auto Meta ADS v2.4.3 | 全指标旗舰版</div>", unsafe_allow_html=True)
