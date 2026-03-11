import os
import json
import requests
import subprocess
import platform
from datetime import datetime
from core.campaign_manager import CampaignManager

def run_job(is_test=False):
    """日报核心逻辑 (全平台自适应版)"""
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
        if not os.path.exists(config_path): return
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        report_cfg = config.get('report', {})
        if not report_cfg.get('enabled') and not is_test: return

        # 1. 获取数据
        cm = CampaignManager()
        campaigns = cm.get_all_campaigns()
        insights = cm.get_yesterday_insights()
        history = cm.get_historical_insights()
        
        # 2. 调优逻辑
        pending_actions = cm.evaluate_optimization_rules(campaigns, insights, history)
        executed_log = ""
        awaiting_approval_log = ""
        for act in pending_actions:
            if act.get('risk'): awaiting_approval_log += f"- ⚠️ **待确认**: {act['name']} ({act['reason']})\n"
            else:
                if cm.execute_action(act): executed_log += f"- ✅ 已执行: {act['type']} - {act['name']}\n"
        
        if not executed_log: executed_log = "- ✨ 暂无自动调优动作。\n"
        if not awaiting_approval_log: awaiting_approval_log = "- ✅ 暂无高风险项。\n"

        # 3. 汇总与详情
        total_spend = sum(ins.get('spend', 0) for ins in insights.values())
        total_installs = sum(ins.get('installs', 0) for ins in insights.values())
        avg_cpi = total_spend / total_installs if total_installs > 0 else 0
        
        details = ""
        sorted_c = sorted(campaigns, key=lambda x: insights.get(x['id'], {}).get('spend', 0), reverse=True)
        for c in sorted_c[:5]:
            ins = insights.get(c['id'], {})
            details += f"**{c['name']}**\n- 消耗: `${ins.get('spend',0):.2f}` | 安装: `{ins.get('installs',0)}` | CPI: `${ins.get('cpi',0):.2f}`\n\n"

        report_md = f"# 📊 Meta 智能调优日报\n> 📅 {datetime.now().strftime('%Y-%m-%d')}\n\n## 📈 表现: Spend `${total_spend:.2f}` | Install `{total_installs}` | Avg CPI `${avg_cpi:.2f}`\n\n## 🤖 调优战报\n{executed_log}\n## 🛑 需审批\n{awaiting_approval_log}\n## 🔍 Top 5 详情\n{details}\n---\n*Auto Meta ADS v2.5.4*"

        # 🚀 4. 全平台自适应发送逻辑
        webhook = report_cfg.get('webhook_url')
        if webhook:
            # 根据系统选择 python 命令
            py_cmd = "python" if platform.system() == "Windows" else "python3"
            
            # 自动定位发送脚本 (兼容 Windows 和 macOS)
            home = os.path.expanduser("~")
            sender_path = os.path.join(home, ".gemini", "skills", "dingtalk-sender", "scripts", "send.py")
            
            if not os.path.exists(sender_path):
                print(f"❌ 找不到发送脚本: {sender_path}")
                return

            cmd = [py_cmd, sender_path, webhook, report_md]
            res = subprocess.run(cmd, capture_output=True, text=True)
            
            if res.returncode == 0:
                config['report']['last_sent'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                with open(config_path, 'w') as f: json.dump(config, f, indent=2)
                print(f"✅ 日报成功送达钉钉")
            else:
                print(f"❌ 发送失败: {res.stderr}")
                
    except Exception as e:
        print(f"❌ run_job 崩溃: {e}")

if __name__ == "__main__":
    import sys
    run_job(is_test="--test" in sys.argv)
