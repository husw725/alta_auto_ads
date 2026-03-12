import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def probe_meta():
    token = os.getenv('META_ACCESS_TOKEN')
    account = os.getenv('META_AD_ACCOUNT_ID')
    pixel = os.getenv('META_PIXEL_ID')
    app_link = os.getenv('META_APP_LINK')
    
    print(f"🔍 [检查配置状态]")
    print(f"  - 账户 ID: {account}")
    print(f"  - 像素 ID: {pixel}")
    print(f"  - App 链接: {app_link}")
    
    # 1. 检查 Token 有效性
    me_url = f"https://graph.facebook.com/v21.0/me?access_token={token}"
    res = requests.get(me_url).json()
    if 'error' in res:
        print(f"❌ Token 无效: {res['error']['message']}")
        return
    print(f"✅ Token 有效，用户: {res.get('name')}")

    # 2. 检查账户权限
    acc_url = f"https://graph.facebook.com/v21.0/{account}?fields=name,account_status,currency&access_token={token}"
    res = requests.get(acc_url).json()
    if 'error' in res:
        print(f"❌ 账户访问失败: {res['error']['message']}")
        return
    print(f"✅ 账户状态正常: {res.get('name')} (状态:{res.get('account_status')}, 币种:{res.get('currency')})")

    # 3. 核心探测：尝试模拟一个最轻量的 AdSet 参数校验 (不真正创建)
    # 这能直接告诉我们 Meta 到底想要什么参数
    validate_url = f"https://graph.facebook.com/v21.0/{account}/adsets"
    test_payload = {
        'name': 'PROBE_TEST',
        'optimization_goal': 'APP_INSTALLS',
        'billing_event': 'IMPRESSIONS',
        'status': 'PAUSED',
        'access_token': token,
        'execution_options': '["validate_only"]' # 关键：只校验，不扣钱不创建
    }
    res = requests.post(validate_url, data=test_payload).json()
    print(f"\n🧪 [Meta 核心参数诊断报告]:")
    print(json.dumps(res, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    probe_meta()
