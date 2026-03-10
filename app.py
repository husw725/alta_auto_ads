import streamlit as st
from core.video_selector import AutoMetaADS
from core.campaign_manager import CampaignManager
import os
import re
import pandas as pd
import json

# 页面配置
st.set_page_config(
    page_title="Auto Meta ADS | 数据中心",
    page_icon="📊",
    layout="wide"
)

# 1. 状态初始化
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
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
    if not os.path.exists('config'): os.makedirs('config')
    if not os.path.exists(config_path):
        default_config = {
            "default": {"country": "US", "daily_budget": 50, "optimization_goal": "MOBILE_APP_INSTALLS"},
            "report": {"enabled": True, "send_time": "10:00", "webhook_url": "", "last_sent": ""}
        }
        with open(config_path, 'w') as f: json.dump(default_config, f, indent=2)
    with open(config_path, 'r') as f: return json.load(f)

def save_config(config):
    with open('config/config.json', 'w') as f: json.dump(config, f, indent=2)

# 4. 侧边栏
with st.sidebar:
    st.title("🚀 Meta ADS")
    st.markdown("---")
    page = st.radio("功能模式", ["💬 AI 投流助手", "📊 数据看板", "⚙️ 系统设置"], index=1) # 默认进入看板
    st.divider()
    cfg = load_config().get('default', {})
    st.caption(f"🌍 默认国家: `{cfg.get('country')}`")
    st.caption(f"💰 默认预算: `${cfg.get('daily_budget')}`")

# 5. 主区域内容
if page == "💬 AI 投流助手":
    st.title("💬 AI 投流助手")
    # ... (保持原有的 AI 助手逻辑，略)
    for i, chat in enumerate(st.session_state.chat_history):
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
            if chat.get("ad_result"):
                res = chat["ad_result"]
                with st.form(f"form_{i}"):
                    st.write(f"确认投流: **{res['drama']}**")
                    if st.form_submit_button("🚀 启动 Campaign"):
                        with st.spinner("🚀 创建并激活中..."):
                            c_res = campaign_manager.create_campaign(res['drama'], res['video_link'])
                        if c_res['status'] == 'success': st.success("✅ 投流并激活成功！")
                        else: st.error(f"❌ 失败: {c_res['error']}")
    if prompt := st.chat_input("输入剧名..."):
        # 简化版 process_input 逻辑直接集成
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.spinner("🔍 正在查询 XMP..."):
            success, result = ads_module.process_request(prompt, enable_campaign=False)
        with st.chat_message("assistant"):
            if success:
                st.session_state.candidates = None
                response = f"### ✅ 找到视频！\n**📁 剧集**：{result['drama']} | **🗣️ 语言**：{result['language']}  \n**🎬 视频**：{result['video']}  \n**🔗 [点击预览]({result['video_link']})**"
                st.markdown(response)
                with st.form("form_new"):
                    if st.form_submit_button("🚀 启动 Campaign"):
                        with st.spinner("🚀 创建并激活中..."):
                            c_res = campaign_manager.create_campaign(result['drama'], result['video_link'])
                        if c_res['status'] == 'success': st.success("✅ 投流并激活成功！")
                        else: st.error(f"❌ 失败: {c_res['error']}")
            else:
                response = f"❌ {result}"
                st.markdown(response)
        st.session_state.chat_history.append({"role": "assistant", "content": response})
        st.rerun()

