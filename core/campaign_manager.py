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
    """Meta ADS 管理器 v2.7.0: 完美集成版 (极速开单 + 完整调优 2.0)"""
    
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
        except: return {"default": {"daily_budget": 50}, "strategy": {"CPI_THRESHOLD": 2.0, "ROI_THRESHOLD": 0.5}}

    # --- 🚀 投流核心逻辑 (极速版) ---
    def create_campaign(self, drama_name, video_url, thumb_url=None):
        try:
            token = self.access_token
            today = datetime.now().strftime('%Y%m%d')
            name_base = f"{drama_name}-US-{today}-w2a-Auto-龙虾ai"
            
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Video Fail: {v_resp}"}

            # 缩略图决策：XMP 优先
            img_hash = None
            if thumb_url:
                img_res = requests.post(f"{self.base_url}/{self.ad_account_id}/adimages", data={'copy_from_url': thumb_url, 'access_token': token}).json()
                if 'images' in img_res: img_hash = img_res['images'][list(img_res['images'].keys())[0]]['hash']

            if not img_hash: img_hash = self._get_video_thumbnail_hash_smart(v_id, token)

            video_data = {'video_id': v_id, 'call_to_action': {'type': 'INSTALL_APP', 'value': {'link': self.official_store_url}}}
            if img_hash: video_data['image_hash'] = img_hash
            else: video_data['image_url'] = "https://starlitshorts.s3.amazonaws.com/s/986f2dd37aba040d55361a407ca860f5.png"

            # 创建全链路
            c_id = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={'name': name_base, 'objective': 'OUTCOME_APP_PROMOTION', 'status': 'PAUSED', 'special_ad_categories': json.dumps(['NONE']), 'daily_budget': 5000, 'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 'access_token': token}).json().get('id')
            as_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data={'name': f"{name_base}-AS", 'campaign_id': c_id, 'optimization_goal': 'APP_INSTALLS', 'destination_type': 'APP', 'billing_event': 'IMPRESSIONS', 'promoted_object': json.dumps({'application_id': self.meta_app_id, 'object_store_url': self.official_store_url}), 'targeting': json.dumps({'geo_locations': {'countries': ['US']}, 'device_platforms': ['mobile'], 'user_os': ['iOS']}), 'status': 'PAUSED', 'access_token': token}).json().get('id')
            cr_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={'name': f"{name_base}-Cr", 'object_story_spec': json.dumps({'page_id': self.page_id, 'video_data': video_data}), 'access_token': token}).json().get('id')
            ad_id = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token}).json().get('id')
            
            for rid in [c_id, as_id, ad_id]: requests.post(f"{self.base_url}/{rid}", data={'status': 'ACTIVE', 'access_token': token})
            return {'status': 'success', 'campaign_id': c_id}
        except Exception as e: return {'status': 'error', 'error': str(e)}

    # --- 🧠 智能调优引擎 2.0 (全血归来) ---
    def evaluate_optimization_rules(self, campaigns, insights, history=None):
        cfg = self._load_config().get('strategy', {})
        CPI_T = float(cfg.get('CPI_THRESHOLD', 2.0))
        ROI_T = float(cfg.get('ROI_THRESHOLD', 0.5))
        actions = []

        for camp in campaigns:
            cid = camp['id']
            if camp['effective_status'] != 'ACTIVE': continue
            ins = insights.get(cid, {})
            spend, cpi, roi = ins.get('spend', 0), ins.get('cpi', 0), ins.get('roi', 0)

            # 1. 暂停劣质 (CPI > T 且 Spend > $50)
            if cpi > CPI_T and spend > 50:
                actions.append({'type': 'PAUSE', 'cid': cid, 'name': camp['name'], 'reason': f"CPI (${cpi:.2f}) > {CPI_T}", 'risk': (spend > 200)})
            
            # 2. 降低预算 (CPI > T*0.8 且 Spend > $30)
            elif cpi > (CPI_T * 0.8) and spend > 30:
                curr_b = float(camp.get('daily_budget', 0)) / 100
                actions.append({'type': 'BUDGET', 'cid': cid, 'name': camp['name'], 'value': curr_b * 0.5, 'reason': "CPI 接近阈值，降预算 50%", 'risk': (curr_b * 0.5 > 100)})
            
            # 3. 提升预算 (CPI < T*0.6 且 ROI > T*1.2)
            elif spend > 10 and cpi < (CPI_T * 0.6) and roi > (ROI_T * 1.2):
                curr_b = float(camp.get('daily_budget', 0)) / 100
                actions.append({'type': 'BUDGET', 'cid': cid, 'name': camp['name'], 'value': curr_b * 1.3, 'reason': f"表现优异 (ROI:{roi:.2f})，提预算 30%", 'risk': (curr_b * 0.3 > 100)})

            # 4. 趋势分析 (需历史数据)
            if history and cid in history:
                h = history[cid]
                if len(h) >= 3 and all(d['cpi'] > CPI_T for d in h[-3:]):
                    actions.append({'type': 'BID', 'cid': cid, 'name': camp['name'], 'action': 'LOWER', 'reason': "CPI 连续 3 天超标"})
                if len(h) >= 2:
                    prev, curr = h[-2]['imps'], h[-1]['imps']
                    if prev > 0 and (prev - curr) / prev > 0.3:
                        actions.append({'type': 'BID', 'cid': cid, 'name': camp['name'], 'action': 'HIGHER', 'reason': "展示量骤降 > 30%"})
        return actions

    # --- 数据抓取与执行 ---
    def get_yesterday_insights(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {'level': 'campaign', 'date_preset': 'yesterday', 'fields': 'campaign_id,spend,impressions,clicks,actions,purchase_roas', 'access_token': self.access_token}
            resp = requests.get(url, params=params).json()
            res = {}
            for item in resp.get('data', []):
                cid = item['campaign_id']
                inst = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                spend = float(item.get('spend', 0))
                roi = float(item['purchase_roas'][0]['value']) if item.get('purchase_roas') else 0
                res[cid] = {'spend': spend, 'installs': inst, 'roi': roi, 'cpi': spend/inst if inst>0 else 0, 'clicks': int(item.get('clicks', 0)), 'imps': int(item.get('impressions', 0)), 'ctr': int(item.get('clicks', 0))/int(item.get('impressions', 1))}
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
                hist[cid].append({'cpi': spend/inst if inst>0 else 0, 'imps': int(item.get('impressions', 0))})
            return hist
        except: return {}

    def get_all_campaigns(self):
        try:
            resp = requests.get(f"{self.base_url}/{self.ad_account_id}/campaigns", params={'fields': 'id,name,status,effective_status,start_time,daily_budget', 'access_token': self.access_token, 'limit': 50}).json()
            return sorted(resp.get('data', []), key=lambda x: x.get('start_time', '0'), reverse=True)
        except: return []

    def execute_action(self, action):
        try:
            if action['type'] == 'PAUSE': return requests.post(f"{self.base_url}/{action['cid']}", data={'status': 'PAUSED', 'access_token': self.access_token}).json().get('success', False)
            if action['type'] == 'BUDGET': return requests.post(f"{self.base_url}/{action['cid']}", data={'daily_budget': int(action['value'] * 100), 'access_token': self.access_token}).json().get('success', False)
            return True # BID 逻辑模拟
        except: return False

    def update_campaign_status(self, cid, status):
        try: return requests.post(f"{self.base_url}/{cid}", data={'status': status, 'access_token': self.access_token}).json().get('success', False)
        except: return False

    def delete_campaign(self, cid):
        try: return requests.delete(f"{self.base_url}/{cid}", params={'access_token': self.access_token}).json().get('success', False)
        except: return False

    def _get_video_thumbnail_hash_smart(self, vid, token):
        for i in range(3):
            try:
                time.sleep(5)
                r = requests.get(f"{self.base_url}/{vid}", params={'fields': 'thumbnails', 'access_token': token}).json()
                if 'thumbnails' in r and r['thumbnails']['data']: return r['thumbnails']['data'][0].get('hash')
            except: pass
        return None
