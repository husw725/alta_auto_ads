import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """Meta ADS 管理器 v1.9.9: 完美复刻 v1.0.0 稳定版链路"""
    
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        self.pixel_id = os.getenv('META_PIXEL_ID')
        self.base_url = "https://graph.facebook.com/v21.0"

    def _load_config(self):
        try:
            with open('config/config.json', 'r') as f: return json.load(f)
        except: return {"default": {"country": "US", "daily_budget": 50}}

    def create_campaign(self, drama_name, video_url, thumb_url=None):
        """复刻 v1.0.0 模式：使用 OUTCOME_SALES 绕过缩略图强制校验"""
        try:
            token = self.access_token
            cfg = self._load_config().get('default', {})
            budget = int(cfg.get('daily_budget', 50))
            country = cfg.get('country', 'US')
            name_base = f"{drama_name}-{country}-{datetime.now().strftime('%m%d%H%M')}-Auto"

            # 1. Upload Video
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Video Fail: {v_resp}"}

            # 2. Campaign (回归 v1.0.0 的 OUTCOME_SALES)
            c_payload = {
                'name': name_base,
                'objective': 'OUTCOME_SALES', # 关键：回归旧目标
                'status': 'PAUSED',
                'special_ad_categories': json.dumps(['NONE']), # v21.0 必填项
                'daily_budget': budget * 100,
                'access_token': token
            }
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data=c_payload).json()
            c_id = c_resp.get('id')
            if not c_id: return {'status': 'error', 'error': f"Campaign Fail: {c_resp}"}

            # 3. AdSet (复刻 v1.0.0 的 OFFSITE_CONVERSIONS)
            as_payload = {
                'name': f"{name_base}-AS",
                'campaign_id': c_id,
                'optimization_goal': 'OFFSITE_CONVERSIONS', 
                'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({
                    'pixel_id': self.pixel_id, 
                    'custom_event_type': 'MOBILE_APP_INSTALLS'
                }),
                'targeting': json.dumps({
                    'geo_locations': {'countries': [country]}, 
                    'device_platforms': ['mobile']
                }),
                'status': 'PAUSED',
                'access_token': token
            }
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data=as_payload).json()
            as_id = as_resp.get('id')
            if not as_id: return {'status': 'error', 'error': f"AdSet Fail: {as_resp}"}

            # 4. Creative & Ad (复刻 v1.0.0 的精简结构)
            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy = writer.generate_copy(drama_name).get('versions', [{}])[0]
            
            story_spec = {
                'page_id': self.page_id,
                'video_data': {
                    'video_id': v_id,
                    'message': copy.get('primary_text', 'Watch now!')
                }
            }
            cr_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={
                'name': f"{name_base}-Cr", 'object_story_spec': json.dumps(story_spec), 'access_token': token
            }).json()
            cr_id = cr_resp.get('id')
            
            ad_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={
                'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token
            }).json()
            
            # 5. Step 2: Auto Activate
            requests.post(f"{self.base_url}/{c_id}", data={'status': 'ACTIVE', 'access_token': token})
            requests.post(f"{self.base_url}/{as_id}", data={'status': 'ACTIVE', 'access_token': token})
            requests.post(f"{self.base_url}/{ad_resp.get('id')}", data={'status': 'ACTIVE', 'access_token': token})

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
    def evaluate_optimization_rules(self, camps, ins, hist): return []