elif page == "📊 数据看板":
    st.title("📊 广告效果数据中心")
    
    col1, col2 = st.columns([3, 1])
    with col1: search_query = st.text_input("🔍 搜索剧名/Campaign ID", placeholder="输入关键词...")
    with col2:
        st.write("")
        if st.button("🔄 同步 Meta 深度数据", use_container_width=True):
            with st.spinner("正在抓取昨日 15 项核心指标..."):
                st.session_state.campaign_list = campaign_manager.get_all_campaigns()
                st.session_state.yesterday_insights = campaign_manager.get_yesterday_insights()

    if st.session_state.campaign_list:
        # 构建深度报表数据
        rows = []
        insights = st.session_state.yesterday_insights
        from datetime import datetime
        import pytz
        tz_beijing = pytz.timezone('Asia/Shanghai')

        for c in st.session_state.campaign_list:
            cid = c['id']
            ins = insights.get(cid, {})
            
            # 时间转换
            raw_time = c.get('start_time', '')
            if raw_time:
                try:
                    # 假设原始时间是 UTC，转换为北京时间
                    dt_utc = datetime.strptime(raw_time, "%Y-%m-%dT%H:%M:%S%z")
                    dt_beijing = dt_utc.astimezone(tz_beijing)
                    display_time = dt_beijing.strftime("%m-%d %H:%M")
                except:
                    display_time = raw_time
            else:
                display_time = "-"

            rows.append({
                "广告ID": cid,
                "广告名称": c['name'],
                "状态": c['effective_status'],
                "创建时间": display_time,
                "广告花费": ins.get('spend', 0),
                "预算": c.get('budget', 0),
                "点击量": ins.get('clicks', 0),
                "CTR": ins.get('ctr', 0),
                "安装量": ins.get('installs', 0),
                "ROI": ins.get('roi', 0),
                "CVR": ins.get('cvr', 0),
                "CPM": ins.get('cpm', 0),
                "CPC": ins.get('cpc', 0),
                "CPI": ins.get('cpi', 0),
                "CPP": ins.get('cpp', 0)
            })
        
        full_df = pd.DataFrame(rows)
        if search_query:
            full_df = full_df[full_df['广告名称'].str.contains(search_query, case=False) | full_df['广告ID'].str.contains(search_query)]

        # 汇总看板
        total_spend = full_df['广告花费'].sum()
        total_install = full_df['安装量'].sum()
        avg_roi = full_df[full_df['广告花费'] > 0]['ROI'].mean()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("昨日总消耗", f"${total_spend:,.2f}")
        m2.metric("昨日总安装", f"{int(total_install):,}")
        m3.metric("平均 ROI", f"{avg_roi:.2f}")
        m4.metric("平均 CPI", f"${(total_spend/total_install if total_install>0 else 0):.2f}")

        st.divider()
        
        # 深度报表表格
        st.subheader("📋 详细数据列表 (昨日表现)")
        st.dataframe(
            full_df,
            use_container_width=True,
            column_config={
                "广告ID": st.column_config.TextColumn("广告ID"),
                "广告名称": st.column_config.TextColumn("广告名称", width="large"),
                "创建时间": st.column_config.DatetimeColumn("创建时间", format="MM-DD HH:mm"),
                "广告花费": st.column_config.NumberColumn("花费 ($)", format="$%.2f"),
                "预算": st.column_config.NumberColumn("预算 ($)", format="$%.2f"),
                "CTR": st.column_config.NumberColumn("CTR (%)", format="%.2f%%"),
                "ROI": st.column_config.NumberColumn("ROI", format="%.2f"),
                "CVR": st.column_config.NumberColumn("CVR (%)", format="%.2f%%"),
                "CPM": st.column_config.NumberColumn("CPM ($)", format="$%.2f"),
                "CPC": st.column_config.NumberColumn("CPC ($)", format="$%.2f"),
                "CPI": st.column_config.NumberColumn("CPI ($)", format="$%.2f"),
                "CPP": st.column_config.NumberColumn("CPP ($)", format="$%.2f"),
            },
            hide_index=True
        )

        st.divider()
        st.subheader("⚙️ 状态管理")
        # 精简后的状态操作行
        for index, row in full_df.iterrows():
            cid, status = row['广告ID'], row['状态']
            c1, c2, c3, c4 = st.columns([4, 2, 1, 1])
            with c1: st.markdown(f"**{row['广告名称']}**")
            with c2: st.markdown(f"ID: `{cid}` | 状态: `{status}`")
            with c3:
                if st.button("🟢 激活", key=f"act_{cid}", use_container_width=True, disabled=(status=="ACTIVE")):
                    if campaign_manager.update_campaign_status(cid, "ACTIVE"): st.rerun()
            with c4:
                if st.button("🟡 暂停", key=f"pas_{cid}", use_container_width=True, disabled=(status=="PAUSED")):
                    if campaign_manager.update_campaign_status(cid, "PAUSED"): st.rerun()
    else:
        st.info("💡 请点击“同步 Meta 深度数据”拉取昨日详细效果报告。")

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
            st.success("✅ 策略已更新！")
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

st.markdown("<div style='text-align: center; color: #888; font-size: 12px;'>Auto Meta ADS v1.7 | 数据中心专业版</div>", unsafe_allow_html=True)
