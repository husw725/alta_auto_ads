import os
import json
import requests
import subprocess
from datetime import datetime
from core.campaign_manager import CampaignManager

def run_job(is_test=False):
    config_path = 'config/config.json'
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    report_cfg = config.get('report', {})
    if not report_cfg.get('enabled') and not is_test: return

    cm = CampaignManager()
    campaigns = cm.get_all_campaigns()
    insights = cm.get_yesterday_insights()
    
    # 自动调优
    pending_actions = cm.evaluate_optimization_rules(campaigns, insights)
    executed_log = ""
    for act in pending_actions:
        if cm.execute_action(act):
            executed_log += f"- ✅ 已自动暂停: **{act['name']}** (原因: {act['reason']})\n"
    if not executed_log: executed_log = "- ✨ 昨日表现均在阈值内，无需干预。\n"

    # 汇总
    total_spend = sum(ins.get('spend', 0) for ins in insights.values())
    total_installs = sum(ins.get('installs', 0) for ins in insights.values())
    total_clicks = sum(ins.get('clicks', 0) for ins in insights.values())
    avg_roi = sum(ins.get('roi', 0) for ins in insights.values()) / len(insights) if insights else 0
    
    # 详情 (Top 5 专业版)
    details = ""
    sorted_c = sorted(campaigns, key=lambda x: insights.get(x['id'], {}).get('spend', 0), reverse=True)
    for c in sorted_c[:5]:
        ins = insights.get(c['id'], {})
        details += f"**{c['name']}**\n"
        details += f"- 消耗: `${ins.get('spend',0):.2f}` | 预算: `${float(c.get('daily_budget',0))/100:.0f}`\n"
        details += f"- 安装: `{ins.get('installs',0)}` | CPI: `${ins.get('cpi',0):.2f}` | ROI: `{ins.get('roi',0):.2f}`\n"
        details += f"- 点击: `{ins.get('clicks',0)}` | CTR: `{ins.get('ctr',0)*100:.2f}%` | CVR: `{ins.get('cvr',0)*100:.2f}%`\n"
        details += f"- CPC: `${ins.get('cpc',0):.2f}` | CPM: `${ins.get('cpm',0):.2f}` | CPP: `${ins.get('cpp',0):.2f}`\n\n"

    report_md = f"""# 📊 Meta 投流专业日报
> 📅 日期: {datetime.now().strftime('%Y-%m-%d')}

## 📈 整体概览
- **总消耗**: `${total_spend:.2f}`
- **总安装**: `{total_installs}`
- **总点击**: `{total_clicks}`
- **平均 ROI**: `{avg_roi:.2f}`

---

## 🤖 自动调优
{executed_log}

---

## 🔍 核心项目 (Top 5)
{details}

---
*Auto Meta ADS · 专业投流决策助手*
"""

    webhook = report_cfg.get('webhook_url')
    if webhook:
        cmd = ["python3", "/Users/husw/.gemini/skills/dingtalk-sender/scripts/send.py", webhook, report_md]
        subprocess.run(cmd)
        print(f"Report sent with all metrics.")

if __name__ == "__main__":
    import sys
    run_job("--test" in sys.argv)
