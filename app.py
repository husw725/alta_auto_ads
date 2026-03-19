import streamlit as st
import streamlit.components.v1 as components
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

# 绝对路径
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
if 'active_preview' not in st.session_state: st.session_state.active_preview = None
if 'ad_details' not in st.session_state: st.session_state.ad_details = {}

# 核心模块
ads_module = AutoMetaADS()
campaign_manager = CampaignManager()

def load_config():
    if not os.path.exists('config'): os.makedirs('config')
    default_template = {"default": {"country": "US", "daily_budget": 50, "target_platform": "iOS", "promo_method": "w2a"}, "strategy": {"CPI_THRESHOLD": 2.0, "ROI_THRESHOLD": 0.5, "MIN_SPEND_FOR_JUDGE": 10.0}, "report": {"enabled": True, "send_time": "10:25", "webhook_url": "", "last_sent": ""}}
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'w') as f: json.dump(default_template, f, indent=2)
        return default_template
    with open(CONFIG_PATH, 'r') as f: return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, 'w') as f: json.dump(config, f, indent=2)

# 4. 侧边栏
with st.sidebar:
    st.title("🚀 Meta ADS")
    page = st.radio("功能模式", ["💬 AI 投流助手", "📊 数据看板", "⚙️ 系统设置"], index=0)
    cfg = load_config()
    st.divider()
    st.caption(f"🌍 {cfg['default'].get('country')} | 💰 ${cfg['default'].get('daily_budget')}")
    st.caption(f"📱 {cfg['default'].get('target_platform')} | 🔗 {cfg['default'].get('promo_method')}")

# AI 助手页面
if page == "💬 AI 投流助手":
    st.title("💬 AI 投流助手")
    for i, chat in enumerate(st.session_state.chat_history):
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
            if chat.get("ad_result"):
                res = chat["ad_result"]
                with st.form(f"f_{i}"):
                    st.markdown(f"### 🚀 赛马计划: {res['drama']}")
                    st.info(f"配置: **{cfg['default']['target_platform']}** + **{cfg['default']['promo_method']}** | 素材: **{res['count']}** 个视频")
                    if st.form_submit_button("🔥 确认并立即投流"):
                        p_bar = st.progress(0, text="批量上传中...")
                        with st.spinner("执行中..."):
                            c_res = campaign_manager.create_campaign(res['drama'], res['materials'], target_language=res.get('lang', '英语'))
                        if c_res.get('status') == 'success': 
                            st.success("✅ 已发布！"); st.session_state.campaign_list = []
                        else: st.error(f"❌ 失败: {c_res['error']}")

    if prompt := st.chat_input("输入指令..."):
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
                msg = f"### ✅ 找到素材：{result['drama']}\n采样 **{result['count']}** 个视频。请确认："
                st.markdown(msg); st.session_state.chat_history.append({"role": "assistant", "content": msg, "ad_result": result})
            elif isinstance(result, dict) and result.get('error_type') == 'multiple_dramas':
                st.session_state.last_candidates = result['candidates']
                cand_msg = "找到多部剧集：\n\n" + "\n".join([f"{idx+1}. **{c['name']}**" for idx, c in enumerate(result['candidates'])])
                st.markdown(cand_msg); st.session_state.chat_history.append({"role": "assistant", "content": cand_msg})
            else:
                st.error(f"❌ {result}"); st.session_state.chat_history.append({"role": "assistant", "content": f"❌ {result}"})
        st.rerun()

