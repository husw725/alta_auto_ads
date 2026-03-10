import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """管理 Meta ADS Campaign 的创建、监控、修改与深度效果分析 (智能优化加固版)"""
    
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        self.pixel_id = os.getenv('META_PIXEL_ID')
        self.app_link = os.getenv('META_APP_LINK') # 修正为 .env 中的字段名
        self.base_url = "https://graph.facebook.com/v21.0"
        self.media_buyer = "Auto ADS"

    def _load_config(self):
        try:
            with open('config/config.json', 'r') as f: return json.load(f)
        except: return {"default": {"country": "US", "daily_budget": 50}, "strategy": {"CPI_THRESHOLD": 2.0}}

    def create_campaign(self, drama_name, video_url):
        """创建 Campaign (采用两阶段法：创建 -> 激活)"""
        try:
            if not video_url: return {'status': 'error', 'error': 'No video URL provided'}
            
            cfg_full = self._load_config()
            cfg = cfg_full.get('default', {})
            country = cfg.get('country', 'US')
            budget = cfg.get('daily_budget', 50.0)
            goal = cfg.get('optimization_goal', 'MOBILE_APP_INSTALLS')
            
            today = datetime.now().strftime("%Y%m%d")
            name_base = f"{drama_name}-{country}-{today}-Auto-{self.media_buyer}"
            token = self.access_token

            # 1. Upload Video
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            if 'id' not in v_resp: return {'status': 'error', 'error': f"Video Upload Fail: {v_resp}"}
            v_id = v_resp['id']
            
            # 2. Step 1: Create as PAUSED
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={'name': name_base, 'objective': 'OUTCOME_SALES', 'status': 'PAUSED', 'access_token': token}).json()
            if 'id' not in c_resp: return {'status': 'error', 'error': f"Campaign Create Fail: {c_resp}"}
            c_id = c_resp['id']
            
            as_payload = {
                'name': f"{name_base}-AS", 'campaign_id': c_id, 'daily_budget': int(budget * 100),
                'optimization_goal': 'OFFSITE_CONVERSIONS', 'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({'pixel_id': self.pixel_id, 'custom_event_type': 'CONTENT_VIEW' if goal == 'CONTENT_VIEW' else 'MOBILE_APP_INSTALLS'}),
                'targeting': json.dumps({'geo_locations': {'countries': [country]}, 'device_platforms': ['mobile']}),
                'status': 'PAUSED', 'access_token': token
            }
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data=as_payload).json()
            if 'id' not in as_resp: return {'status': 'error', 'error': f"AdSet Create Fail: {as_resp}"}
            as_id = as_resp['id']
            
            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy_res = writer.generate_copy(drama_name)
            copy = copy_res.get('versions', [{}])[0] if (isinstance(copy_res, dict) and 'versions' in copy_res) else {}
            
            story_spec = {'page_id': self.page_id, 'video_data': {'video_id': v_id, 'message': copy.get('primary_text', 'Watch now!')}}
            cr_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={'name': f"{name_base}-Cr", 'object_story_spec': json.dumps(story_spec), 'access_token': token}).json()
            if 'id' not in cr_resp: return {'status': 'error', 'error': f"Creative Create Fail: {cr_resp}"}
            cr_id = cr_resp['id']
            
            ad_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token}).json()
            if 'id' not in ad_resp: return {'status': 'error', 'error': f"Ad Create Fail: {ad_resp}"}
            ad_id = ad_resp['id']

            # 3. Step 2: Auto Activate
            requests.post(f"{self.base_url}/{c_id}", data={'status': 'ACTIVE', 'access_token': token})
            requests.post(f"{self.base_url}/{as_id}", data={'status': 'ACTIVE', 'access_token': token})
            requests.post(f"{self.base_url}/{ad_id}", data={'status': 'ACTIVE', 'access_token': token})
            
            return {'status': 'success', 'campaign_id': c_id}
        except Exception as e:
            return {'status': 'error', 'error': f"Exception: {str(e)}"}

    def get_all_campaigns(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/adsets"
            params = {'fields': 'name,status,effective_status,campaign_id,daily_budget,lifetime_budget,bid_amount', 'access_token': self.access_token, 'limit': 100}
            resp = requests.get(url, params=params).json()
            adsets_map = {}
            if 'data' in resp:
                for item in resp['data']:
                    db = float(item.get('daily_budget', 0)) / 100
                    lb = float(item.get('lifetime_budget', 0)) / 100
                    adsets_map[item['campaign_id']] = {'adset_id': item['id'], 'budget': db if db > 0 else lb, 'bid': float(item.get('bid_amount', 0)) / 100}
            url = f"{self.base_url}/{self.ad_account_id}/campaigns"
            params = {'fields': 'name,status,effective_status,start_time', 'access_token': self.access_token, 'limit': 100}
            c_resp = requests.get(url, params=params).json()
            final_list = []
            if 'data' in c_resp:
                for c in c_resp['data']:
                    info = adsets_map.get(c['id'], {'budget': 0, 'bid': 0, 'adset_id': None})
                    c.update(info)
                    final_list.append(c)
            return sorted(final_list, key=lambda x: x.get('start_time', '0'), reverse=True)
        except: return []

    def update_campaign_status(self, campaign_id, status):
        try:
            url = f"{self.base_url}/{campaign_id}"
            params = {'status': status, 'access_token': self.access_token}
            return requests.post(url, data=params).json().get('success', False)
        except: return False

    def get_yesterday_insights(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {'level': 'campaign', 'date_preset': 'yesterday', 'fields': 'campaign_id,spend,impressions,inline_link_clicks,actions,purchase_roas', 'access_token': self.access_token, 'limit': 100}
            resp = requests.get(url, params=params).json()
            insights_map = {}
            if 'data' in resp:
                for item in resp['data']:
                    cid, spend, imps, clicks = item['campaign_id'], float(item.get('spend', 0)), int(item.get('impressions', 0)), int(item.get('inline_link_clicks', 0))
                    installs = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                    roi = float(item['purchase_roas'][0]['value']) if item.get('purchase_roas') else 0
                    insights_map[cid] = {'spend': spend, 'imps': imps, 'clicks': clicks, 'installs': installs, 'roi': roi, 'ctr': (clicks/imps if imps>0 else 0), 'cvr': (installs/clicks if clicks>0 else 0), 'cpi': (spend/installs if installs>0 else 0)}
            return insights_map
        except: return {}

    def get_historical_insights(self, days=7):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {'level': 'campaign', 'time_range': json.dumps({'since': (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'), 'until': datetime.now().strftime('%Y-%m-%d')}), 'time_increment': 1, 'fields': 'campaign_id,spend,impressions,actions', 'access_token': self.access_token, 'limit': 500}
            resp = requests.get(url, params=params).json()
            history = {}
            if 'data' in resp:
                for item in resp['data']:
                    cid = item['campaign_id']
                    if cid not in history: history[cid] = []
                    spend, imps = float(item.get('spend', 0)), int(item.get('impressions', 0))
                    installs = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                    history[cid].append({'date': item.get('date_start'), 'spend': spend, 'imps': imps, 'installs': installs, 'cpi': spend/installs if installs>0 else 0})
            return history
        except: return {}

    def evaluate_optimization_rules(self, campaigns, insights, history):
        cfg = self._load_config(); strat = cfg.get('strategy', {}); threshold = strat.get('CPI_THRESHOLD', 2.0); roi_target = strat.get('ROI_THRESHOLD', 0.5); min_spend = strat.get('MIN_SPEND_FOR_JUDGE', 10.0)
        actions = []
        for c in campaigns:
            cid, aid, name = c['id'], c.get('adset_id'), c['name']
            if not aid or c['effective_status'] != 'ACTIVE': continue
            ins = insights.get(cid, {}); spend, cpi, roi, h_data = ins.get('spend', 0), ins.get('cpi', 0), ins.get('roi', 0), history.get(cid, [])
            if cpi > threshold and spend > 50: actions.append({'type': 'PAUSE', 'cid': cid, 'name': name, 'reason': f"CPI (${cpi:.2f}) > 阈值且花费 > $50", 'high_risk': spend > 200})
            elif cpi > (threshold * 0.8) and spend > 30:
                new_b = c['budget'] * 0.5
                actions.append({'type': 'BUDGET', 'cid': cid, 'aid': aid, 'name': name, 'value': new_b, 'reason': f"CPI (${cpi:.2f}) 偏高，降低预算至 ${new_b:.2f}", 'high_risk': abs(new_b - c['budget']) > 100})
            elif cpi < (threshold * 0.6) and roi > (roi_target * 1.2) and spend > min_spend:
                new_b = c['budget'] * 1.3
                actions.append({'type': 'BUDGET', 'cid': cid, 'aid': aid, 'name': name, 'value': new_b, 'reason': f"表现优异 (CPI:${cpi:.2f}, ROI:{roi:.2f})，提升预算至 ${new_b:.2f}", 'high_risk': abs(new_b - c['budget']) > 100})
            if len(h_data) >= 3 and all(d['cpi'] > threshold for d in h_data[-3:]):
                curr_bid = c['bid'] if c['bid'] > 0 else (threshold * 0.8); new_bid = curr_bid * 0.9; actions.append({'type': 'BID', 'cid': cid, 'aid': aid, 'name': name, 'value': new_bid, 'reason': "CPI 连续 3 天高于阈值，调低出价 10%"})
            if len(h_data) >= 2:
                yest_imps, before_imps = h_data[-1]['imps'], h_data[-2]['imps']
                if before_imps > 0 and (before_imps - yest_imps) / before_imps > 0.3:
                    curr_bid = c['bid'] if c['bid'] > 0 else (threshold * 0.8); new_bid = curr_bid * 1.1; actions.append({'type': 'BID', 'cid': cid, 'aid': aid, 'name': name, 'value': new_bid, 'reason': "展示量下降 > 30%，调高出价 10%"})
        return actions

    def execute_action(self, action):
        try:
            token = self.access_token
            if action['type'] == 'PAUSE': return requests.post(f"{self.base_url}/{action['cid']}", data={'status': 'PAUSED', 'access_token': token}).json().get('success', False)
            elif action['type'] == 'BUDGET': return requests.post(f"{self.base_url}/{action['aid']}", data={'daily_budget': int(action['value'] * 100), 'access_token': token}).json().get('success', False)
            elif action['type'] == 'BID': return requests.post(f"{self.base_url}/{action['aid']}", data={'bid_amount': int(action['value'] * 100), 'access_token': token}).json().get('success', False)
        except: return False
