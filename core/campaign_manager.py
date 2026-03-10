import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """Meta ADS 管理器 v2.0.0: 100% 复刻 v1.0.0 逻辑版"""
    
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        self.pixel_id = os.getenv('META_PIXEL_ID')
        self.base_url = "https://graph.facebook.com/v21.0"
        self.media_buyer = "Auto ADS"

    def _load_dynamic_config(self):
        try:
            with open('config/config.json', 'r') as f:
                return json.load(f).get('default', {})
        except:
            return {"country": "US", "daily_budget": 50, "optimization_goal": "MOBILE_APP_INSTALLS"}

    def create_campaign(self, drama_name, video_url, thumb_url=None):
        """100% 复刻 v1.0.0 创建逻辑 (仅保留 v21.0 必填分类)"""
        try:
            cfg = self._load_dynamic_config()
            country = cfg.get('country', 'US')
            budget = float(cfg.get('daily_budget', 50.0))
            goal = cfg.get('optimization_goal', 'MOBILE_APP_INSTALLS')
            
            today = datetime.now().strftime("%Y%m%d%H%M")
            name_base = f"{drama_name}-{country}-{today}-Auto-{self.media_buyer}"
            token = self.access_token

            # 1. Upload Video
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            if 'id' not in v_resp: return {'status': 'error', 'error': f"Video upload failed: {v_resp}"}
            v_id = v_resp['id']
            
            # 2. Create Campaign (回归 v1.0.0 的 OUTCOME_SALES)
            c_payload = {
                'name': name_base, 
                'objective': 'OUTCOME_SALES', 
                'status': 'PAUSED',
                'special_ad_categories': json.dumps(['NONE']), # v21.0 必须保留
                'access_token': token
            }
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data=c_payload).json()
            if 'id' not in c_resp: return {'status': 'error', 'error': f"Campaign fail: {c_resp}"}
            c_id = c_resp['id']
            
            # 3. Create AdSet (回归 v1.0.0: 预算回到这里)
            as_payload = {
                'name': f"{name_base}-AS",
                'campaign_id': c_id,
                'daily_budget': int(budget * 100), # 预算回到广告组
                'optimization_goal': 'OFFSITE_CONVERSIONS',
                'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({
                    'pixel_id': self.pixel_id, 
                    'custom_event_type': 'CONTENT_VIEW' if goal == 'CONTENT_VIEW' else 'MOBILE_APP_INSTALLS'
                }),
                'targeting': json.dumps({'geo_locations': {'countries': [country]}, 'device_platforms': ['mobile']}),
                'status': 'PAUSED',
                'access_token': token
            }
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data=as_payload).json()
            if 'id' not in as_resp: return {'status': 'error', 'error': f"AdSet fail: {as_resp}"}
            as_id = as_resp['id']
            
            # 4. Creative & Ad (复刻 v1.0.0: 极简结构)
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
                'name': f"{name_base}-Cr", 
                'object_story_spec': json.dumps(story_spec), 
                'access_token': token
            }).json()
            cr_id = cr_resp.get('id')
            if not cr_id: return {'status': 'error', 'error': f"Creative fail: {cr_resp}"}
            
            ad_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={
                'name': f"{name_base}-Ad", 
                'adset_id': as_id, 
                'creative': json.dumps({'creative_id': cr_id}), 
                'status': 'PAUSED', 
                'access_token': token
            }).json()
            if 'id' not in ad_resp: return {'status': 'error', 'error': f"Ad fail: {ad_resp}"}

            # 5. 自动激活逻辑 (按需补发)
            requests.post(f"{self.base_url}/{c_id}", data={'status': 'ACTIVE', 'access_token': token})
            requests.post(f"{self.base_url}/{as_id}", data={'status': 'ACTIVE', 'access_token': token})
            requests.post(f"{self.base_url}/{ad_resp['id']}", data={'status': 'ACTIVE', 'access_token': token})
            
            return {'status': 'success', 'campaign_id': c_id}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def get_all_campaigns(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/campaigns"
            params = {'fields': 'id,name,status,effective_status,start_time,objective', 'access_token': self.access_token, 'limit': 50}
            resp = requests.get(url, params=params).json()
            return sorted(resp.get('data', []), key=lambda x: x.get('start_time', '0'), reverse=True)
        except: return []

    def update_campaign_status(self, cid, status):
        try: return requests.post(f"{self.base_url}/{cid}", data={'status': status, 'access_token': self.access_token}).json().get('success', False)
        except: return False

    def get_yesterday_insights(self): return {}
    def evaluate_optimization_rules(self, camps, ins, hist): return []
