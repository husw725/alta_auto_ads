import os
import requests
import json
import traceback
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        self.pixel_id = os.getenv('META_PIXEL_ID')
        self.app_link = os.getenv('META_APP_LINK')
        self.base_url = "https://graph.facebook.com/v21.0"

    def create_campaign(self, drama_name, video_url):
        """创建 Campaign (具备极端日志能力的诊断版)"""
        try:
            # 0. 输入完整性检查
            if not drama_name: return {'status': 'error', 'error': 'Input Error: drama_name is empty'}
            if not video_url: return {'status': 'error', 'error': 'Input Error: video_url is empty'}
            
            token = self.access_token
            name_base = f"{drama_name}-{datetime.now().strftime('%m%d%H%M')}"

            # 1. Video
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Step 1 Video Failed: {v_resp}"}

            # 2. Campaign
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={'name': name_base, 'objective': 'OUTCOME_SALES', 'status': 'PAUSED', 'access_token': token}).json()
            c_id = c_resp.get('id')
            if not c_id: return {'status': 'error', 'error': f"Step 2 Campaign Failed: {c_resp}"}

            # 3. AdSet
            as_payload = {
                'name': f"{name_base}-AS",
                'campaign_id': c_id,
                'daily_budget': 5000, # 默认 $50
                'optimization_goal': 'OFFSITE_CONVERSIONS',
                'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({'pixel_id': self.pixel_id, 'custom_event_type': 'MOBILE_APP_INSTALLS'}),
                'targeting': json.dumps({'geo_locations': {'countries': ['US']}, 'device_platforms': ['mobile']}),
                'status': 'PAUSED',
                'access_token': token
            }
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data=as_payload).json()
            as_id = as_resp.get('id')
            if not as_id: return {'status': 'error', 'error': f"Step 3 AdSet Failed: {as_resp}"}

            # 4. Creative
            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy = writer.generate_copy(drama_name).get('versions', [{}])[0]
            story_spec = {'page_id': self.page_id, 'video_data': {'video_id': v_id, 'message': copy.get('primary_text', 'Watch now!')}}
            cr_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={'name': f"{name_base}-Cr", 'object_story_spec': json.dumps(story_spec), 'access_token': token}).json()
            cr_id = cr_resp.get('id')
            if not cr_id: return {'status': 'error', 'error': f"Step 4 Creative Failed: {cr_resp}"}

            # 5. Ad
            ad_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token}).json()
            ad_id = ad_resp.get('id')
            if not ad_id: return {'status': 'error', 'error': f"Step 5 Ad Failed: {ad_resp}"}

            return {'status': 'success', 'campaign_id': c_id}

        except Exception as e:
            return {'status': 'error', 'error': f"CRITICAL: {str(e)}", 'traceback': traceback.format_exc()}

    def get_all_campaigns(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/campaigns"
            params = {'fields': 'id,name,status,effective_status,start_time', 'access_token': self.access_token, 'limit': 50}
            resp = requests.get(url, params=params).json()
            return resp.get('data', [])
        except: return []

    def get_yesterday_insights(self):
        return {}
