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
    history = cm.get_historical_insights()
    
    # --- 智能调优 (2.0 逻辑) ---
    pending_actions = cm.evaluate_optimization_rules(campaigns, insights, history)
    executed_log = ""
    awaiting_approval_log = ""
    
    for act in pending_actions:
        # 高风险动作不自动执行，只在日报提醒
        if act.get('risk'):
            awaiting_approval_log += f"- ⚠️ **待手动确认**: {act['name']} ({act['reason']})\n"
        else:
            if cm.execute_action(act):
                executed_log += f"- ✅ 已自动执行: {act['type']} - {act['name']} ({act['reason']})\n"
    
    if not executed_log: executed_log = "- ✨ 暂无低风险自动调优动作。\n"
    if not awaiting_approval_log: awaiting_approval_log = "- ✅ 暂无高风险需人工确认项。\n"

    # --- 数据汇总 ---
    total_spend = sum(ins.get('spend', 0) for ins in insights.values())
    total_installs = sum(ins.get('installs', 0) for ins in insights.values())
    avg_cpi = total_spend / total_installs if total_installs > 0 else 0
    
    # --- 构建报表 ---
    details = ""
    sorted_c = sorted(campaigns, key=lambda x: insights.get(x['id'], {}).get('spend', 0), reverse=True)
    for c in sorted_c[:5]:
        ins = insights.get(c['id'], {})
        details += f"**{c['name']}**\n"
        details += f"- 消耗: `${ins.get('spend',0):.2f}` | 安装: `{ins.get('installs',0)}` | CPI: `${ins.get('cpi',0):.2f}` | ROI: `{ins.get('roi',0):.2f}`\n\n"

    report_md = f"""# 📊 Meta 投流智能调优日报
> 📅 日期: {datetime.now().strftime('%Y-%m-%d')}

## 📈 整体表现
- **总消耗**: `${total_spend:.2f}`
- **总安装**: `{total_installs}`
- **平均 CPI**: `${avg_cpi:.2f}`

---

## 🤖 自动执行记录 (Safe)
{executed_log}

---

## 🛑 需您人工审批 (High Risk)
{awaiting_approval_log}
> 💡 请前往 [龙虾AI数据看板] 批准或忽略以上高风险操作。

---

## 🔍 重点项目 (Top 5)
{details}

---
*Auto Meta ADS v2.4.0 · 智能风控引擎已就绪*
"""

    webhook = report_cfg.get('webhook_url')
    if webhook:
        cmd = ["python3", "/Users/husw/.gemini/skills/dingtalk-sender/scripts/send.py", webhook, report_md]
        subprocess.run(cmd)

if __name__ == "__main__":
    import sys
    run_job("--test" in sys.argv)
