import os
import requests
import json
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """Meta ADS 管理器 v1.9.7: 稳定版 (自动处理视频封面)"""
    
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        self.meta_app_id = "1807921329643155"
        self.official_store_url = "http://itunes.apple.com/app/id6469592412"
        self.base_url = "https://graph.facebook.com/v21.0"

    def _load_config(self):
        try:
            with open('config/config.json', 'r') as f: return json.load(f)
        except: return {"default": {"country": "US", "daily_budget": 50}}

    def create_campaign(self, drama_name, video_url, thumb_url=None):
        try:
            token = self.access_token
            cfg = self._load_config().get('default', {})
            budget = int(cfg.get('daily_budget', 50))
            name_base = f"{drama_name}-{cfg.get('country', 'US')}-{datetime.now().strftime('%m%d%H%M')}"

            # 1. Video Upload
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Video Fail: {v_resp}"}

            # 2. Campaign (CBO)
            c_payload = {
                'name': name_base, 'objective': 'OUTCOME_APP_PROMOTION', 'status': 'PAUSED',
                'special_ad_categories': json.dumps(['NONE']), 'daily_budget': budget * 100,
                'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 'access_token': token
            }
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data=c_payload).json()
            c_id = c_resp.get('id')
            if not c_id: return {'status': 'error', 'error': f"Campaign Fail: {c_resp}"}

            # 3. AdSet
            as_payload = {
                'name': f"{name_base}-AS", 'campaign_id': c_id, 'optimization_goal': 'APP_INSTALLS',
                'destination_type': 'APP', 'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({'application_id': self.meta_app_id, 'object_store_url': self.official_store_url}),
                'targeting': json.dumps({'geo_locations': {'countries': [cfg.get('country', 'US')]}, 'device_platforms': ['mobile'], 'user_os': ['iOS']}),
                'status': 'PAUSED', 'access_token': token
            }
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data=as_payload).json()
            as_id = as_resp.get('id')
            if not as_id: return {'status': 'error', 'error': f"AdSet Fail: {as_resp}"}

            # 4. AdCreative
            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy = writer.generate_copy(drama_name).get('versions', [{}])[0]
            
            # 🚀 关键改进：如果传进来的 thumb_url 是 mp4 或为空，直接不传 image_url
            # Meta 会自动使用视频的第一帧作为缩略图，从而避开下载失败
            video_data = {
                'video_id': v_id,
                'message': copy.get('primary_text', 'Watch now!'),
                'title': copy.get('headline', f"Watch {drama_name}"),
                'call_to_action': {'type': 'INSTALL_APP', 'value': {'link': self.official_store_url}}
            }
            
            # 仅当 thumb_url 确实是图片时才添加（简单通过后缀判断）
            if thumb_url and any(thumb_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                video_data['image_url'] = thumb_url

            story_spec = {'page_id': self.page_id, 'video_data': video_data}
            
            cr_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={
                'name': f"{name_base}-Cr", 'object_story_spec': json.dumps(story_spec), 'access_token': token
            }).json()
            cr_id = cr_resp.get('id')
            if not cr_id: return {'status': 'error', 'error': f"Creative Fail: {cr_resp}"}
            
            # 5. Ad
            ad_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={
                'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token
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
    def evaluate_optimization_rules(self, camps, ins, hist): return []
