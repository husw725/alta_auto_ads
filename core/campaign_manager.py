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
    """Meta ADS 管理器 v2.6.0: 极速开单版 (XMP 海报优先)"""
    
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
        except: return {"default": {"daily_budget": 50}, "strategy": {"CPI_THRESHOLD": 2.0}}

    def create_campaign(self, drama_name, video_url, thumb_url=None):
        """创建 Campaign (🚀 XMP 海报直传模式)"""
        try:
            token = self.access_token
            name_base = f"{drama_name}-US-{datetime.now().strftime('%Y%m%d')}-w2a-Auto-龙虾ai"
            
            # 1. 视频上传
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Video Fail: {v_resp}"}

            # 2. 🚀 缩略图决策 (翻转逻辑：优先用 XMP URL)
            img_hash = None
            if thumb_url:
                print(f"🚀 发现 XMP 海报，正在同步至 Meta: {thumb_url}")
                img_res = requests.post(f"{self.base_url}/{self.ad_account_id}/adimages", data={'copy_from_url': thumb_url, 'access_token': token}).json()
                if 'images' in img_res:
                    img_hash = img_res['images'][list(img_res['images'].keys())[0]]['hash']
                    print(f"✅ 海报上传成功: {img_hash}")

            # 如果 XMP 海报失败，才去尝试 Meta 抽帧 (作为保底)
            if not img_hash:
                print("⚠️ XMP 海报失效，尝试 Meta 官方抽帧保底...")
                img_hash = self._get_video_thumbnail_hash_smart(v_id, token)

            # 最终兜底链接 (S3)
            video_data = {'video_id': v_id, 'call_to_action': {'type': 'INSTALL_APP', 'value': {'link': self.official_store_url}}}
            if img_hash:
                video_data['image_hash'] = img_hash
            else:
                video_data['image_url'] = "https://starlitshorts.s3.amazonaws.com/s/986f2dd37aba040d55361a407ca860f5.png"

            # 3. 创建 Campaign
            c_id = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={'name': name_base, 'objective': 'OUTCOME_APP_PROMOTION', 'status': 'PAUSED', 'special_ad_categories': json.dumps(['NONE']), 'daily_budget': 5000, 'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 'access_token': token}).json().get('id')
            
            # 4. 创建 AdSet
            as_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data={'name': f"{name_base}-AS", 'campaign_id': c_id, 'optimization_goal': 'APP_INSTALLS', 'destination_type': 'APP', 'billing_event': 'IMPRESSIONS', 'promoted_object': json.dumps({'application_id': self.meta_app_id, 'object_store_url': self.official_store_url}), 'targeting': json.dumps({'geo_locations': {'countries': ['US']}, 'device_platforms': ['mobile'], 'user_os': ['iOS']}), 'status': 'PAUSED', 'access_token': token}).json().get('id')
            
            # 5. 创建 Creative
            cr_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={'name': f"{name_base}-Cr", 'object_story_spec': json.dumps({'page_id': self.page_id, 'video_data': video_data}), 'access_token': token}).json().get('id')
            
            # 6. 创建 Ad
            ad_id = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token}).json().get('id')
            
            # 7. 激活
            for rid in [c_id, as_id, ad_id]: requests.post(f"{self.base_url}/{rid}", data={'status': 'ACTIVE', 'access_token': token})
            
            return {'status': 'success', 'campaign_id': c_id}
        except Exception as e: return {'status': 'error', 'error': str(e)}

    def _get_video_thumbnail_hash_smart(self, vid, token):
        # 仅尝试 3 次 (15秒)，不再死等 40 秒
        for i in range(3):
            try:
                time.sleep(5)
                r = requests.get(f"{self.base_url}/{vid}", params={'fields': 'thumbnails', 'access_token': token}).json()
                if 'thumbnails' in r and r['thumbnails']['data']: return r['thumbnails']['data'][0].get('hash')
            except: pass
        return None

    def get_all_campaigns(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/campaigns"
            params = {'fields': 'id,name,status,effective_status,start_time,daily_budget', 'access_token': self.access_token, 'limit': 50}
            resp = requests.get(url, params=params).json()
            return resp.get('data', [])
        except: return []

    def get_yesterday_insights(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {'level': 'campaign', 'date_preset': 'yesterday', 'fields': 'campaign_id,spend,impressions,clicks,actions,purchase_roas', 'access_token': self.access_token}
            resp = requests.get(url, params=params).json()
            res = {}
            if 'data' in resp:
                for item in resp['data']:
                    cid = item['campaign_id']
                    installs = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                    spend = float(item.get('spend', 0))
                    roi = float(item['purchase_roas'][0]['value']) if item.get('purchase_roas') else 0
                    res[cid] = {'spend': spend, 'installs': installs, 'roi': roi, 'cpi': spend/installs if installs>0 else 0, 'clicks': int(item.get('clicks', 0)), 'ctr': int(item.get('clicks',0))/int(item.get('impressions',1))}
            return res
        except: return {}

    def get_historical_insights(self, days=7):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {'level': 'campaign', 'time_increment': 1, 'time_range': json.dumps({'since': (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'), 'until': datetime.now().strftime('%Y-%m-%d')}), 'fields': 'campaign_id,spend,actions,impressions', 'access_token': self.access_token}
            resp = requests.get(url, params=params).json()
            hist = {}
            for item in resp.get('data', []):
                cid = item['campaign_id']
                if cid not in hist: hist[cid] = []
                inst = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                spend = float(item.get('spend', 0))
                hist[cid].append({'spend': spend, 'imps': int(item.get('impressions', 0)), 'cpi': spend / inst if inst > 0 else 0})
            return hist
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
            if cpi > CPI_T and spend > 50:
                actions.append({'type': 'PAUSE', 'cid': cid, 'name': camp['name'], 'reason': f"CPI (${cpi:.2f}) > {CPI_T}", 'risk': (spend > 200)})
        return actions

    def update_campaign_status(self, cid, status):
        try: return requests.post(f"{self.base_url}/{cid}", data={'status': status, 'access_token': self.access_token}).json().get('success', False)
        except: return False

    def delete_campaign(self, cid):
        try: return requests.delete(f"{self.base_url}/{cid}", params={'access_token': self.access_token}).json().get('success', False)
        except: return False

    def execute_action(self, action):
        return self.update_campaign_status(action['cid'], 'PAUSED') if action['type'] == 'PAUSE' else False