# 数据看板页面
elif page == "📊 数据看板":
    st.title("📊 广告效果数据中心")
    user_tz = timezone(timedelta(hours=-8))
    now_user = datetime.now(user_tz)
    today_dt, yesterday_dt = now_user.date(), now_user.date() - timedelta(days=1)

    date_col1, date_col2 = st.columns([2, 3])
    quick_select = date_col1.radio("快速选择", ["今天", "昨天", "自定义"], index=0, horizontal=True)
    if quick_select == "今天": start_date, end_date = today_dt, today_dt
    elif quick_select == "昨天": start_date, end_date = yesterday_dt, yesterday_dt
    else: 
        selected_range = date_col1.date_input("选择范围", value=[yesterday_dt, today_dt])
        start_date = selected_range[0] if len(selected_range) > 0 else yesterday_dt
        end_date = selected_range[1] if len(selected_range) > 1 else today_dt
    
    since_str, until_str = start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
    date_col2.info(f"📅 区间: `{since_str}` 至 `{until_str}` (UTC-8)")

    if st.session_state.current_date_view != f"{since_str}_{until_str}" or not st.session_state.campaign_list:
        with st.spinner(f"拉取数据..."):
            st.session_state.campaign_list = campaign_manager.get_all_campaigns()
            st.session_state.yesterday_insights = campaign_manager.get_custom_insights(since_str, until_str)
            st.session_state.current_date_view = f"{since_str}_{until_str}"

    if st.session_state.yesterday_insights:
        ins_map = st.session_state.yesterday_insights
        total_spend = sum(ins.get('spend', 0) for ins in ins_map.values())
        total_installs = sum(ins.get('installs', 0) for ins in ins_map.values())
        total_purchases = sum(ins.get('purchases', 0) for ins in ins_map.values())
        avg_cpi = total_spend / total_installs if total_installs > 0 else 0
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("区间总消耗", f"${total_spend:,.2f}"); k2.metric("区间总安装", f"{int(total_installs):,}"); k3.metric("总购买", f"{int(total_purchases):,}"); k4.metric("平均 CPI", f"${avg_cpi:.2f}")

    st.subheader("🤖 智能调优建议")
    c1, c2 = st.columns([1, 1])
    if c1.button("🔍 扫描分析风险项", type="primary", width='stretch'):
        with st.spinner("分析中..."):
            history = campaign_manager.get_historical_insights()
            st.session_state.pending_actions = campaign_manager.evaluate_optimization_rules(st.session_state.campaign_list, st.session_state.yesterday_insights, history)
    
    if st.session_state.pending_actions:
        safe_actions = [a for a in st.session_state.pending_actions if not a.get('risk')]
        if safe_actions and c2.button(f"⚡ 一键执行 {len(safe_actions)} 项安全优化", width='stretch'):
            for act in safe_actions: 
                if campaign_manager.execute_action(act):
                    for camp in st.session_state.campaign_list:
                        if camp.get('id') == act['cid']: camp['effective_status'] = 'PAUSED'
            st.success("优化成功"); st.rerun()
        for i, act in enumerate(st.session_state.pending_actions):
            with st.expander(f"{'⚠️' if act.get('risk') else '💡'} {act['type']}: {act['name']}", expanded=True):
                st.write(f"原因: {act['reason']}")
                if st.button("✅ 执行", key=f"pact_{i}"):
                    if campaign_manager.execute_action(act): 
                        for camp in st.session_state.campaign_list:
                            if camp.get('id') == act['cid']: camp['effective_status'] = 'PAUSED'
                        st.success("已执行"); st.session_state.pending_actions.pop(i); st.rerun()

    st.divider()
    if st.session_state.active_preview:
        with st.container():
            st.subheader(f"👁️ 赛马预览: {st.session_state.active_preview['campaign_name']}")
            previews = st.session_state.active_preview['list']
            if previews:
                tabs = st.tabs([p['name'] for p in previews])
                for idx, tab in enumerate(tabs):
                    with tab: components.html(previews[idx]['html'], height=600, scrolling=True)
            if st.button("❌ 关闭预览"): st.session_state.active_preview = None; st.rerun()
        st.divider()

    if st.button("🔄 手动同步 Meta 最新全量数据", width='stretch'):
        st.session_state.campaign_list = []; st.rerun()

    if st.session_state.campaign_list:
        rows = []
        insights = st.session_state.yesterday_insights
        for c in st.session_state.campaign_list:
            cid, ins = c.get('id'), insights.get(c.get('id'), {})
            raw_time = c.get('start_time', '')[:16].replace('T', ' ')
            rows.append({
                "广告id": cid, "名称": c.get('name'), "状态": c.get('effective_status'), "创建时间": raw_time, "投放日期": raw_time.split()[0] if raw_time else '-',
                "预算$": float(c.get('daily_budget', 0)) / 100, "花费$": ins.get('spend', 0), "曝光": ins.get('imps', 0), "点击": ins.get('clicks', 0),
                "CTR": f"{ins.get('ctr', 0)*100:.2f}%", "安装": ins.get('installs', 0), "CPI$": f"{ins.get('cpi', 0):.2f}",
                "购买": ins.get('purchases', 0), "CPP$": f"{ins.get('cpp', 0):.2f}", "ROI": f"{ins.get('roi', 0):.2f}",
                "CVR": f"{ins.get('cvr', 0)*100:.2f}%", "PurCVR": f"{ins.get('pur_cvr', 0)*100:.2f}%", "CPM": f"${ins.get('cpm', 0):.2f}", "CPC": f"${ins.get('cpc', 0):.2f}"
            })
        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)

        st.subheader("⚙️ 生命周期与赛马穿透管理")
        for index, row in pd.DataFrame(rows).iterrows():
            cid, name, status = row['广告id'], row['名称'], row['状态']
            cl1, cl2, cl3, cl4, cl5 = st.columns([3, 1, 1, 1, 1])
            with cl1: st.write(f"**{name}**")
            with cl2:
                if st.button("👁️ 预览", key=f"prev_{cid}"):
                    with st.spinner("拉取预览..."):
                        p_list = campaign_manager.get_ad_preview(cid)
                        if p_list: st.session_state.active_preview = {'campaign_name': name, 'list': p_list}; st.rerun()
                        else: st.error("无法获取预览")
            with cl3:
                if st.button("🟢 激活", key=f"act_{cid}", disabled=(status=='ACTIVE')):
                    if campaign_manager.update_campaign_status(cid, "ACTIVE"): 
                        for camp in st.session_state.campaign_list:
                            if camp.get('id') == cid: camp['effective_status'] = 'ACTIVE'; break
                        st.rerun()
            with cl4:
                if st.button("🟡 暂停", key=f"pau_{cid}", disabled=(status=='PAUSED')):
                    if campaign_manager.update_campaign_status(cid, "PAUSED"): 
                        for camp in st.session_state.campaign_list:
                            if camp.get('id') == cid: camp['effective_status'] = 'PAUSED'; break
                        st.rerun()
            with cl5:
                del_k = f"del_{cid}"
                if st.session_state.get(del_k):
                    if st.button("🔥 确认", key=f"fdel_{cid}", type="primary"):
                        if campaign_manager.delete_campaign(cid):
                            st.session_state.campaign_list = [c for c in st.session_state.campaign_list if c.get('id') != cid]; st.session_state[del_k] = False; st.rerun()
                    if st.button("取消", key=f"rdel_{cid}"): st.session_state[del_k] = False; st.rerun()
                elif st.button("🗑️ 删", key=f"pre_{cid}"): st.session_state[del_k] = True; st.rerun()
            
            # 🚀 [TASK 7.2] 赛马详情穿透展示
            with st.expander(f"📊 查看该系列下的 5 个素材赛马详情"):
                if st.button("🔃 加载/刷新素材细分数据", key=f"load_ad_{cid}"):
                    with st.spinner("正在穿透抓取 Ad 级别数据..."):
                        st.session_state.ad_details[cid] = campaign_manager.get_ad_level_details(cid, since_str, until_str)
                
                if cid in st.session_state.ad_details:
                    ad_data = st.session_state.ad_details[cid]
                    if ad_data:
                        # 转换成 DataFrame 显示
                        df_ad = pd.DataFrame(ad_data)
                        # 重命名/格式化列以适应小屏幕
                        display_cols = {
                            'name': '素材名称', 'effective_status': '状态', 'spend': '花费$', 'installs': '安装', 
                            'purchases': '购买', 'cpi': 'CPI$', 'ctr': 'CTR', 'cvr': 'CVR'
                        }
                        df_show = df_ad[list(display_cols.keys())].rename(columns=display_cols)
                        st.table(df_show) # 使用静态表格更清晰
                    else: st.info("该系列下暂无素材数据。")
            st.divider()

