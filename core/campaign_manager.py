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
    """二级优化版：1-1-5 赛马投放引擎 (v2.0.0)"""
    
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

    def create_campaign(self, drama_name, materials_list):
        """[核心重构] 实现 1-1-5 赛马模式 (Task 2.1-2.3)"""
        try:
            token = self.access_token
            cfg = self._load_config().get('default', {})
            country = cfg.get('country', 'US')
            budget_cents = int(cfg.get('daily_budget', 50)) * 100
            today = datetime.now().strftime('%Y%m%d')
            
            # 系列基础名
            name_base = f"{drama_name}-{country}-{today}-w2a-Auto-龙虾ai"
            
            # --- 1. 创建 Campaign ---
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={
                'name': name_base, 'objective': 'OUTCOME_APP_PROMOTION', 'status': 'PAUSED',
                'special_ad_categories': json.dumps(['NONE']), 'daily_budget': budget_cents,
                'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 'access_token': token
            }).json()
            c_id = c_resp.get('id')
            if not c_id: return {'status': 'error', 'error': f"Campaign Creation Fail: {c_resp}"}

            # --- 2. 创建 AdSet ---
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data={
                'name': f"{name_base}-AS", 'campaign_id': c_id, 'optimization_goal': 'APP_INSTALLS',
                'destination_type': 'APP', 'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({'application_id': self.meta_app_id, 'object_store_url': self.official_store_url}),
                'targeting': json.dumps({'geo_locations': {'countries': [country]}, 'device_platforms': ['mobile'], 'user_os': ['iOS']}),
                'status': 'PAUSED', 'access_token': token
            }).json()
            as_id = as_resp.get('id')
            if not as_id: return {'status': 'error', 'error': f"AdSet Creation Fail: {as_resp}"}

            # --- 3. 🚀 循环创建多个广告 (Task 2.2) ---
            from skills.copywriter import Copywriter
            writer = Copywriter()
            ad_ids = []

            for idx, mat in enumerate(materials_list):
                v_url = mat['video_url']
                t_url = mat['cover_url']
                ad_index = idx + 1
                
                # A. 视频上传
                v_res = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': v_url, 'access_token': token}).json()
                v_id = v_res.get('id')
                if not v_id: continue # 跳过单个失败
                
                # B. 文案生成 (每条广告取独立文案或随机一套)
                copy_res = writer.generate_copy(drama_name)
                main_copy = copy_res.get('versions', [{}])[0]
                
                # C. 封面处理
                img_hash = None
                if t_url:
                    i_res = requests.post(f"{self.base_url}/{self.ad_account_id}/adimages", data={'copy_from_url': t_url, 'access_token': token}).json()
                    if 'images' in i_res: img_hash = i_res['images'][list(i_res['images'].keys())[0]]['hash']
                if not img_hash: img_hash = self._get_video_thumbnail_hash_smart(v_id, token)

                video_data = {
                    'video_id': v_id,
                    'message': main_copy.get('primary_text', f"Enjoy {drama_name} Part {ad_index}!"),
                    'title': main_copy.get('headline', f"Watch {drama_name} V{ad_index}"),
                    'call_to_action': {'type': 'INSTALL_APP', 'value': {'link': self.official_store_url}}
                }
                if img_hash: video_data['image_hash'] = img_hash
                else: video_data['image_url'] = "https://starlitshorts.s3.amazonaws.com/s/986f2dd37aba040d55361a407ca860f5.png"

                # D. 创建 Creative
                cr_res = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={
                    'name': f"{name_base}-Cr-{ad_index}", 
                    'object_story_spec': json.dumps({'page_id': self.page_id, 'video_data': video_data}), 
                    'access_token': token
                }).json()
                cr_id = cr_res.get('id')
                
                # E. 创建 Ad (Task 2.3 命名差异化)
                if cr_id:
                    ad_res = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={
                        'name': f"{name_base}-Ad-{ad_index}", 
                        'adset_id': as_id, 
                        'creative': json.dumps({'creative_id': cr_id}), 
                        'status': 'PAUSED', 
                        'access_token': token
                    }).json()
                    if ad_res.get('id'): ad_ids.append(ad_res['id'])

            # --- 4. 批量激活 ---
            if ad_ids:
                for rid in [c_id, as_id] + ad_ids:
                    requests.post(f"{self.base_url}/{rid}", data={'status': 'ACTIVE', 'access_token': token})
                return {'status': 'success', 'campaign_id': c_id, 'ads_count': len(ad_ids)}
            
            return {'status': 'error', 'error': "No ads were successfully created."}
            
        except Exception as e: return {'status': 'error', 'error': str(e)}

    def get_ad_preview(self, campaign_id):
        """[升级] 获取该系列下所有广告的预览"""
        try:
            ads_res = requests.get(f"{self.base_url}/{campaign_id}/ads", params={'fields': 'id,name', 'access_token': self.access_token}).json()
            previews = []
            for ad in ads_res.get('data', []):
                prev_res = requests.get(f"{self.base_url}/{ad['id']}/previews", params={'ad_format': 'MOBILE_FEED_STANDARD', 'access_token': self.access_token}).json()
                body = prev_res.get('data', [{}])[0].get('body')
                if body: previews.append({'name': ad['name'], 'html': body})
            return previews
        except: return []

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
                imps = int(item.get('impressions', 1))
                clicks = int(item.get('clicks', 0))
                res[cid] = {
                    'spend': spend, 'installs': inst, 'roi': float(item['purchase_roas'][0]['value']) if item.get('purchase_roas') else 0,
                    'cpi': spend/inst if inst>0 else 0, 'imps': imps, 'clicks': clicks,
                    'ctr': clicks/imps, 'cvr': inst/clicks if clicks>0 else 0,
                    'cpm': spend/imps*1000, 'cpc': spend/clicks if clicks>0 else 0,
                    'cpp': 0 # 简化处理
                }
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
            if ins.get('spend', 0) > 50 and ins.get('cpi', 0) > CPI_T:
                actions.append({'type': 'PAUSE', 'cid': cid, 'name': camp['name'], 'reason': f"CPI (${ins['cpi']:.2f}) > {CPI_T}", 'risk': (ins['spend'] > 200)})
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

    def execute_action(self, action):
        return self.update_campaign_status(action['cid'], 'PAUSED') if action['type'] == 'PAUSE' else False

    def _get_video_thumbnail_hash_smart(self, vid, token):
        for i in range(3):
            try:
                time.sleep(5)
                r = requests.get(f"{self.base_url}/{vid}", params={'fields': 'thumbnails', 'access_token': token}).json()
                if 'thumbnails' in r and r['thumbnails']['data']: return r['thumbnails']['data'][0].get('hash')
            except: pass
        return None
