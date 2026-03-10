import os
import requests
import json
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        # Meta 官方 App ID
        self.meta_app_id = "1807921329643155"
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

            # 1. Video
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            if 'id' not in v_resp: return {'status': 'error', 'error': f"Step 1 Video Fail: {v_resp}"}
            v_id = v_resp['id']

            # 2. Campaign (合并预算到系列层级，启用 CBO 模式)
            c_payload = {
                'name': name_base,
                'objective': 'OUTCOME_APP_PROMOTION',
                'status': 'PAUSED',
                'special_ad_categories': json.dumps(['NONE']),
                'daily_budget': budget * 100, # 恢复标准 50 刀预算
                'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', # 自动出价
                'access_token': token
            }
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data=c_payload).json()
            if 'id' not in c_resp: return {'status': 'error', 'error': f"Step 2 Campaign Fail: {c_resp}"}
            c_id = c_resp['id']

            # 3. AdSet
            as_payload = {
                'name': f"{name_base}-AS",
                'campaign_id': c_id,
                'optimization_goal': 'APP_INSTALLS',
                'destination_type': 'APP',
                'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({'application_id': self.meta_app_id}),
                'targeting': json.dumps({'geo_locations': {'countries': [cfg.get('country', 'US')]}, 'device_platforms': ['mobile']}),
                'status': 'PAUSED',
                'access_token': token
            }
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data=as_payload).json()
            if 'id' not in as_resp: return {'status': 'error', 'error': f"Step 3 AdSet Fail: {as_resp}"}
            as_id = as_resp['id']

            # 4. Creative
            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy = writer.generate_copy(drama_name).get('versions', [{}])[0]
            story_spec = {
                'page_id': self.page_id,
                'video_data': {'video_id': v_id, 'message': copy.get('primary_text', 'Watch now on AltaTV!')}
            }
            cr_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={
                'name': f"{name_base}-Cr",
                'object_story_spec': json.dumps(story_spec),
                'access_token': token
            }).json()
            if 'id' not in cr_resp: return {'status': 'error', 'error': f"Step 4 Creative Fail: {cr_resp}"}
            cr_id = cr_resp['id']

            # 5. Ad
            ad_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={
                'name': f"{name_base}-Ad",
                'adset_id': as_id,
                'creative': json.dumps({'creative_id': cr_id}),
                'status': 'PAUSED',
                'access_token': token
            }).json()
            if 'id' not in ad_resp: return {'status': 'error', 'error': f"Step 5 Ad Fail: {ad_resp}"}

            return {'status': 'success', 'campaign_id': c_id}
        except Exception as e:
            return {'status': 'error', 'error': f"Critical: {str(e)}"}

    def get_all_campaigns(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/campaigns"
            params = {'fields': 'id,name,status,effective_status,start_time,daily_budget', 'access_token': self.access_token, 'limit': 50}
            resp = requests.get(url, params=params).json()
            return resp.get('data', [])
        except: return []

    def update_campaign_status(self, cid, status):
        try: return requests.post(f"{self.base_url}/{cid}", data={'status': status, 'access_token': self.access_token}).json().get('success', False)
        except: return False

    def get_yesterday_insights(self): return {}
