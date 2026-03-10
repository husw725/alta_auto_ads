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
    """Meta ADS 管理器 v2.2.3: 极限稳定 + 精准海报版"""
    
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        self.meta_app_id = "1807921329643155"
        self.official_store_url = "http://itunes.apple.com/app/id6469592412"
        self.base_url = "https://graph.facebook.com/v21.0"

    def _extract_real_name_from_url(self, video_url):
        """[核心算法] 从混乱的文件名中精准剥离剧名"""
        try:
            filename = unquote(video_url.split('/')[-1])
            # 1. 彻底移除所有非 ASCII 字符 (如中文)
            name = filename.encode('ascii', 'ignore').decode('ascii')
            # 2. 统一分隔符并处理驼峰
            name = re.sub(r'[\(\)\[\]\._\-]', ' ', name)
            name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
            # 3. 移除后缀
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
                if re.match(r'^\d{4,12}$', p): continue
                if p_lower in blacklist: continue
                if p.isdigit() and len(p) < 5: continue
                if len(p) <= 1: continue
                clean_parts.append(p)
            
            result = " ".join(clean_parts).strip()
            return result if len(result) > 2 else None
        except: return None

    def _scrape_poster_from_web(self, drama_name):
        """[邻近定位] 根据截图布局，精准抓取标题左侧/上方的海报"""
        try:
            search_key = drama_name.replace(' ', '+')
            url = f"https://altatv.com/search?keywords={search_key}&type=1"
            print(f"🔍 [DEBUG] 正在访问官网搜索页: {url}")
            
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=5).text
            
            # 定位剧名在 HTML 中的位置
            title_pos = resp.lower().find(drama_name.lower())
            
            if title_pos != -1:
                # 截图显示海报在左，源码中在文字上方。向上搜索 3000 字符。
                search_start = max(0, title_pos - 3000)
                upper_context = resp[search_start:title_pos]
                matches = re.findall(r'https://starlitshorts\.s3\.amazonaws\.com/s/[a-f0-9]+\.(?:png|jpg|webp)', upper_context)
                
                if matches:
                    # 取距离标题最近的一个 (即最后一个匹配项)
                    target_img = matches[-1]
                    print(f"✅ [DEBUG] 成功定位到标题附近的海报: {target_img}")
                    return target_img
            
            # 兜底：全局搜索
            global_matches = re.findall(r'https://starlitshorts\.s3\.amazonaws\.com/s/[a-f0-9]+\.(?:png|jpg|webp)', resp)
            if global_matches:
                # 优先取 index 1 (通常是海报而不是图标)
                target_global = global_matches[1] if len(global_matches) > 1 else global_matches[0]
                return target_global
            return None
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
        try:
            token = self.access_token
            real_name = self._extract_real_name_from_url(video_url)
            search_name = real_name if real_name else drama_name
            name_base = f"{search_name}-{datetime.now().strftime('%m%d%H%M')}"

            # 1. Video Upload
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Step 1 Video Fail: {v_resp}"}

            # 2. 智能缩略图决策
            img_hash = self._get_video_thumbnail_hash_smart(v_id, token)
            if not img_hash:
                poster_url = self._scrape_poster_from_web(search_name)
                final_img_url = poster_url if poster_url else "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Google_Play_Store_badge_EN.svg/2560px-Google_Play_Store_badge_EN.svg.png"
                img_res = requests.post(f"{self.base_url}/{self.ad_account_id}/adimages", data={'copy_from_url': final_img_url, 'access_token': token}).json()
                if 'images' in img_res:
                    img_hash = img_res['images'][list(img_res['images'].keys())[0]]['hash']

            if not img_hash: return {'status': 'error', 'error': "无法获取图片 Hash"}

            # 3. Campaign (CBO)
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={
                'name': name_base, 'objective': 'OUTCOME_APP_PROMOTION', 'status': 'PAUSED',
                'special_ad_categories': json.dumps(['NONE']), 'daily_budget': 5000,
                'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 'access_token': token
            }).json()
            c_id = c_resp.get('id')

            # 4. AdSet (iOS 锁定)
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
            copy = writer.generate_copy(search_name).get('versions', [{}])[0]
            story_spec = {
                'page_id': self.page_id,
                'video_data': {
                    'video_id': v_id, 'image_hash': img_hash,
                    'message': copy.get('primary_text', 'Watch now!'),
                    'title': copy.get('headline', f"Watch {search_name}"),
                    'call_to_action': {'type': 'INSTALL_APP', 'value': {'link': self.official_store_url}}
                }
            }
            cr_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={'name': f"{name_base}-Cr", 'object_story_spec': json.dumps(story_spec), 'access_token': token}).json()
            cr_id = cr_resp.get('id')
            
            # 6. Ad & Activate
            ad_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token}).json()
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
