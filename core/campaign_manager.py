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
    """Meta ADS 管理器 v2.8.9: 动态配置 + 极速开单版"""
    
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

    def create_campaign(self, drama_name, video_url, thumb_url=None):
        """创建 Campaign (🚀 动态读取配置模式)"""
        try:
            token = self.access_token
            # 🚀 核心改进：从配置中读取最新设置
            cfg = self._load_config().get('default', {})
            country = cfg.get('country', 'US')
            budget_cents = int(cfg.get('daily_budget', 50)) * 100
            
            today = datetime.now().strftime('%Y%m%d')
            name_base = f"{drama_name}-{country}-{today}-w2a-Auto-龙虾ai"
            
            # 1. 视频上传
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Video Fail: {v_resp}"}

            # 2. 缩略图决策
            img_hash = None
            if thumb_url:
                img_res = requests.post(f"{self.base_url}/{self.ad_account_id}/adimages", data={'copy_from_url': thumb_url, 'access_token': token}).json()
                if 'images' in img_res: img_hash = img_res['images'][list(img_res['images'].keys())[0]]['hash']
            if not img_hash: img_hash = self._get_video_thumbnail_hash_smart(v_id, token)

            video_data = {'video_id': v_id, 'call_to_action': {'type': 'INSTALL_APP', 'value': {'link': self.official_store_url}}}
            if img_hash: video_data['image_hash'] = img_hash
            else: video_data['image_url'] = "https://starlitshorts.s3.amazonaws.com/s/986f2dd37aba040d55361a407ca860f5.png"

            # 3. 创建 Campaign (使用动态预算)
            c_id = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={
                'name': name_base, 'objective': 'OUTCOME_APP_PROMOTION', 'status': 'PAUSED',
                'special_ad_categories': json.dumps(['NONE']), 'daily_budget': budget_cents,
                'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 'access_token': token
            }).json().get('id')
            
            # 4. 创建 AdSet (使用动态国家)
            as_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data={
                'name': f"{name_base}-AS", 'campaign_id': c_id, 'optimization_goal': 'APP_INSTALLS',
                'destination_type': 'APP', 'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({'application_id': self.meta_app_id, 'object_store_url': self.official_store_url}),
                'targeting': json.dumps({'geo_locations': {'countries': [country]}, 'device_platforms': ['mobile'], 'user_os': ['iOS']}),
                'status': 'PAUSED', 'access_token': token
            }).json().get('id')
            
            # 5. 创建 Creative
            cr_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={'name': f"{name_base}-Cr", 'object_story_spec': json.dumps({'page_id': self.page_id, 'video_data': video_data}), 'access_token': token}).json().get('id')
            
            # 6. 创建 Ad
            ad_id = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token}).json().get('id')
            
            # 7. 激活
            for rid in [c_id, as_id, ad_id]: requests.post(f"{self.base_url}/{rid}", data={'status': 'ACTIVE', 'access_token': token})
            return {'status': 'success', 'campaign_id': c_id}
        except Exception as e: return {'status': 'error', 'error': str(e)}

    def get_yesterday_insights(self, date_str=None):
        try:
            from datetime import datetime, timedelta, timezone
            if not date_str:
                user_tz = timezone(timedelta(hours=-8))
                date_str = (datetime.now(user_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {'level': 'campaign', 'time_range': json.dumps({'since': date_str, 'until': date_str}), 'fields': 'campaign_id,spend,impressions,clicks,actions,purchase_roas', 'access_token': self.access_token}
            resp = requests.get(url, params=params).json()
            res = {}
            for item in resp.get('data', []):
                cid = item['campaign_id']
                inst = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                spend = float(item.get('spend', 0))
                roi = float(item['purchase_roas'][0]['value']) if item.get('purchase_roas') else 0
                imps = int(item.get('impressions', 0))
                clicks = int(item.get('clicks', 0))
                res[cid] = {'spend': spend, 'installs': inst, 'roi': roi, 'cpi': spend/inst if inst>0 else 0, 'clicks': clicks, 'ctr': clicks/imps if imps>0 else 0, 'cvr': inst/clicks if clicks>0 else 0, 'cpm': spend/imps*1000 if imps>0 else 0, 'cpc': spend/clicks if clicks>0 else 0, 'cpp': spend/sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] in ['purchase', 'fb_pixel_purchase']) if any(a['action_type'] in ['purchase', 'fb_pixel_purchase'] for a in item.get('actions', [])) else 0}
            return res
        except: return {}

    def evaluate_optimization_rules(self, campaigns, insights, history=None):
        cfg = self._load_config().get('strategy', {})
        CPI_T = float(cfg.get('CPI_THRESHOLD', 2.0))
        actions = []
        for camp in campaigns:
            cid = camp['id']
            if camp['effective_status'] != 'ACTIVE': continue
            ins = insights.get(cid, {})
            spend, cpi = ins.get('spend', 0), ins.get('cpi', 0)
            if cpi > CPI_T and spend > 50: actions.append({'type': 'PAUSE', 'cid': cid, 'name': camp['name'], 'reason': f"CPI (${cpi:.2f}) > {CPI_T}", 'risk': (spend > 200)})
        return actions

    def get_all_campaigns(self):
        try: return sorted(requests.get(f"{self.base_url}/{self.ad_account_id}/campaigns", params={'fields': 'id,name,status,effective_status,start_time,daily_budget', 'access_token': self.access_token, 'limit': 50}).json().get('data', []), key=lambda x: x.get('start_time', '0'), reverse=True)
        except: return []

    def update_campaign_status(self, cid, status):
        try: return requests.post(f"{self.base_url}/{cid}", data={'status': status, 'access_token': self.access_token}).json().get('success', False)
        except: return False

    def delete_campaign(self, cid):
        try: return requests.delete(f"{self.base_url}/{cid}", params={'access_token': self.access_token}).json().get('success', False)
        except: return False

    def get_ad_preview(self, campaign_id):
        """[增强] 获取该系列下第一个广告的实时预览 HTML"""
        try:
            # 1. 找广告 ID
            ads_res = requests.get(f"{self.base_url}/{campaign_id}/ads", params={'fields': 'id', 'access_token': self.access_token}).json()
            ad_id = ads_res.get('data', [{}])[0].get('id')
            if not ad_id: return None
            
            # 2. 生成预览 HTML
            # 使用 MOBILE_FEED_STANDARD 格式，最适合移动端剧集展示
            prev_res = requests.get(f"{self.base_url}/{ad_id}/previews", params={
                'ad_format': 'MOBILE_FEED_STANDARD', 
                'access_token': self.access_token
            }).json()
            return prev_res.get('data', [{}])[0].get('body')
        except: return None

    def execute_action(self, action):
        if action['type'] == 'PAUSE': return self.update_campaign_status(action['cid'], 'PAUSED')
        return False

    def _get_video_thumbnail_hash_smart(self, vid, token):
        for i in range(3):
            try:
                time.sleep(5)
                r = requests.get(f"{self.base_url}/{vid}", params={'fields': 'thumbnails', 'access_token': token}).json()
                if 'thumbnails' in r and r['thumbnails']['data']: return r['thumbnails']['data'][0].get('hash')
            except: pass
        return None
