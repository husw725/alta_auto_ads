import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def find_my_app():
    token = os.getenv('META_ACCESS_TOKEN')
    account = os.getenv('META_AD_ACCOUNT_ID')
    
    # 查询该账户下所有可用的 Application
    url = f"https://graph.facebook.com/v21.0/{account}/advertisable_applications"
    params = {'access_token': token, 'fields': 'id,name,object_store_urls'}
    
    res = requests.get(url, params=params).json()
    print("📡 [Meta 可投放应用列表]:")
    print(json.dumps(res, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    find_my_app()
