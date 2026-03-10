import os
import json
import requests
import subprocess
from datetime import datetime
from core.campaign_manager import CampaignManager

def run_job(is_test=False):
    # 1. 加载配置
    config_path = 'config/config.json'
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    report_cfg = config.get('report', {})
    if not report_cfg.get('enabled') and not is_test:
        return

    # 2. 获取数据与执行自动优化
    cm = CampaignManager()
    campaigns = cm.get_all_campaigns()
    insights = cm.get_yesterday_insights()
    
    # 🚀 [核心升级]：日报前自动执行调优逻辑
    pending_actions = cm.evaluate_optimization_rules(campaigns, insights)
    executed_log = ""
    if pending_actions:
        for act in pending_actions:
            if cm.execute_action(act):
                executed_log += f"- ✅ 已自动暂停: **{act['name']}** (原因: {act['reason']})\n"
    
    if not executed_log:
        executed_log = "- ✨ 昨日所有广告表现均在阈值内，无需干预。\n"

    # 3. 计算汇总
    total_spend = sum(ins.get('spend', 0) for ins in insights.values())
    total_installs = sum(ins.get('installs', 0) for ins in insights.values())
    avg_cpi = total_spend / total_installs if total_installs > 0 else 0
    
    # 4. 构建分析报表
    details = ""
    sorted_c = sorted(campaigns, key=lambda x: insights.get(x['id'], {}).get('spend', 0), reverse=True)
    for c in sorted_c[:10]:
        ins = insights.get(c['id'], {'spend': 0, 'installs': 0, 'cpi': 0})
        status_icon = "🟢" if c['effective_status'] == 'ACTIVE' else "🟡"
        details += f"**{c['name']}**\n"
        details += f"- 状态: {status_icon} | 消耗: `${ins['spend']:.2f}` | 安装: `{ins['installs']}` | CPI: `${ins['cpi']:.2f}`\n\n"

    report_md = f"""# 📊 Meta 投流昨日深度日报
> 📅 日期: {datetime.now().strftime('%Y-%m-%d')}

## 📈 整体表现
- **总消耗**: `${total_spend:.2f}`
- **总安装**: `{total_installs}`
- **平均 CPI**: `${avg_cpi:.2f}`

---

## 🤖 自动调优战报
{executed_log}

---

## 🔍 重点剧集详情 (Top 10)
{details}

---
*Auto Meta ADS · 智能风控引擎已介入*
"""

    # 5. 发送
    webhook = report_cfg.get('webhook_url')
    if webhook:
        cmd = ["python3", "/Users/husw/.gemini/skills/dingtalk-sender/scripts/send.py", webhook, report_md]
        subprocess.run(cmd)
        print(f"Report sent with {len(pending_actions)} actions.")

if __name__ == "__main__":
    import sys
    run_job(is_test="--test" in sys.argv)
