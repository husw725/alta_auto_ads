import os
import requests
import json
import re
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """Meta ADS 管理器 v1.9.8: 官方缩略图自动对齐版"""
    
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

    def _get_video_thumbnail(self, video_id):
        """[核心功能] 从 Meta 官方接口获取该视频处理后的缩略图"""
        token = self.access_token
        url = f"{self.base_url}/{video_id}/thumbnails"
        
        # 最多尝试 3 次，每次等 2 秒，给 Meta 一点处理视频的时间
        for i in range(3):
            try:
                time.sleep(2)
                resp = requests.get(url, params={'access_token': token}).json()
                if 'data' in resp and len(resp['data']) > 0:
                    # 优先获取最高分辨率的缩略图
                    return resp['data'][0].get('uri')
            except: pass
        return None

    def create_campaign(self, drama_name, video_url, thumb_url=None):
        """创建 Campaign (包含全自动缩略图提取)"""
        try:
            token = self.access_token
            cfg = self._load_config().get('default', {})
            budget = int(cfg.get('daily_budget', 50))
            name_base = f"{drama_name}-{cfg.get('country', 'US')}-{datetime.now().strftime('%m%d%H%M')}"

            # 1. Video Upload
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Video Fail: {v_resp}"}

            # 🚀 关键步骤：获取视频自带的缩略图
            official_thumb = self._get_video_thumbnail(v_id)
            # 如果 Meta 生成得慢，且 XMP 给的是图片链接，则用 XMP 的；否则用 Meta 官方的
            final_image_url = official_thumb if official_thumb else thumb_url
            
            # 兜底：如果还是没拿到图片链接（比如 XMP 给的是 mp4），我们就必须要传一个图，
            # 否则会被 Meta 报 1443226。此时我们传 App 的官方 Icon 作为最后兜底。
            if not final_image_url or '.mp4' in final_image_url.lower():
                final_image_url = "https://is1-ssl.mzstatic.com/image/thumb/Purple211/v4/3d/8c/7a/3d8c7a6b-6b7a-8d7a-6b7a-8d7a6b7a8d7a/AppIcon-0-0-1x_U007emarketing-0-7-0-sRGB-85-220.png/512x512bb.jpg"

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
            
            story_spec = {
                'page_id': self.page_id,
                'video_data': {
                    'video_id': v_id,
                    'image_url': final_image_url, # 强制提供图片链接
                    'message': copy.get('primary_text', 'Watch the latest drama now!'),
                    'title': copy.get('headline', f"Watch {drama_name}"),
                    'call_to_action': {'type': 'INSTALL_APP', 'value': {'link': self.official_store_url}}
                }
            }
            
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
