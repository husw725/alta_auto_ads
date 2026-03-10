import os
import requests
import json
import re
import time
from datetime import datetime
from urllib.parse import unquote
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """Meta ADS 管理器 v2.2.6: 极速投流版 (支持 URL 直接保底)"""
    
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        self.meta_app_id = "1807921329643155"
        self.official_store_url = "http://itunes.apple.com/app/id6469592412"
        self.base_url = "https://graph.facebook.com/v21.0"

    def _extract_real_name_from_url(self, video_url):
        try:
            filename = unquote(video_url.split('/')[-1])
            name = filename.encode('ascii', 'ignore').decode('ascii')
            name = re.sub(r'[\(\)\[\]\._\-]', ' ', name)
            name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
            name = re.sub(r'\s(mp4|mov|mkv)$', '', name, flags=re.IGNORECASE)
            parts = name.split()
            blacklist = {'v1','v2','v3','eng','en','us','pt','br','es','espanol','1080p','720p','60fps','30fps','short','final','fixed','export','ios','android','ad','drama','mp4','bsj','kk','alta','kkshort'}
            clean = [p for p in parts if not (re.match(r'^\d{4,12}$', p) or p.lower() in blacklist or (p.isdigit() and len(p) < 5) or len(p) <= 1)]
            return " ".join(clean).strip()
        except: return None

    def _get_video_thumbnail_hash_smart(self, video_id, token):
        """尝试获取官方视频帧 Hash"""
        for i in range(8):
            try:
                time.sleep(5)
                res = requests.get(f"{self.base_url}/{video_id}", params={'fields': 'thumbnails', 'access_token': token}).json()
                if 'thumbnails' in res and 'data' in res['thumbnails'] and res['thumbnails']['data']:
                    h = res['thumbnails']['data'][0].get('hash')
                    if h: return h
                print(f"⏳ [WAIT] 第 {i+1} 次尝试：Meta 正在抽帧...")
            except: pass
        return None

    def create_campaign(self, drama_name, video_url, thumb_url=None):
        try:
            token = self.access_token
            real_name = self._extract_real_name_from_url(video_url)
            display_name = real_name if real_name else drama_name
            name_base = f"{display_name}-{datetime.now().strftime('%m%d%H%M')}"

            # 1. Upload Video
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Step 1 Video Fail: {v_resp}"}

            # 2. 缩略图决策 (不再报错，只做逻辑切换)
            img_hash = self._get_video_thumbnail_hash_smart(v_id, token)
            
            # 3. 构建 AdCreative payload
            from skills.copywriter import Copywriter
            copy = Copywriter().generate_copy(display_name).get('versions', [{}])[0]
            
            video_data = {
                'video_id': v_id,
                'message': copy.get('primary_text', 'Watch now!'),
                'title': copy.get('headline', f"Watch {display_name}"),
                'call_to_action': {'type': 'INSTALL_APP', 'value': {'link': self.official_store_url}}
            }

            if img_hash:
                video_data['image_hash'] = img_hash # 优先用 Hash
            elif thumb_url and any(thumb_url.lower().endswith(ext) for ext in ['.jpg', '.png', '.jpeg', '.webp']):
                print(f"🚀 使用 URL 直接保底: {thumb_url}")
                video_data['image_url'] = thumb_url # 没 Hash 就直接传 URL，省去上传步骤
            else:
                # 🚀 最终保底：使用搜索发现的官方高清封面
                video_data['image_url'] = "https://starlitshorts.s3.amazonaws.com/s/986f2dd37aba040d55361a407ca860f5.png"

            # 4. 创建流程
            c_id = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={'name': name_base, 'objective': 'OUTCOME_APP_PROMOTION', 'status': 'PAUSED', 'special_ad_categories': json.dumps(['NONE']), 'daily_budget': 5000, 'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 'access_token': token}).json().get('id')
            
            as_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data={'name': f"{name_base}-AS", 'campaign_id': c_id, 'optimization_goal': 'APP_INSTALLS', 'destination_type': 'APP', 'billing_event': 'IMPRESSIONS', 'promoted_object': json.dumps({'application_id': self.meta_app_id, 'object_store_url': self.official_store_url}), 'targeting': json.dumps({'geo_locations': {'countries': ['US']}, 'device_platforms': ['mobile'], 'user_os': ['iOS']}), 'status': 'PAUSED', 'access_token': token}).json().get('id')
            
            cr_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={'name': f"{name_base}-Cr", 'object_story_spec': json.dumps({'page_id': self.page_id, 'video_data': video_data}), 'access_token': token}).json()
            cr_id = cr_resp.get('id')
            if not cr_id: return {'status': 'error', 'error': f"Creative Fail: {cr_resp}"}
            
            ad_id = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token}).json().get('id')
            
            # Activate
            for rid in [c_id, as_id, ad_id]: requests.post(f"{self.base_url}/{rid}", data={'status': 'ACTIVE', 'access_token': token})

            return {'status': 'success', 'campaign_id': c_id}
        except Exception as e: return {'status': 'error', 'error': str(e)}

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
