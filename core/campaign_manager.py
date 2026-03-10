import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """管理 Meta ADS Campaign (修复 ID 字段缺失的关键稳健版)"""
    
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        self.pixel_id = os.getenv('META_PIXEL_ID')
        self.app_link = os.getenv('META_APP_LINK')
        self.base_url = "https://graph.facebook.com/v21.0"

    def _load_config(self):
        try:
            with open('config/config.json', 'r') as f: return json.load(f)
        except: return {"default": {"country": "US", "daily_budget": 50}}

    def get_all_campaigns(self):
        """获取所有 Campaign (显式请求 id 字段)"""
        try:
            # 1. 获取 AdSets (显式请求 id 和 campaign_id)
            url = f"{self.base_url}/{self.ad_account_id}/adsets"
            params = {'fields': 'id,campaign_id,daily_budget,lifetime_budget,status', 'access_token': self.access_token, 'limit': 150}
            resp = requests.get(url, params=params).json()
            
            adsets_map = {}
            if 'data' in resp:
                for item in resp['data']:
                    cid = item.get('campaign_id')
                    if cid:
                        db = float(item.get('daily_budget', 0)) / 100
                        lb = float(item.get('lifetime_budget', 0)) / 100
                        adsets_map[cid] = {'adset_id': item.get('id'), 'budget': db if db > 0 else lb}
            
            # 2. 获取 Campaign (显式请求 id 字段！！)
            url = f"{self.base_url}/{self.ad_account_id}/campaigns"
            params = {'fields': 'id,name,status,effective_status,start_time', 'access_token': self.access_token, 'limit': 100}
            c_resp = requests.get(url, params=params).json()
            
            final_list = []
            if 'data' in c_resp:
                for c in c_resp['data']:
                    cid = c.get('id')
                    if cid:
                        c.update(adsets_map.get(cid, {'budget': 0, 'adset_id': None}))
                        final_list.append(c)
            return sorted(final_list, key=lambda x: x.get('start_time', '0'), reverse=True)
        except Exception as e:
            print(f"❌ Error: {e}")
            return []

    def create_campaign(self, drama_name, video_url):
        """创建 Campaign (PAUSED 稳定版)"""
        try:
            if not video_url: return {'status': 'error', 'error': 'No Video URL'}
            cfg = self._load_config().get('default', {"country": "US", "daily_budget": 50})
            country, budget, goal = cfg.get('country', 'US'), cfg.get('daily_budget', 50), cfg.get('optimization_goal', 'MOBILE_APP_INSTALLS')
            token = self.access_token
            name_base = f"{drama_name}-{country}-{datetime.now().strftime('%m%d')}"

            # Step 1: Video
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"V-Fail: {v_resp}"}
            
            # Step 2: Campaign
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={'name': name_base, 'objective': 'OUTCOME_SALES', 'status': 'PAUSED', 'access_token': token}).json()
            c_id = c_resp.get('id')
            if not c_id: return {'status': 'error', 'error': f"C-Fail: {c_resp}"}
            
            # Step 3: AdSet
            as_payload = {
                'name': f"{name_base}-AS", 'campaign_id': c_id, 'daily_budget': int(budget * 100),
                'optimization_goal': 'OFFSITE_CONVERSIONS', 'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({'pixel_id': self.pixel_id, 'custom_event_type': 'CONTENT_VIEW' if goal == 'CONTENT_VIEW' else 'MOBILE_APP_INSTALLS'}),
                'targeting': json.dumps({'geo_locations': {'countries': [country]}, 'device_platforms': ['mobile']}),
                'status': 'PAUSED', 'access_token': token
            }
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data=as_payload).json()
            as_id = as_resp.get('id')
            if not as_id: return {'status': 'error', 'error': f"AS-Fail: {as_resp}"}
            
            # Step 4: Creative & Ad
            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy = writer.generate_copy(drama_name).get('versions', [{}])[0]
            story_spec = {'page_id': self.page_id, 'video_data': {'video_id': v_id, 'message': copy.get('primary_text', 'Watch now!')}}
            cr_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={'name': f"{name_base}-Cr", 'object_story_spec': json.dumps(story_spec), 'access_token': token}).json()
            cr_id = cr_resp.get('id')
            
            ad_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token}).json()
            if 'id' not in ad_resp: return {'status': 'error', 'error': f"Ad-Fail: {ad_resp}"}
            
            return {'status': 'success', 'campaign_id': c_id}
        except Exception as e:
            return {'status': 'error', 'error': f"Exception: {str(e)}"}

    def update_campaign_status(self, cid, status):
        try: return requests.post(f"{self.base_url}/{cid}", data={'status': status, 'access_token': self.access_token}).json().get('success', False)
        except: return False

    def get_yesterday_insights(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {'level': 'campaign', 'date_preset': 'yesterday', 'fields': 'campaign_id,spend,actions,purchase_roas', 'access_token': self.access_token}
            resp = requests.get(url, params=params).json()
            res = {}
            for item in resp.get('data', []):
                inst = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                roi = float(item['purchase_roas'][0]['value']) if item.get('purchase_roas') else 0
                res[item['campaign_id']] = {'spend': float(item.get('spend', 0)), 'installs': inst, 'roi': roi}
            return res
        except: return {}

    def get_historical_insights(self, days=7):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {'level': 'campaign', 'time_range': json.dumps({'since': (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'), 'until': datetime.now().strftime('%Y-%m-%d')}), 'time_increment': 1, 'fields': 'campaign_id,spend,impressions,actions', 'access_token': self.access_token}
            resp = requests.get(url, params=params).json()
            hist = {}
            for item in resp.get('data', []):
                cid = item['campaign_id']
                if cid not in hist: hist[cid] = []
                inst = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                hist[cid].append({'date': item.get('date_start'), 'spend': float(item.get('spend', 0)), 'imps': int(item.get('impressions', 0)), 'installs': inst})
            return hist
        except: return {}

    def evaluate_optimization_rules(self, camps, ins, hist):
        return []
