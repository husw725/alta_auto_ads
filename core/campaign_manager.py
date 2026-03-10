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
    """Meta ADS 管理器 v2.2.5: 极简稳定版 (弃用网页搜索)"""
    
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        self.meta_app_id = "1807921329643155"
        self.official_store_url = "http://itunes.apple.com/app/id6469592412"
        self.base_url = "https://graph.facebook.com/v21.0"

    def _extract_real_name_from_url(self, video_url):
        """从文件名中剥离剧名"""
        try:
            filename = unquote(video_url.split('/')[-1])
            name = filename.encode('ascii', 'ignore').decode('ascii')
            name = re.sub(r'[\(\)\[\]\._\-]', ' ', name)
            name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
            name = re.sub(r'\s(mp4|mov|mkv)$', '', name, flags=re.IGNORECASE)
            parts = name.split()
            blacklist = {
                'v1', 'v2', 'v3', 'eng', 'en', 'us', 'pt', 'br', 'es', 'espanol', 
                '1080p', '720p', '60fps', '30fps', 'short', 'final', 'fixed', 'export',
                'ios', 'android', 'ad', 'drama', 'mp4', 'bsj', 'kk', 'alta', 'kkshort'
            }
            clean_parts = []
            for p in parts:
                p_lower = p.lower()
                if re.match(r'^\d{4,12}$', p) or p_lower in blacklist or (p.isdigit() and len(p) < 5) or len(p) <= 1: continue
                clean_parts.append(p)
            result = " ".join(clean_parts).strip()
            return result if len(result) > 2 else None
        except: return None

    def _get_video_thumbnail_hash_smart(self, video_id, token):
        """探测 Meta 视频帧"""
        for i in range(8):
            try:
                time.sleep(5)
                url = f"{self.base_url}/{video_id}"
                params = {'fields': 'thumbnails', 'access_token': token}
                res = requests.get(url, params=params).json()
                if 'thumbnails' in res and 'data' in res['thumbnails'] and res['thumbnails']['data']:
                    h = res['thumbnails']['data'][0].get('hash')
                    if h: return h
                print(f"⏳ [WAIT] 第 {i+1} 次尝试：Meta 正在抽帧...")
            except: pass
        return None

    def create_campaign(self, drama_name, video_url, thumb_url=None):
        """创建 Campaign (主打 Meta 抽帧，辅以 XMP 海报兜底)"""
        try:
            token = self.access_token
            real_name = self._extract_real_name_from_url(video_url)
            display_name = real_name if real_name else drama_name
            name_base = f"{display_name}-{datetime.now().strftime('%m%d%H%M')}"

            # 1. Upload Video
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Step 1 Video Fail: {v_resp}"}

            # 2. 缩略图决策逻辑
            img_hash = self._get_video_thumbnail_hash_smart(v_id, token)
            
            if not img_hash and thumb_url:
                print(f"⏳ 视频抽帧超时，直接使用 XMP 海报: {thumb_url}")
                # 上传 XMP 提供的封面并获取 Hash
                img_res = requests.post(f"{self.base_url}/{self.ad_account_id}/adimages", data={'copy_from_url': thumb_url, 'access_token': token}).json()
                if 'images' in img_res:
                    img_hash = img_res['images'][list(img_res['images'].keys())[0]]['hash']

            # 3. 终极兜底 (如果 Meta 和 XMP 封面都失效)
            if not img_hash:
                fallback_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Google_Play_Store_badge_EN.svg/2560px-Google_Play_Store_badge_EN.svg.png"
                img_res = requests.post(f"{self.base_url}/{self.ad_account_id}/adimages", data={'copy_from_url': fallback_url, 'access_token': token}).json()
                img_hash = img_res['images'][list(img_res['images'].keys())[0]]['hash'] if 'images' in img_res else None

            if not img_hash: return {'status': 'error', 'error': "无法获取图片 Hash"}

            # 4. Campaign & AdSet & Creative & Ad (逻辑保持不变)
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={'name': name_base, 'objective': 'OUTCOME_APP_PROMOTION', 'status': 'PAUSED', 'special_ad_categories': json.dumps(['NONE']), 'daily_budget': 5000, 'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 'access_token': token}).json()
            c_id = c_resp.get('id')
            
            as_payload = {'name': f"{name_base}-AS", 'campaign_id': c_id, 'optimization_goal': 'APP_INSTALLS', 'destination_type': 'APP', 'billing_event': 'IMPRESSIONS', 'promoted_object': json.dumps({'application_id': self.meta_app_id, 'object_store_url': self.official_store_url}), 'targeting': json.dumps({'geo_locations': {'countries': ['US']}, 'device_platforms': ['mobile'], 'user_os': ['iOS']}), 'status': 'PAUSED', 'access_token': token}
            as_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data=as_payload).json().get('id')
            
            from skills.copywriter import Copywriter
            copy = Copywriter().generate_copy(display_name).get('versions', [{}])[0]
            story_spec = {'page_id': self.page_id, 'video_data': {'video_id': v_id, 'image_hash': img_hash, 'message': copy.get('primary_text', 'Watch now!'), 'title': copy.get('headline', f"Watch {display_name}"), 'call_to_action': {'type': 'INSTALL_APP', 'value': {'link': self.official_store_url}}}}
            cr_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={'name': f"{name_base}-Cr", 'object_story_spec': json.dumps(story_spec), 'access_token': token}).json().get('id')
            
            ad_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token}).json()
            
            # Activate all
            requests.post(f"{self.base_url}/{c_id}", data={'status': 'ACTIVE', 'access_token': token})
            requests.post(f"{self.base_url}/{as_id}", data={'status': 'ACTIVE', 'access_token': token})
            requests.post(f"{self.base_url}/{ad_resp.get('id', '')}", data={'status': 'ACTIVE', 'access_token': token})

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
