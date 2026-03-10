import os
import requests
import json
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """Meta ADS 管理器 v1.9.3: 全字段合规版 (对齐 v23.0 标准)"""
    
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        # 官方锁定的 ID 和 URL
        self.meta_app_id = "1807921329643155"
        self.official_store_url = "http://itunes.apple.com/app/id6469592412"
        self.base_url = "https://graph.facebook.com/v21.0"

    def _load_config(self):
        try:
            with open('config/config.json', 'r') as f: return json.load(f)
        except: return {"default": {"country": "US", "daily_budget": 50}}

    def create_campaign(self, drama_name, video_url):
        try:
            token = self.access_token
            cfg = self._load_config().get('default', {})
            budget = int(cfg.get('daily_budget', 50))
            name_base = f"{drama_name}-{cfg.get('country', 'US')}-{datetime.now().strftime('%m%d%H%M')}"

            # 1. Video Upload
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Video Fail: {v_resp}"}

            # 2. Campaign (CBO 模式)
            c_payload = {
                'name': name_base, 
                'objective': 'OUTCOME_APP_PROMOTION', 
                'status': 'PAUSED',
                'special_ad_categories': json.dumps(['NONE']), 
                'daily_budget': budget * 100,
                'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 
                'access_token': token
            }
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data=c_payload).json()
            c_id = c_resp.get('id')
            if not c_id: return {'status': 'error', 'error': f"Campaign Fail: {c_resp}"}

            # 3. AdSet (操作系统对齐 + 目的地对齐)
            as_payload = {
                'name': f"{name_base}-AS", 
                'campaign_id': c_id, 
                'optimization_goal': 'APP_INSTALLS',
                'destination_type': 'APP', 
                'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({
                    'application_id': self.meta_app_id,
                    'object_store_url': self.official_store_url
                }),
                'targeting': json.dumps({
                    'geo_locations': {'countries': [cfg.get('country', 'US')]}, 
                    'device_platforms': ['mobile'],
                    'user_os': ['iOS'] # 必须指定 iOS
                }),
                'status': 'PAUSED', 
                'access_token': token
            }
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data=as_payload).json()
            as_id = as_resp.get('id')
            if not as_id: return {'status': 'error', 'error': f"AdSet Fail: {as_resp}"}

            # 4. AdCreative (补全 CTA、Headline 等所有必填版块)
            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy = writer.generate_copy(drama_name).get('versions', [{}])[0]
            
            # 重要：构建完整的 story_spec，包含 CTA 和标题
            story_spec = {
                'page_id': self.page_id,
                'video_data': {
                    'video_id': v_id,
                    'message': copy.get('primary_text', 'Watch the latest drama now!'), # 广告正文
                    'title': copy.get('headline', f"Watch {drama_name}"), # 强制要求：广告标题 (Headline)
                    'call_to_action': {
                        'type': 'INSTALL_APP', # 修正为报错中允许的正确枚举值
                        'value': {
                            'link': self.official_store_url
                        }
                    }
                }
            }
            
            cr_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={
                'name': f"{name_base}-Cr",
                'object_story_spec': json.dumps(story_spec),
                'access_token': token
            }).json()
            cr_id = cr_resp.get('id')
            if not cr_id: return {'status': 'error', 'error': f"Creative Fail: {cr_resp}"}
            
            # 5. Ad
            ad_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={
                'name': f"{name_base}-Ad",
                'adset_id': as_id,
                'creative': json.dumps({'creative_id': cr_id}),
                'status': 'PAUSED',
                'access_token': token
            }).json()
            if 'id' not in ad_resp: return {'status': 'error', 'error': f"Ad Fail: {ad_resp}"}

            # 6. Auto Activate
            requests.post(f"{self.base_url}/{c_id}", data={'status': 'ACTIVE', 'access_token': token})
            requests.post(f"{self.base_url}/{as_id}", data={'status': 'ACTIVE', 'access_token': token})
            requests.post(f"{self.base_url}/{ad_resp['id']}", data={'status': 'ACTIVE', 'access_token': token})

            return {'status': 'success', 'campaign_id': c_id}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def get_all_campaigns(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/campaigns"
            params = {'fields': 'id,name,status,effective_status,start_time,daily_budget,objective', 'access_token': self.access_token, 'limit': 50}
            resp = requests.get(url, params=params).json()
            return sorted(resp.get('data', []), key=lambda x: x.get('start_time', '0'), reverse=True)
        except: return []

    def update_campaign_status(self, cid, status):
        try: return requests.post(f"{self.base_url}/{cid}", data={'status': status, 'access_token': self.access_token}).json().get('success', False)
        except: return False

    def get_yesterday_insights(self): return {}
    def get_historical_insights(self, days=7): return {}
    def evaluate_optimization_rules(self, camps, ins, hist): return []
    def execute_action(self, act): return False
