import os
import json
import requests
import subprocess
from datetime import datetime
from core.campaign_manager import CampaignManager

def run_job(is_test=False):
    # 1. 加载配置
    with open('config/config.json', 'r') as f:
        config = json.load(f)
    
    report_cfg = config.get('report', {})
    if not report_cfg.get('enabled') and not is_test:
        print("Report is disabled.")
        return

    # 2. 获取数据
    cm = CampaignManager()
    insights = cm.get_yesterday_insights()
    campaigns = cm.get_all_campaigns()
    
    # 3. 计算汇总
    total_spend = sum(ins['spend'] for ins in insights.values())
    total_conv = sum(ins['conversions'] for ins in insights.values())
    avg_cpi = total_spend / total_conv if total_conv > 0 else 0
    
    # 4. 构建分析报表 (手机端优化版)
    details = ""
    # 只显示昨日有消耗的或者最近的 10 条
    sorted_c = sorted(campaigns, key=lambda x: insights.get(x['id'], {}).get('spend', 0), reverse=True)
    
    for c in sorted_c[:10]:
        ins = insights.get(c['id'], {'spend': 0, 'conversions': 0, 'cpi': 0})
        status_icon = "🟢" if c['effective_status'] == 'ACTIVE' else "🟡"
        details += f"**{c['name']}**\n"
        details += f"- 状态: {status_icon} | 消耗: `${ins['spend']:.2f}`\n"
        details += f"- 转化: `{ins['conversions']}` | CPI: `${ins['cpi']:.2f}`\n\n"

    # AI 策略逻辑
    analysis = "#### 🧠 AI 调优建议\n"
    if total_spend > 0:
        if avg_cpi < 0.5:
            analysis += "✅ **表现优异**: 整体 CPI 低于 $0.5。建议今日对 Top 3 剧集上调 20% 预算以获取更多流量。\n"
        elif avg_cpi > 1.0:
            analysis += "⚠️ **风险预警**: 整体 CPI 偏高。建议排查昨日高成本素材，及时止损并更换新素材。\n"
        else:
            analysis += "✨ **运行平稳**: 成本符合预期。建议继续观察，并尝试小幅度测试新剧集。\n"
    else:
        analysis += "📭 **无数据**: 昨日无广告消耗。请确认是否有 Campaign 处于 Active 状态或账户余额是否充足。\n"

    report_md = f"""# 📊 Meta 投流昨日深度日报
> 📅 日期: {datetime.now().strftime('%Y-%m-%d')}

## 📈 整体表现
- **总消耗**: `${total_spend:.2f}`
- **总转化**: `{total_conv}`
- **平均 CPI**: `${avg_cpi:.2f}`

---

## 🔍 重点剧集详情
{details}

---

{analysis}

---
*Auto Meta ADS · 智能报表助手*
"""

    # 5. 发送
    webhook = report_cfg.get('webhook_url')
    if webhook:
        # 使用本地脚本发送
        cmd = ["python3", "/Users/husw/.gemini/skills/dingtalk-sender/scripts/send.py", webhook, report_md]
        subprocess.run(cmd)
        print("Report sent.")

if __name__ == "__main__":
    import sys
    is_test = "--test" in sys.argv
    run_job(is_test)
