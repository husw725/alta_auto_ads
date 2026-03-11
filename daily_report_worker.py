import os
import json
import requests
import subprocess
import platform
import sys
from datetime import datetime
from core.campaign_manager import CampaignManager

def send_dingtalk_message(webhook_url, content, title="Meta 投流日报"):
    """
    内置钉钉 Markdown 发送逻辑，消除外部脚本依赖
    """
    try:
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content
            }
        }
        headers = {"Content-Type": "application/json"}
        resp = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            return True, resp.json()
        else:
            return False, f"HTTP {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, str(e)

def run_job(is_test=False):
    """日报核心逻辑 (全自研集成版: 零外部依赖)"""
    try:
        # 获取绝对路径锁定配置文件
        base_dir = os.path.abspath(os.path.dirname(__file__))
        config_path = os.path.join(base_dir, 'config', 'config.json')
        
        if not os.path.exists(config_path):
            print(f"❌ 配置文件不存在: {config_path}")
            return
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        report_cfg = config.get('report', {})
        if not report_cfg.get('enabled') and not is_test:
            return

        # 1. 初始化核心
        cm = CampaignManager()
        campaigns = cm.get_all_campaigns()
        insights = cm.get_yesterday_insights()
        history = cm.get_historical_insights()
        
        # 2. 智能调优 (2.0 逻辑)
        pending_actions = cm.evaluate_optimization_rules(campaigns, insights, history)
        executed_log = ""
        awaiting_approval_log = ""
        
        for act in pending_actions:
            if act.get('risk'):
                awaiting_approval_log += f"- ⚠️ **待手动确认**: {act['name']} ({act['reason']})\n"
            else:
                if cm.execute_action(act):
                    executed_log += f"- ✅ 已自动执行: {act['type']} - {act['name']} ({act['reason']})\n"
        
        if not executed_log: executed_log = "- ✨ 暂无低风险自动调优动作。\n"
        if not awaiting_approval_log: awaiting_approval_log = "- ✅ 暂无高风险需人工确认项。\n"

        # 3. 数据汇总
        total_spend = sum(ins.get('spend', 0) for ins in insights.values())
        total_installs = sum(ins.get('installs', 0) for ins in insights.values())
        avg_cpi = total_spend / total_installs if total_installs > 0 else 0
        
        # 4. 构建报表 (仅展示激活中的 Top 5)
        details = ""
        # 🚀 改进：只筛选正在运行的广告进入详情列表
        active_campaigns = [c for c in campaigns if c.get('effective_status') == 'ACTIVE']
        sorted_c = sorted(active_campaigns, key=lambda x: insights.get(x['id'], {}).get('spend', 0), reverse=True)
        
        for c in sorted_c[:5]:
            ins = insights.get(c['id'], {})
            details += f"**{c['name']}**\n"
            details += f"- 消耗: `${ins.get('spend',0):.2f}` | 安装: `{ins.get('installs',0)}` | CPI: `${ins.get('cpi',0):.2f}`\n\n"

        if not details: details = "_今日暂无运行中的重点项目_\n"

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
*Auto Meta ADS v2.8.0 · 零依赖全集成版*
"""

        # 5. 🚀 核心改进：直接使用内置发送逻辑
        webhook = report_cfg.get('webhook_url')
        if webhook:
            success, msg = send_dingtalk_message(webhook, report_md)
            if success:
                config['report']['last_sent'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                print(f"✅ 日报成功送达钉钉")
            else:
                print(f"❌ 钉钉发送失败: {msg}")
                
    except Exception as e:
        print(f"❌ run_job 发生异常: {e}")

if __name__ == "__main__":
    import sys
    run_job(is_test="--test" in sys.argv)
