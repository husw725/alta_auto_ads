import os
import requests
import json
import traceback
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def log_debug(step, request_data, response_data):
    """记录详细的 API 交互日志到文件"""
    with open('debug_meta.log', 'a', encoding='utf-8') as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"--- {timestamp} [{step}] ---\n")
        f.write(f"REQ: {json.dumps(request_data, ensure_ascii=False)}\n")
        f.write(f"RES: {json.dumps(response_data, ensure_ascii=False)}\n\n")

class CampaignManager:
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

    def create_campaign(self, drama_name, video_url):
        """创建 Campaign (具备全栈调试能力的加固版)"""
        try:
            if not video_url: return {'status': 'error', 'error': 'Missing Video URL'}
            
            cfg = self._load_config().get('default', {})
            country = cfg.get('country', 'US')
            budget = cfg.get('daily_budget', 50)
            goal = cfg.get('optimization_goal', 'MOBILE_APP_INSTALLS')
            token = self.access_token
            name_base = f"{drama_name}-{country}-{datetime.now().strftime('%m%d%H%M')}"

            # --- STEP 1: VIDEO ---
            v_data = {'file_url': video_url, 'access_token': token}
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data=v_data).json()
            log_debug("Step 1: Video", v_data, v_resp)
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Video Upload Failed: {v_resp}"}

            # --- STEP 2: CAMPAIGN ---
            c_data = {'name': name_base, 'objective': 'OUTCOME_SALES', 'status': 'PAUSED', 'access_token': token}
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data=c_data).json()
            log_debug("Step 2: Campaign", c_data, c_resp)
            c_id = c_resp.get('id')
            if not c_id: return {'status': 'error', 'error': f"Campaign Create Failed: {c_resp}"}

            # --- STEP 3: ADSET ---
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
            log_debug("Step 3: AdSet", as_payload, as_resp)
            as_id = as_resp.get('id')
            if not as_id: return {'status': 'error', 'error': f"AdSet Create Failed: {as_resp}"}

            # --- STEP 4: CREATIVE ---
            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy_res = writer.generate_copy(drama_name)
            copy = copy_res.get('versions', [{}])[0] if isinstance(copy_res, dict) and 'versions' in copy_res else {}
            
            story_spec = {'page_id': self.page_id, 'video_data': {'video_id': v_id, 'message': copy.get('primary_text', 'Watch now!')}}
            cr_data = {'name': f"{name_base}-Cr", 'object_story_spec': json.dumps(story_spec), 'access_token': token}
            cr_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data=cr_data).json()
            log_debug("Step 4: Creative", cr_data, cr_resp)
            cr_id = cr_resp.get('id')
            if not cr_id: return {'status': 'error', 'error': f"Creative Create Failed: {cr_resp}"}

            # --- STEP 5: AD ---
            ad_data = {'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token}
            ad_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data=ad_data).json()
            log_debug("Step 5: Ad", ad_data, ad_resp)
            ad_id = ad_resp.get('id')
            if not ad_id: return {'status': 'error', 'error': f"Ad Create Failed: {ad_resp}"}

            return {'status': 'success', 'campaign_id': c_id}

        except Exception as e:
            full_error = traceback.format_exc()
            log_debug("Critical Exception", {"msg": str(e)}, {"traceback": full_error})
            return {'status': 'error', 'error': f"Traceback Error: {str(e)}\n{full_error}"}

    def get_all_campaigns(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/adsets"
            params = {'fields': 'id,campaign_id,daily_budget,lifetime_budget,status', 'access_token': self.access_token, 'limit': 100}
            resp = requests.get(url, params=params).json()
            adsets_map = {}
            if 'data' in resp:
                for item in resp['data']:
                    cid = item.get('campaign_id')
                    if cid: adsets_map[cid] = {'budget': float(item.get('daily_budget', item.get('lifetime_budget', 0)))/100}
            
            url = f"{self.base_url}/{self.ad_account_id}/campaigns"
            params = {'fields': 'id,name,status,effective_status,start_time', 'access_token': self.access_token, 'limit': 100}
            c_resp = requests.get(url, params=params).json()
            final_list = []
            if 'data' in c_resp:
                for c in c_resp['data']:
                    cid = c.get('id')
                    if cid:
                        c.update(adsets_map.get(cid, {'budget': 0}))
                        final_list.append(c)
            return sorted(final_list, key=lambda x: x.get('start_time', '0'), reverse=True)
        except: return []

    def update_campaign_status(self, cid, status):
        try: return requests.post(f"{self.base_url}/{cid}", data={'status': status, 'access_token': self.access_token}).json().get('success', False)
        except: return False

    def get_yesterday_insights(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {'level': 'campaign', 'date_preset': 'yesterday', 'fields': 'campaign_id,spend,actions,purchase_roas', 'access_token': self.access_token}
            resp = requests.get(url, params=params).json()
            res = {}
            if 'data' in resp:
                for item in resp['data']:
                    installs = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                    roi = float(item['purchase_roas'][0]['value']) if item.get('purchase_roas') else 0
                    res[item['campaign_id']] = {'spend': float(item.get('spend', 0)), 'installs': installs, 'roi': roi}
            return res
        except: return {}

    def get_historical_insights(self, days=7):
        return {} # 简化版暂不处理历史趋势

    def evaluate_optimization_rules(self, camps, ins, hist):
        return []
