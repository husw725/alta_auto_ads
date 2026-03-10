import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """管理 Meta ADS Campaign (回归最稳初始版本)"""
    
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

    def get_all_campaigns(self):
        """获取所有 Campaign (增加绝对安全的 Key 检查)"""
        try:
            # 1. 获取 AdSets 预算信息
            url = f"{self.base_url}/{self.ad_account_id}/adsets"
            params = {'fields': 'campaign_id,daily_budget,lifetime_budget,status', 'access_token': self.access_token, 'limit': 150}
            resp = requests.get(url, params=params).json()
            
            adsets_map = {}
            if 'data' in resp:
                for item in resp['data']:
                    cid = item.get('campaign_id')
                    if cid:
                        db = float(item.get('daily_budget', 0)) / 100
                        lb = float(item.get('lifetime_budget', 0)) / 100
                        adsets_map[cid] = {'budget': db if db > 0 else lb}
            
            # 2. 获取 Campaign 基础信息
            url = f"{self.base_url}/{self.ad_account_id}/campaigns"
            params = {'fields': 'name,status,effective_status,start_time', 'access_token': self.access_token, 'limit': 100}
            c_resp = requests.get(url, params=params).json()
            
            final_list = []
            if 'data' in c_resp:
                for c in c_resp['data']:
                    cid = c.get('id')
                    if cid:
                        c.update(adsets_map.get(cid, {'budget': 0}))
                        final_list.append(c)
            return sorted(final_list, key=lambda x: x.get('start_time', '0'), reverse=True)
        except Exception as e:
            print(f"❌ Get Campaigns Error: {e}")
            return []

    def update_campaign_status(self, campaign_id, status):
        """修改状态"""
        try:
            url = f"{self.base_url}/{campaign_id}"
            params = {'status': status, 'access_token': self.access_token}
            return requests.post(url, data=params).json().get('success', False)
        except: return False

    def create_campaign(self, drama_name, video_url):
        """创建 Campaign (回归最初 PAUSED 稳定版，禁止任何自动激活逻辑)"""
        try:
            if not video_url: return {'status': 'error', 'error': 'Video URL is empty'}
            
            cfg = self._load_config().get('default', {"country": "US", "daily_budget": 50})
            country = cfg.get('country', 'US')
            budget = cfg.get('daily_budget', 50)
            goal = cfg.get('optimization_goal', 'MOBILE_APP_INSTALLS')
            
            today = datetime.now().strftime("%Y%m%d")
            name_base = f"{drama_name}-{country}-{today}-Auto"
            token = self.access_token

            # Step 1: Video
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Video Error: {v_resp}"}
            
            # Step 2: Campaign (PAUSED)
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={'name': name_base, 'objective': 'OUTCOME_SALES', 'status': 'PAUSED', 'access_token': token}).json()
            c_id = c_resp.get('id')
            if not c_id: return {'status': 'error', 'error': f"Campaign Error: {c_resp}"}
            
            # Step 3: AdSet (PAUSED)
            as_payload = {
                'name': f"{name_base}-AS",
                'campaign_id': c_id,
                'daily_budget': int(budget * 100),
                'optimization_goal': 'OFFSITE_CONVERSIONS',
                'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({'pixel_id': self.pixel_id, 'custom_event_type': 'CONTENT_VIEW' if goal == 'CONTENT_VIEW' else 'MOBILE_APP_INSTALLS'}),
                'targeting': json.dumps({'geo_locations': {'countries': [country]}, 'device_platforms': ['mobile']}),
                'status': 'PAUSED',
                'access_token': token
            }
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data=as_payload).json()
            as_id = as_resp.get('id')
            if not as_id: return {'status': 'error', 'error': f"AdSet Error: {as_resp}"}
            
            # Step 4: Creative & Ad
            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy = writer.generate_copy(drama_name).get('versions', [{}])[0]
            story_spec = {'page_id': self.page_id, 'video_data': {'video_id': v_id, 'message': copy.get('primary_text', 'Watch now!')}}
            cr_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={'name': f"{name_base}-Cr", 'object_story_spec': json.dumps(story_spec), 'access_token': token}).json()
            cr_id = cr_resp.get('id')
            if not cr_id: return {'status': 'error', 'error': f"Creative Error: {cr_resp}"}
            
            ad_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token}).json()
            ad_id = ad_resp.get('id')
            if not ad_id: return {'status': 'error', 'error': f"Ad Error: {ad_resp}"}
            
            return {'status': 'success', 'campaign_id': c_id}
        except Exception as e:
            return {'status': 'error', 'error': f"Critical Runtime Error: {str(e)}"}

    # 保持其他方法精简稳定
    def get_yesterday_insights(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {'level': 'campaign', 'date_preset': 'yesterday', 'fields': 'campaign_id,spend,actions,purchase_roas', 'access_token': self.access_token}
            resp = requests.get(url, params=params).json()
            insights = {}
            for item in resp.get('data', []):
                installs = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                insights[item['campaign_id']] = {'spend': float(item.get('spend', 0)), 'installs': installs, 'roi': float(item['purchase_roas'][0]['value']) if item.get('purchase_roas') else 0}
            return insights
        except: return {}

    def get_historical_insights(self, days=7):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {'level': 'campaign', 'time_range': json.dumps({'since': (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'), 'until': datetime.now().strftime('%Y-%m-%d')}), 'time_increment': 1, 'fields': 'campaign_id,spend,actions', 'access_token': self.access_token}
            resp = requests.get(url, params=params).json()
            history = {}
            for item in resp.get('data', []):
                cid = item['campaign_id']
                if cid not in history: history[cid] = []
                installs = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                history[cid].append({'spend': float(item.get('spend', 0)), 'installs': installs})
            return history
        except: return {}

    def evaluate_optimization_rules(self, campaigns, insights, history):
        return [] # 暂时关闭智能优化建议，优先恢复投流功能