elif page == "⚙️ 系统设置":
    st.title("⚙️ 系统与策略配置")
    config = load_config()
    with st.expander("🚀 投流基础策略", expanded=True):
        c1, c2 = st.columns(2)
        d_country = c1.selectbox("国家", ["US", "UK", "CA", "AU", "DE", "FR", "JP", "KR"], index=0)
        d_budget = c1.number_input("默认预算 ($)", value=int(config['default'].get('daily_budget', 50)))
        d_platform = c2.selectbox("投放平台 (OS)", ["iOS", "Android", "All"], index=["iOS", "Android", "All"].index(config['default'].get('target_platform', 'iOS')))
        d_method = c2.selectbox("投放链路", ["w2a", "Direct"], index=["w2a", "Direct"].index(config['default'].get('promo_method', 'w2a')))
        if st.button("💾 保存基础策略"):
            config['default'].update({"country": d_country, "daily_budget": d_budget, "target_platform": d_platform, "promo_method": d_method})
            save_config(config); st.success("已保存"); st.rerun()
    with st.expander("🤖 智能风控策略", expanded=True):
        c1, c2 = st.columns(2)
        cpi_t = c1.slider("CPI 阈值 ($)", 0.5, 10.0, float(config['strategy'].get('CPI_THRESHOLD', 2.0)))
        min_s = c2.number_input("最小判定消耗", value=float(config['strategy'].get('MIN_SPEND_FOR_JUDGE', 10.0)))
        if st.button("💾 保存风控"):
            config['strategy'].update({"CPI_THRESHOLD": cpi_t, "MIN_SPEND_FOR_JUDGE": min_s}); save_config(config); st.success("已生效"); st.rerun()
    with st.expander("📅 定时日报设置", expanded=True):
        last_sent = config['report'].get('last_sent', '无记录')
        st.write(f"**任务健康度**: ⚡ 锁定 UTC-8 正常运行 (上次成功: {last_sent})")
        if st.button("🧪 立即测试日报发送", width='stretch'): run_job(is_test=True); st.success("指令已发出！")
        webhook = st.text_input("钉钉 Webhook", value=config['report'].get('webhook_url', ''))
        send_time = st.text_input("推送时间 (HH:mm)", value=config['report'].get('send_time', '10:25'))
        if st.button("💾 保存日报配置"):
            config['report'].update({"webhook_url": webhook, "send_time": send_time}); save_config(config); st.success("✅ 设置已保存！"); st.rerun()

st.markdown("<div style='text-align: center; color: #888; font-size: 12px;'>Auto Meta ADS v3.2.0 | 赛马穿透透视版</div>", unsafe_allow_html=True)
