import os
import requests
import json
import re
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """Meta ADS 管理器 v1.9.9: 极致稳定版 (100% 依赖官方抽帧)"""
    
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        self.meta_app_id = "1807921329643155"
        self.official_store_url = "http://itunes.apple.com/app/id6469592412"
        self.base_url = "https://graph.facebook.com/v21.0"

    def _get_video_thumbnail_hash_forced(self, video_id, token):
        """[极致稳定] 强制等待并提取 Meta 官方抽帧，失败则阻塞"""
        print(f"📡 [DEBUG] 正在反查视频 {video_id} 的官方缩略图...")
        for i in range(10): # 最多等待 30 秒
            try:
                time.sleep(3)
                url = f"{self.base_url}/{video_id}"
                params = {'fields': 'thumbnails', 'access_token': token}
                res = requests.get(url, params=params).json()
                
                if 'thumbnails' in res and 'data' in res['thumbnails'] and res['thumbnails']['data']:
                    h = res['thumbnails']['data'][0].get('hash')
                    if h:
                        print(f"✨ [OK] 已获得 Meta 官方 Hash: {h}")
                        return h
                print(f"⏳ [WAIT] 第 {i+1} 次尝试：Meta 处理中...")
            except: pass
        return None

    def create_campaign(self, drama_name, video_url, thumb_url=None):
        try:
            token = self.access_token
            cfg = {"country": "US", "daily_budget": 50} # 默认配置
            name_base = f"{drama_name}-{datetime.now().strftime('%m%d%H%M')}"

            # 1. Upload Video
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Step 1 Video Fail: {v_resp}"}

            # 2. 🚀 阻塞获取官方 Hash (这是核心)
            img_hash = self._get_video_thumbnail_hash_forced(v_id, token)
            if not img_hash: return {'status': 'error', 'error': "Meta 官方抽帧超时，请稍后重试"}

            # 3. Campaign
            c_payload = {
                'name': name_base, 'objective': 'OUTCOME_APP_PROMOTION', 'status': 'PAUSED',
                'special_ad_categories': json.dumps(['NONE']), 'daily_budget': 5000,
                'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 'access_token': token
            }
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data=c_payload).json()
            c_id = c_resp.get('id')
            if not c_id: return {'status': 'error', 'error': f"Step 2 Campaign Fail: {c_resp}"}

            # 4. AdSet
            as_payload = {
                'name': f"{name_base}-AS", 'campaign_id': c_id, 'optimization_goal': 'APP_INSTALLS',
                'destination_type': 'APP', 'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({'application_id': self.meta_app_id, 'object_store_url': self.official_store_url}),
                'targeting': json.dumps({'geo_locations': {'countries': ['US']}, 'device_platforms': ['mobile'], 'user_os': ['iOS']}),
                'status': 'PAUSED', 'access_token': token
            }
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data=as_payload).json()
            as_id = as_resp.get('id')
            if not as_id: return {'status': 'error', 'error': f"Step 3 AdSet Fail: {as_resp}"}

            # 5. AdCreative (完全使用 Hash 模式)
            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy = writer.generate_copy(drama_name).get('versions', [{}])[0]
            
            story_spec = {
                'page_id': self.page_id,
                'video_data': {
                    'video_id': v_id,
                    'image_hash': img_hash, # 100% 官方产出的 Hash
                    'message': copy.get('primary_text', 'Watch on AltaTV!'),
                    'title': copy.get('headline', f"Watch {drama_name}"),
                    'call_to_action': {'type': 'INSTALL_APP', 'value': {'link': self.official_store_url}}
                }
            }
            cr_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={
                'name': f"{name_base}-Cr", 'object_story_spec': json.dumps(story_spec), 'access_token': token
            }).json()
            cr_id = cr_resp.get('id')
            if not cr_id: return {'status': 'error', 'error': f"Step 4 Creative Fail: {cr_resp}"}
            
            # 6. Ad
            ad_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={
                'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token
            }).json()
            
            # 7. Auto Activate
            requests.post(f"{self.base_url}/{c_id}", data={'status': 'ACTIVE', 'access_token': token})
            requests.post(f"{self.base_url}/{as_id}", data={'status': 'ACTIVE', 'access_token': token})
            requests.post(f"{self.base_url}/{ad_resp['id']}", data={'status': 'ACTIVE', 'access_token': token})

            return {'status': 'success', 'campaign_id': c_id}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def get_all_campaigns(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/campaigns"
            params = {'fields': 'id,name,status,effective_status,start_time,daily_budget', 'access_token': self.access_token, 'limit': 50}
            resp = requests.get(url, params=params).json()
            return sorted(resp.get('data', []), key=lambda x: x.get('start_time', '0'), reverse=True)
        except: return []

    def update_campaign_status(self, cid, status):
        try: return requests.post(f"{self.base_url}/{cid}", data={'status': status, 'access_token': self.access_token}).json().get('success', False)
        except: return False

    def get_yesterday_insights(self): return {}
    def evaluate_optimization_rules(self, camps, ins, hist): return []
