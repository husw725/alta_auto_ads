import os
import requests
import json
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """Meta ADS 管理器 v1.9.1: 深度参数补全版"""
    
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        # 正式 Meta App ID
        self.meta_app_id = "1807921329643155"
        # 正式商店链接
        self.app_link = os.getenv('META_APP_LINK', 'https://apps.apple.com/app/id6504221151')
        self.base_url = "https://graph.facebook.com/v21.0"

    def _load_config(self):
        try:
            with open('config/config.json', 'r') as f: return json.load(f)
        except: return {"default": {"country": "US", "daily_budget": 50}, "strategy": {"CPI_THRESHOLD": 2.0}}

    def get_all_campaigns(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/campaigns"
            params = {'fields': 'id,name,status,effective_status,start_time,daily_budget,lifetime_budget', 'access_token': self.access_token, 'limit': 50}
            resp = requests.get(url, params=params).json()
            return sorted(resp.get('data', []), key=lambda x: x.get('start_time', '0'), reverse=True)
        except: return []

    def create_campaign(self, drama_name, video_url):
        try:
            cfg = self._load_config().get('default', {})
            budget = int(cfg.get('daily_budget', 50))
            country = cfg.get('country', 'US')
            token = self.access_token
            name_base = f"{drama_name}-{country}-{datetime.now().strftime('%m%d%H%M')}"

            # 1. Video
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Video Fail: {v_resp}"}

            # 2. Campaign
            c_payload = {
                'name': name_base, 'objective': 'OUTCOME_APP_PROMOTION', 'status': 'PAUSED',
                'special_ad_categories': json.dumps(['NONE']), 'daily_budget': budget * 100,
                'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 'access_token': token
            }
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data=c_payload).json()
            c_id = c_resp.get('id')
            if not c_id: return {'status': 'error', 'error': f"Campaign Fail: {c_resp}"}

            # 3. AdSet (补充 object_store_url)
            as_payload = {
                'name': f"{name_base}-AS", 'campaign_id': c_id, 'optimization_goal': 'APP_INSTALLS',
                'destination_type': 'APP', 'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({
                    'application_id': self.meta_app_id,
                    'object_store_url': self.app_link # 补全商店链接参数
                }),
                'targeting': json.dumps({'geo_locations': {'countries': [country]}, 'device_platforms': ['mobile']}),
                'status': 'PAUSED', 'access_token': token
            }
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data=as_payload).json()
            as_id = as_resp.get('id')
            if not as_id: return {'status': 'error', 'error': f"AdSet Fail: {as_resp}"}

            # 4. Creative
            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy = writer.generate_copy(drama_name).get('versions', [{}])[0]
            story_spec = {'page_id': self.page_id, 'video_data': {'video_id': v_id, 'message': copy.get('primary_text', 'New Drama on AltaTV!')}}
            cr_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={'name': f"{name_base}-Cr", 'object_story_spec': json.dumps(story_spec), 'access_token': token}).json()
            cr_id = cr_resp.get('id')
            
            # 5. Ad
            ad_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token}).json()
            ad_id = ad_resp.get('id')
            if not ad_id: return {'status': 'error', 'error': f"Ad Fail: {ad_resp}"}

            # 6. Auto Activate
            requests.post(f"{self.base_url}/{c_id}", data={'status': 'ACTIVE', 'access_token': token})
            requests.post(f"{self.base_url}/{as_id}", data={'status': 'ACTIVE', 'access_token': token})
            requests.post(f"{self.base_url}/{ad_id}", data={'status': 'ACTIVE', 'access_token': token})

            return {'status': 'success', 'campaign_id': c_id}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def update_campaign_status(self, cid, status):
        try: return requests.post(f"{self.base_url}/{cid}", data={'status': status, 'access_token': self.access_token}).json().get('success', False)
        except: return False

    def execute_action(self, action):
        token = self.access_token
        try:
            if action['type'] == 'PAUSE':
                return requests.post(f"{self.base_url}/{action['cid']}", data={'status': 'PAUSED', 'access_token': token}).json().get('success', False)
            elif action['type'] == 'BUDGET':
                return requests.post(f"{self.base_url}/{action['cid']}", data={'daily_budget': int(action['value'] * 100), 'access_token': token}).json().get('success', False)
            return False
        except: return False

    def get_yesterday_insights(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {'level': 'campaign', 'date_preset': 'yesterday', 'fields': 'campaign_id,spend,actions,purchase_roas', 'access_token': self.access_token}
            resp = requests.get(url, params=params).json()
            res = {}
            if 'data' in resp:
                for item in resp['data']:
                    inst = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                    roi = float(item['purchase_roas'][0]['value']) if item.get('purchase_roas') else 0
                    res[item['campaign_id']] = {'spend': float(item.get('spend', 0)), 'installs': inst, 'roi': roi, 'cpi': float(item.get('spend', 0))/inst if inst > 0 else 0}
            return res
        except: return {}

    def get_historical_insights(self, days=7):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {'level': 'campaign', 'time_range': json.dumps({'since': (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'), 'until': datetime.now().strftime('%Y-%m-%d')}), 'time_increment': 1, 'fields': 'campaign_id,spend,actions', 'access_token': self.access_token}
            resp = requests.get(url, params=params).json()
            hist = {}
            for item in resp.get('data', []):
                cid = item['campaign_id']
                if cid not in hist: hist[cid] = []
                inst = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                hist[cid].append({'spend': float(item.get('spend', 0)), 'installs': inst, 'cpi': float(item.get('spend', 0))/inst if inst > 0 else 0})
            return hist
        except: return {}

    def evaluate_optimization_rules(self, campaigns, insights, history):
        strat = self._load_config().get('strategy', {})
        threshold = strat.get('CPI_THRESHOLD', 2.0)
        actions = []
        for c in campaigns:
            cid = c['id']
            ins = insights.get(cid, {})
            spend, cpi = ins.get('spend', 0), ins.get('cpi', 0)
            if cpi > threshold and spend > 10:
                actions.append({'type': 'PAUSE', 'cid': cid, 'name': c.get('name'), 'reason': f"CPI (${cpi:.2f}) > 阈值"})
        return actions
