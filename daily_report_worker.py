import os
import json
import requests
from datetime import datetime
from core.campaign_manager import CampaignManager

def run_job(is_test=False):
    # 1. 加载配置
    config_path = 'config/config.json'
    if not os.path.exists(config_path): return
    with open(config_path, 'r') as f: config = json.load(f)
    
    report_cfg = config.get('report', {})
    if not report_cfg.get('enabled') and not is_test: return
    
    manager = CampaignManager()
    
    # 2. 获取数据
    print("🔍 正在抓取数据并分析趋势...")
    camps = manager.get_all_campaigns()
    insights = manager.get_yesterday_insights()
    history = manager.get_historical_insights()
    
    # 3. 运行规则引擎并执行自动化优化
    print("🤖 正在执行策略优化...")
    actions = manager.evaluate_optimization_rules(camps, insights, history)
    executed_list = []
    pending_list = []
    
    for act in actions:
        if not act.get('high_risk'):
            if manager.execute_action(act):
                executed_list.append(f"✅ {act['type']}: {act['name']} ({act['reason']})")
        else:
            pending_list.append(f"🚨 {act['type']} (待确认): {act['name']} ({act['reason']})")

    # 4. 汇总日报数据
    total_spend = sum(ins.get('spend', 0) for ins in insights.values())
    total_install = sum(ins.get('installs', 0) for ins in insights.values())
    avg_roi = sum(ins.get('roi', 0) for ins in insights.values()) / len(insights) if insights else 0
    
    # 5. 组装 Markdown 消息
    msg = f"### 📊 Meta ADS 每日优化日报 ({datetime.now().strftime('%m-%d')})\n\n"
    msg += f"#### 📈 昨日战况汇总\n"
    msg += f"- **总消耗**: `${total_spend:,.2f}`\n"
    msg += f"- **总安装**: `{total_install:,}`\n"
    msg += f"- **平均 ROI**: `{avg_roi:.2f}`\n"
    msg += f"- **平均 CPI**: `${(total_spend/total_install if total_install>0 else 0):.2f}`\n\n"
    
    if executed_list:
        msg += f"#### 🤖 Agent 已自动执行 ({len(executed_list)}项)\n"
        for item in executed_list: msg += f"- {item}\n"
        msg += "\n"
        
    if pending_list:
        msg += f"#### 🚨 需人工审批建议 ({len(pending_list)}项)\n"
        for item in pending_list: msg += f"- {item}\n"
        msg += f"\n👉 [点击进入看板进行确认](http://localhost:8501)\n"
    else:
        msg += f"✅ 目前账号状态健康，暂无高风险操作建议。\n"

    # 6. 推送到 DingTalk
    webhook = report_cfg.get('webhook_url')
    if webhook:
        payload = {"msgtype": "markdown", "markdown": {"title": "Meta ADS 优化日报", "content": msg}}
        requests.post(webhook, json=payload)
        print("🚀 日报已推送至 DingTalk")
    else:
        print("⚠️ 未配置 Webhook，日报内容如下：\n", msg)

if __name__ == "__main__":
    run_job()
