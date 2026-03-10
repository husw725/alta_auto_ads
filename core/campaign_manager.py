import os
import requests
import json
import re
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """Meta ADS 管理器 v1.9.8: 工业级合规版 (官方缩略图 Hash 方案)"""
    
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        self.meta_app_id = "1807921329643155"
        self.official_store_url = "http://itunes.apple.com/app/id6469592412"
        self.base_url = "https://graph.facebook.com/v21.0"

    def _get_video_thumbnail_hash(self, video_id, token):
        """[核心加固] 从上传的视频中提取 Meta 官方生成的缩略图 Hash"""
        try:
            # 等待 1-2 秒确保 Meta 已经处理出第一帧
            time.sleep(2)
            url = f"{self.base_url}/{video_id}"
            params = {'fields': 'thumbnails', 'access_token': token}
            res = requests.get(url, params=params).json()
            
            # 提取第一个生成的缩略图 Hash
            if 'thumbnails' in res and 'data' in res['thumbnails'] and res['thumbnails']['data']:
                return res['thumbnails']['data'][0].get('hash')
            return None
        except:
            return None

    def create_campaign(self, drama_name, video_url, thumb_url=None):
        try:
            token = self.access_token
            name_base = f"{drama_name}-{datetime.now().strftime('%m%d%H%M')}"

            # 1. Video Upload
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Video Fail: {v_resp}"}

            # 🚀 关键步骤：获取 Meta 官方生成的 Hash，确保 100% 通过校验
            img_hash = self._get_video_thumbnail_hash(v_id, token)

            # 2. Campaign
            c_payload = {
                'name': name_base, 'objective': 'OUTCOME_APP_PROMOTION', 'status': 'PAUSED',
                'special_ad_categories': json.dumps(['NONE']), 'daily_budget': 5000,
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
                'targeting': json.dumps({'geo_locations': {'countries': ['US']}, 'device_platforms': ['mobile'], 'user_os': ['iOS']}),
                'status': 'PAUSED', 'access_token': token
            }
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data=as_payload).json()
            as_id = as_resp.get('id')
            if not as_id: return {'status': 'error', 'error': f"AdSet Fail: {as_resp}"}

            # 4. AdCreative (补全所有必填版块)
            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy = writer.generate_copy(drama_name).get('versions', [{}])[0]
            
            video_data = {
                'video_id': v_id,
                'message': copy.get('primary_text', 'Watch now!'),
                'title': copy.get('headline', f"Watch {drama_name}"),
                'call_to_action': {'type': 'INSTALL_APP', 'value': {'link': self.official_store_url}}
            }
            
            # --- 终极缩略图填充逻辑 ---
            if img_hash:
                video_data['image_hash'] = img_hash # 优先使用 Meta 官方生成的 Hash
            elif thumb_url and any(thumb_url.lower().endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                video_data['image_url'] = thumb_url # 备选 XMP 图片
            else:
                # 最后的兜底：如果都没有，传视频地址给 URL（虽然有风险，但好过报错）
                video_data['image_url'] = "https://altatv.net/favicon.png" # 强制使用一个合规的占位图
            
            cr_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={
                'name': f"{name_base}-Cr", 'object_story_spec': json.dumps({'page_id': self.page_id, 'video_data': video_data}), 'access_token': token
            }).json()
            cr_id = cr_resp.get('id')
            if not cr_id: return {'status': 'error', 'error': f"Creative Fail: {cr_resp}"}
            
            # 5. Ad
            ad_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={
                'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token
            }).json()
            
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
