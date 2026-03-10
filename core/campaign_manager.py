import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """管理 Meta ADS Campaign (回归稳定 PAUSED 模式)"""
    
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        self.pixel_id = os.getenv('META_PIXEL_ID')
        self.app_link = os.getenv('META_APP_LINK')
        self.base_url = "https://graph.facebook.com/v21.0"
        self.media_buyer = "Auto ADS"

    def _load_config(self):
        try:
            with open('config/config.json', 'r') as f: return json.load(f)
        except: return {"default": {"country": "US", "daily_budget": 50}}

    def create_campaign(self, drama_name, video_url):
        """创建 Campaign (纯暂停模式，不包含任何激活逻辑)"""
        print(f"🚀 [Debug] Starting creation for: {drama_name}")
        print(f"🔗 [Debug] Video URL: {video_url}")
        
        try:
            if not video_url: return {'status': 'error', 'error': 'No video URL'}
            
            cfg = self._load_config().get('default', {"country": "US", "daily_budget": 50})
            country, budget, goal = cfg.get('country', 'US'), cfg.get('daily_budget', 50), cfg.get('optimization_goal', 'MOBILE_APP_INSTALLS')
            
            today = datetime.now().strftime("%Y%m%d")
            name_base = f"{drama_name}-{country}-{today}-Auto"
            token = self.access_token

            # 1. Upload Video
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            if 'id' not in v_resp: return {'status': 'error', 'error': f"Step 1 Video Fail: {v_resp}"}
            v_id = v_resp['id']
            print(f"✅ Video Uploaded: {v_id}")
            
            # 2. Create Campaign (PAUSED)
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={'name': name_base, 'objective': 'OUTCOME_SALES', 'status': 'PAUSED', 'access_token': token}).json()
            if 'id' not in c_resp: return {'status': 'error', 'error': f"Step 2 Campaign Fail: {c_resp}"}
            c_id = c_resp['id']
            print(f"✅ Campaign Created: {c_id}")
            
            # 3. Create AdSet (PAUSED)
            as_payload = {
                'name': f"{name_base}-AS", 'campaign_id': c_id, 'daily_budget': int(budget * 100),
                'optimization_goal': 'OFFSITE_CONVERSIONS', 'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({'pixel_id': self.pixel_id, 'custom_event_type': 'CONTENT_VIEW' if goal == 'CONTENT_VIEW' else 'MOBILE_APP_INSTALLS'}),
                'targeting': json.dumps({'geo_locations': {'countries': [country]}, 'device_platforms': ['mobile']}),
                'status': 'PAUSED', 'access_token': token
            }
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data=as_payload).json()
            if 'id' not in as_resp: return {'status': 'error', 'error': f"Step 3 AdSet Fail: {as_resp}"}
            as_id = as_resp['id']
            print(f"✅ AdSet Created: {as_id}")
            
            # 4. Creative
            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy = writer.generate_copy(drama_name).get('versions', [{}])[0]
            story_spec = {'page_id': self.page_id, 'video_data': {'video_id': v_id, 'message': copy.get('primary_text', 'Watch now!')}}
            cr_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={'name': f"{name_base}-Cr", 'object_story_spec': json.dumps(story_spec), 'access_token': token}).json()
            if 'id' not in cr_resp: return {'status': 'error', 'error': f"Step 4 Creative Fail: {cr_resp}"}
            cr_id = cr_resp['id']
            print(f"✅ Creative Created: {cr_id}")
            
            # 5. Ad (PAUSED)
            ad_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token}).json()
            if 'id' not in ad_resp: return {'status': 'error', 'error': f"Step 5 Ad Fail: {ad_resp}"}
            print(f"✅ Ad Created: {ad_resp['id']}")

            return {'status': 'success', 'campaign_id': c_id}
        except Exception as e:
            return {'status': 'error', 'error': f"Runtime Error: {str(e)}"}

    # 保持其他方法同步
    def get_all_campaigns(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/adsets"
            params = {'fields': 'name,status,effective_status,campaign_id,daily_budget,lifetime_budget,bid_amount', 'access_token': self.access_token, 'limit': 100}
            resp = requests.get(url, params=params).json()
            adsets_map = {item['campaign_id']: {'budget': float(item.get('daily_budget', 0))/100, 'adset_id': item['id']} for item in resp.get('data', [])}
            url = f"{self.base_url}/{self.ad_account_id}/campaigns"
            params = {'fields': 'name,status,effective_status,start_time', 'access_token': self.access_token, 'limit': 100}
            c_resp = requests.get(url, params=params).json()
            final_list = []
            for c in c_resp.get('data', []):
                c.update(adsets_map.get(c['id'], {'budget': 0, 'adset_id': None}))
                final_list.append(c)
            return sorted(final_list, key=lambda x: x.get('start_time', '0'), reverse=True)
        except: return []

    def update_campaign_status(self, cid, status):
        try: return requests.post(f"{self.base_url}/{cid}", data={'status': status, 'access_token': self.access_token}).json().get('success', False)
        except: return False

    def get_yesterday_insights(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {'level': 'campaign', 'date_preset': 'yesterday', 'fields': 'campaign_id,spend,impressions,inline_link_clicks,actions,purchase_roas', 'access_token': self.access_token, 'limit': 100}
            resp = requests.get(url, params=params).json()
            insights_map = {}
            for item in resp.get('data', []):
                installs = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                insights_map[item['campaign_id']] = {'spend': float(item.get('spend', 0)), 'installs': installs, 'roi': float(item['purchase_roas'][0]['value']) if item.get('purchase_roas') else 0}
            return insights_map
        except: return {}

    def get_historical_insights(self, days=7):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {'level': 'campaign', 'time_range': json.dumps({'since': (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'), 'until': datetime.now().strftime('%Y-%m-%d')}), 'time_increment': 1, 'fields': 'campaign_id,spend,impressions,actions', 'access_token': self.access_token, 'limit': 500}
            resp = requests.get(url, params=params).json()
            history = {}
            for item in resp.get('data', []):
                cid = item['campaign_id']
                if cid not in history: history[cid] = []
                installs = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                history[cid].append({'date': item.get('date_start'), 'spend': float(item.get('spend', 0)), 'imps': int(item.get('impressions', 0)), 'installs': installs})
            return history
        except: return {}

    def evaluate_optimization_rules(self, campaigns, insights, history):
        strat = self._load_config().get('strategy', {"CPI_THRESHOLD": 2.0})
        actions = []
        for c in campaigns:
            cid, aid = c['id'], c.get('adset_id')
            if not aid or c['effective_status'] != 'ACTIVE': continue
            ins = insights.get(cid, {})
            spend, cpi = ins.get('spend', 0), ins.get('spend', 0)/ins.get('installs', 1)
            if cpi > strat.get('CPI_THRESHOLD', 2.0) and spend > 50:
                actions.append({'type': 'PAUSE', 'cid': cid, 'name': c['name'], 'reason': f"CPI (${cpi:.2f}) 偏高"})
        return actions

    def execute_action(self, action):
        try:
            if action['type'] == 'PAUSE': return self.update_campaign_status(action['cid'], 'PAUSED')
            return False
        except: return False
