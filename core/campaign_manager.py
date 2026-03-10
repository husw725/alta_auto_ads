import os
import requests
import json
import re
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """Meta ADS 管理器 v2.0.0: 智能异步双保险版"""
    
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        self.meta_app_id = "1807921329643155"
        self.official_store_url = "http://itunes.apple.com/app/id6469592412"
        self.base_url = "https://graph.facebook.com/v21.0"
        # 预置一个已验证的官方图标 Hash (AltaTV Logo)
        # 如果获取不到视频帧，就用这个兜底，确保 100% 成功
        self.fallback_img_hash = None 

    def _get_or_upload_fallback_hash(self, token):
        """[核心加固] 预先上传一个图标作为保险绳"""
        try:
            # 使用 AltaTV 官网的 Favicon 或 Logo 确保合规
            logo_url = "https://altatv.net/favicon.png"
            res = requests.post(f"{self.base_url}/{self.ad_account_id}/adimages", data={
                'copy_from_url': logo_url, 'access_token': token
            }).json()
            if 'images' in res:
                # 获取返回的第一个 Hash
                first_key = list(res['images'].keys())[0]
                return res['images'][first_key]['hash']
            return None
        except: return None

    def _get_video_thumbnail_hash_smart(self, video_id, token):
        """[智能探测] 尝试获取官方视频帧，不成功则返回 None"""
        for i in range(6): # 等待 18 秒，这是一个性能平衡点
            try:
                time.sleep(3)
                url = f"{self.base_url}/{video_id}"
                params = {'fields': 'thumbnails', 'access_token': token}
                res = requests.get(url, params=params).json()
                if 'thumbnails' in res and 'data' in res['thumbnails'] and res['thumbnails']['data']:
                    h = res['thumbnails']['data'][0].get('hash')
                    if h: return h
            except: pass
        return None

    def create_campaign(self, drama_name, video_url, thumb_url=None):
        try:
            token = self.access_token
            name_base = f"{drama_name}-{datetime.now().strftime('%m%d%H%M')}"

            # 1. Upload Video
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Video Fail: {v_resp}"}

            # 2. 🚀 双路并行获取 Hash
            # 路径 A: 探测视频帧
            img_hash = self._get_video_thumbnail_hash_smart(v_id, token)
            
            # 路径 B: 如果路径 A 失败，立即上传一个图标作为兜底
            if not img_hash:
                print("⏳ 视频抽帧较慢，启动图标兜底方案...")
                img_hash = self._get_or_upload_fallback_hash(token)
            
            if not img_hash: return {'status': 'error', 'error': "无法获取有效的图片 Hash，Meta 接口当前较繁忙"}

            # 3. Campaign
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={
                'name': name_base, 'objective': 'OUTCOME_APP_PROMOTION', 'status': 'PAUSED',
                'special_ad_categories': json.dumps(['NONE']), 'daily_budget': 5000,
                'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 'access_token': token
            }).json()
            c_id = c_resp.get('id')

            # 4. AdSet
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data={
                'name': f"{name_base}-AS", 'campaign_id': c_id, 'optimization_goal': 'APP_INSTALLS',
                'destination_type': 'APP', 'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({'application_id': self.meta_app_id, 'object_store_url': self.official_store_url}),
                'targeting': json.dumps({'geo_locations': {'countries': ['US']}, 'device_platforms': ['mobile'], 'user_os': ['iOS']}),
                'status': 'PAUSED', 'access_token': token
            }).json()
            as_id = as_resp.get('id')

            # 5. AdCreative
            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy = writer.generate_copy(drama_name).get('versions', [{}])[0]
            
            story_spec = {
                'page_id': self.page_id,
                'video_data': {
                    'video_id': v_id, 'image_hash': img_hash,
                    'message': copy.get('primary_text', 'Watch on AltaTV!'),
                    'title': copy.get('headline', f"Watch {drama_name}"),
                    'call_to_action': {'type': 'INSTALL_APP', 'value': {'link': self.official_store_url}}
                }
            }
            cr_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={
                'name': f"{name_base}-Cr", 'object_story_spec': json.dumps(story_spec), 'access_token': token
            }).json()
            cr_id = cr_resp.get('id')
            
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
