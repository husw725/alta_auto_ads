import os
import requests
import json
import traceback
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        self.pixel_id = os.getenv('META_PIXEL_ID')
        self.app_link = os.getenv('META_APP_LINK', '')
        # 从链接提取 App ID
        self.app_id = self._extract_app_id(self.app_link)
        self.base_url = "https://graph.facebook.com/v21.0"

    def _extract_app_id(self, url):
        match = re.search(r'id(\d+)', url)
        return match.group(1) if match else ""

    def create_campaign(self, drama_name, video_url):
        """创建 Campaign (修复 Objective 与 Promoted Object 匹配问题)"""
        try:
            token = self.access_token
            name_base = f"{drama_name}-{datetime.now().strftime('%m%d%H%M')}"

            # 1. Video
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            if 'id' not in v_resp: return {'status': 'error', 'error': v_resp, 'step': 'Step 1: Video'}
            v_id = v_resp['id']

            # 2. Campaign (切换到标准的 APP_PROMOTION 目标)
            c_data = {
                'name': name_base,
                'objective': 'OUTCOME_APP_PROMOTION',
                'status': 'PAUSED',
                'special_ad_categories': json.dumps(['NONE']), # 补全必填参数
                'access_token': token
            }
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data=c_data).json()
            if 'id' not in c_resp: return {'status': 'error', 'error': c_resp, 'step': 'Step 2: Campaign'}
            c_id = c_resp['id']

            # 3. AdSet
            as_payload = {
                'name': f"{name_base}-AS",
                'campaign_id': c_id,
                'daily_budget': 5000,
                'optimization_goal': 'APP_INSTALLS', # 修正优化目标
                'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({'application_id': self.app_id}), # 必须关联 APP ID
                'targeting': json.dumps({'geo_locations': {'countries': ['US']}, 'device_platforms': ['mobile']}),
                'status': 'PAUSED',
                'access_token': token
            }
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data=as_payload).json()
            if 'id' not in as_resp: return {'status': 'error', 'error': as_resp, 'step': 'Step 3: AdSet'}
            as_id = as_resp['id']

            # 4. Creative
            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy_res = writer.generate_copy(drama_name)
            copy = copy_res.get('versions', [{}])[0] if isinstance(copy_res, dict) and 'versions' in copy_res else {}
            
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
            if 'id' not in cr_resp: return {'status': 'error', 'error': cr_resp, 'step': 'Step 4: Creative'}
            cr_id = cr_resp['id']

            # 5. Ad
            ad_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={
                'name': f"{name_base}-Ad",
                'adset_id': as_id,
                'creative': json.dumps({'creative_id': cr_id}),
                'status': 'PAUSED',
                'access_token': token
            }).json()
            if 'id' not in ad_resp: return {'status': 'error', 'error': ad_resp, 'step': 'Step 5: Ad'}

            return {'status': 'success', 'campaign_id': c_id}

        except Exception as e:
            return {'status': 'error', 'error': str(e), 'traceback': traceback.format_exc()}

    def get_all_campaigns(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/campaigns"
            params = {'fields': 'id,name,status,effective_status,start_time', 'access_token': self.access_token, 'limit': 50}
            resp = requests.get(url, params=params).json()
            return resp.get('data', [])
        except: return []

    def get_yesterday_insights(self):
        return {}
