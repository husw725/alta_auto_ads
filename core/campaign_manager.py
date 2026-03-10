import os
import requests
import json
import re
import time
from datetime import datetime, timedelta
from urllib.parse import unquote
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """Meta ADS 管理器 v2.3.0: 全指标专业版"""
    
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
        except: return {"default": {"country": "US", "daily_budget": 50}, "strategy": {"CPI_THRESHOLD": 2.0}}

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

    def create_campaign(self, drama_name, video_url, thumb_url=None):
        try:
            token = self.access_token
            cfg = self._load_config().get('default', {})
            country = cfg.get('country', 'US')
            today = datetime.now().strftime('%Y%m%d')
            
            # 🚀 锁定 6 段式标准命名: {剧名}-{国家}-{日期}-w2a-Auto-龙虾ai
            name_base = f"{drama_name}-{country}-{today}-w2a-Auto-龙虾ai"
            
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Video Fail: {v_resp}"}

            img_hash = self._get_video_thumbnail_hash_smart(v_id, token)
            video_data = {'video_id': v_id, 'call_to_action': {'type': 'INSTALL_APP', 'value': {'link': self.official_store_url}}}
            if img_hash: video_data['image_hash'] = img_hash
            elif thumb_url: video_data['image_url'] = thumb_url
            else: video_data['image_url'] = "https://starlitshorts.s3.amazonaws.com/s/986f2dd37aba040d55361a407ca860f5.png"

            c_id = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={'name': name_base, 'objective': 'OUTCOME_APP_PROMOTION', 'status': 'PAUSED', 'special_ad_categories': json.dumps(['NONE']), 'daily_budget': 5000, 'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 'access_token': token}).json().get('id')
            as_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data={'name': f"{name_base}-AS", 'campaign_id': c_id, 'optimization_goal': 'APP_INSTALLS', 'destination_type': 'APP', 'billing_event': 'IMPRESSIONS', 'promoted_object': json.dumps({'application_id': self.meta_app_id, 'object_store_url': self.official_store_url}), 'targeting': json.dumps({'geo_locations': {'countries': ['US']}, 'device_platforms': ['mobile'], 'user_os': ['iOS']}), 'status': 'PAUSED', 'access_token': token}).json().get('id')
            
            from skills.copywriter import Copywriter
            copy = Copywriter().generate_copy(display_name).get('versions', [{}])[0]
            video_data.update({'message': copy.get('primary_text', 'Watch now!'), 'title': copy.get('headline', f"Watch {display_name}")})
            cr_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={'name': f"{name_base}-Cr", 'object_story_spec': json.dumps({'page_id': self.page_id, 'video_data': video_data}), 'access_token': token}).json().get('id')
            ad_id = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token}).json().get('id')
            
            for rid in [c_id, as_id, ad_id]: requests.post(f"{self.base_url}/{rid}", data={'status': 'ACTIVE', 'access_token': token})
            return {'status': 'success', 'campaign_id': c_id}
        except Exception as e: return {'status': 'error', 'error': str(e)}

    def get_all_campaigns(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/campaigns"
            params = {'fields': 'id,name,status,effective_status,start_time,daily_budget', 'access_token': self.access_token, 'limit': 50}
            resp = requests.get(url, params=params).json()
            return resp.get('data', [])
        except: return []

    def get_yesterday_insights(self):
        """获取全指标深度表现数据"""
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            # 扩展字段：impressions(展示), clicks(点击), actions(各种动作)
            params = {
                'level': 'campaign', 'date_preset': 'yesterday',
                'fields': 'campaign_id,spend,impressions,clicks,actions,purchase_roas',
                'access_token': self.access_token
            }
            resp = requests.get(url, params=params).json()
            res = {}
            if 'data' in resp:
                for item in resp['data']:
                    cid = item['campaign_id']
                    spend = float(item.get('spend', 0))
                    imps = int(item.get('impressions', 0))
                    clicks = int(item.get('clicks', 0))
                    
                    # 提取安装量和购物量
                    installs = 0
                    purchases = 0
                    for a in item.get('actions', []):
                        if a['action_type'] == 'mobile_app_install': installs = int(a['value'])
                        if a['action_type'] == 'purchase' or 'fb_pixel_purchase' in a['action_type']: purchases = int(a['value'])
                    
                    roi = float(item['purchase_roas'][0]['value']) if item.get('purchase_roas') else 0
                    
                    # 计算专业指标
                    res[cid] = {
                        'spend': spend,
                        'clicks': clicks,
                        'installs': installs,
                        'purchases': purchases,
                        'roi': roi,
                        'ctr': (clicks / imps) if imps > 0 else 0,
                        'cpm': (spend / imps * 1000) if imps > 0 else 0,
                        'cpc': (spend / clicks) if clicks > 0 else 0,
                        'cpi': (spend / installs) if installs > 0 else 0,
                        'cpp': (spend / purchases) if purchases > 0 else 0,
                        'cvr': (installs / clicks) if clicks > 0 else 0
                    }
            return res
        except: return {}

    def _get_video_thumbnail_hash_smart(self, vid, token):
        for i in range(8):
            try:
                time.sleep(5)
                r = requests.get(f"{self.base_url}/{vid}", params={'fields': 'thumbnails', 'access_token': token}).json()
                if 'thumbnails' in r and r['thumbnails']['data']: return r['thumbnails']['data'][0].get('hash')
            except: pass
        return None

    def evaluate_optimization_rules(self, campaigns, insights):
        strat = self._load_config().get('strategy', {})
        threshold = float(strat.get('CPI_THRESHOLD', 2.0))
        actions = []
        for c in campaigns:
            cid = c['id']
            if c['effective_status'] != 'ACTIVE': continue
            ins = insights.get(cid, {})
            if ins.get('spend', 0) > 10 and ins.get('cpi', 0) > threshold:
                actions.append({'type': 'PAUSE', 'cid': cid, 'name': c['name'], 'reason': f"CPI (${ins['cpi']:.2f}) > {threshold}"})
        return actions

    def update_campaign_status(self, cid, status):
        try: return requests.post(f"{self.base_url}/{cid}", data={'status': status, 'access_token': self.access_token}).json().get('success', False)
        except: return False

    def execute_action(self, action):
        return self.update_campaign_status(action['cid'], 'PAUSED') if action['type'] == 'PAUSE' else False
