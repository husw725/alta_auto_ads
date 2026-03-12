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
    """二级优化版：多语种文案 + 1-1-5 赛马投放引擎 (v2.11.3)"""
    
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

    def create_campaign(self, drama_name, materials_list, target_language="英语"):
        """[核心重构] 实现 1-1-5 赛马 + 批量文案对齐 (v2.11.3)"""
        try:
            token = self.access_token
            cfg = self._load_config().get('default', {})
            country = cfg.get('country', 'US')
            budget_cents = int(cfg.get('daily_budget', 50)) * 100
            today = datetime.now().strftime('%Y%m%d')
            
            name_base = f"{drama_name}-{country}-{today}-w2a-Auto-龙虾ai"
            
            # 1. 创建 Campaign
            c_id = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={'name': name_base, 'objective': 'OUTCOME_APP_PROMOTION', 'status': 'PAUSED', 'special_ad_categories': json.dumps(['NONE']), 'daily_budget': budget_cents, 'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 'access_token': token}).json().get('id')
            # 2. 创建 AdSet
            as_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data={'name': f"{name_base}-AS", 'campaign_id': c_id, 'optimization_goal': 'APP_INSTALLS', 'destination_type': 'APP', 'billing_event': 'IMPRESSIONS', 'promoted_object': json.dumps({'application_id': self.meta_app_id, 'object_store_url': self.official_store_url}), 'targeting': json.dumps({'geo_locations': {'countries': [country]}, 'device_platforms': ['mobile'], 'user_os': ['iOS']}), 'status': 'PAUSED', 'access_token': token}).json().get('id')

            # 🚀 3. 核心改进：一次性生成批量多语种文案
            from skills.copywriter import Copywriter
            writer = Copywriter()
            count = len(materials_list)
            copy_res = writer.generate_batch_copy(drama_name, target_language=target_language, count=count)
            versions = copy_res.get('versions', [])
            
            ad_ids = []
            for idx, mat in enumerate(materials_list):
                # 如果 AI 返回文案不足，循环使用第一套
                curr_copy = versions[idx] if idx < len(versions) else versions[0]
                
                v_res = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': mat['video_url'], 'access_token': token}).json()
                v_id = v_res.get('id')
                if not v_id: continue
                
                img_hash = None
                if mat['cover_url']:
                    i_res = requests.post(f"{self.base_url}/{self.ad_account_id}/adimages", data={'copy_from_url': mat['cover_url'], 'access_token': token}).json()
                    if 'images' in i_res: img_hash = i_res['images'][list(i_res['images'].keys())[0]]['hash']
                
                video_data = {
                    'video_id': v_id, 
                    'message': curr_copy.get('primary_text', 'Watch now!'), 
                    'title': curr_copy.get('headline', f"Watch {drama_name}"), 
                    'call_to_action': {'type': 'INSTALL_APP', 'value': {'link': self.official_store_url}}
                }
                if img_hash: video_data['image_hash'] = img_hash
                else: video_data['image_url'] = "https://starlitshorts.s3.amazonaws.com/s/986f2dd37aba040d55361a407ca860f5.png"

                cr_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={'name': f"{name_base}-Cr-{idx+1}", 'object_story_spec': json.dumps({'page_id': self.page_id, 'video_data': video_data}), 'access_token': token}).json().get('id')
                if cr_id:
                    ad_res = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={'name': f"{name_base}-Ad-{idx+1}", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token}).json()
                    if ad_res.get('id'): ad_ids.append(ad_res['id'])

            if ad_ids:
                for rid in [c_id, as_id] + ad_ids: requests.post(f"{self.base_url}/{rid}", data={'status': 'ACTIVE', 'access_token': token})
                return {'status': 'success', 'campaign_id': c_id, 'ads_count': len(ad_ids)}
            return {'status': 'error', 'error': "No ads created."}
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
                roi = float(item['purchase_roas'][0]['value']) if item.get('purchase_roas') else 0
                res[cid] = {'spend': float(item.get('spend', 0)), 'installs': inst, 'roi': roi, 'cpi': float(item.get('spend', 0))/inst if inst>0 else 0, 'clicks': int(item.get('clicks', 0)), 'imps': int(item.get('impressions', 0)), 'ctr': int(item.get('clicks', 0))/int(item.get('impressions', 1))}
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
                hist[cid].append({'cpi': float(item.get('spend',0))/inst if inst>0 else 0, 'imps': int(item.get('impressions', 0))})
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
            if ins.get('spend', 0) > 50 and ins.get('cpi', 0) > CPI_T:
                actions.append({'type': 'PAUSE', 'cid': cid, 'name': camp['name'], 'reason': f"CPI (${ins['cpi']:.2f}) > {CPI_T}", 'risk': (ins['spend'] > 200)})
        return actions

    def get_all_campaigns(self):
        try: return sorted(requests.get(f"{self.base_url}/{self.ad_account_id}/campaigns", params={'fields': 'id,name,status,effective_status,start_time,daily_budget', 'access_token': self.access_token, 'limit': 50}).json().get('data', []), key=lambda x: x.get('start_time', '0'), reverse=True)
        except: return []

    def get_ad_preview(self, campaign_id):
        try:
            ads_res = requests.get(f"{self.base_url}/{campaign_id}/ads", params={'fields': 'id,name', 'access_token': self.access_token}).json()
            previews = []
            for ad in ads_res.get('data', []):
                prev_res = requests.get(f"{self.base_url}/{ad['id']}/previews", params={'ad_format': 'MOBILE_FEED_STANDARD', 'access_token': self.access_token}).json()
                body = prev_res.get('data', [{}])[0].get('body')
                if body: previews.append({'name': ad['name'], 'html': body})
            return previews
        except: return []

    def update_campaign_status(self, cid, status):
        try: return requests.post(f"{self.base_url}/{cid}", data={'status': status, 'access_token': self.access_token}).json().get('success', False)
        except: return False

    def delete_campaign(self, cid):
        try: return requests.delete(f"{self.base_url}/{cid}", params={'access_token': self.access_token}).json().get('success', False)
        except: return False

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
