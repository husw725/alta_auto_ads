import os
import requests
import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """二级优化稳健版：穿透式数据引擎 + 全能策略 (v3.2.0)"""
    
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        self.meta_app_id = "1807921329643155"
        self.IOS_STORE_URL = "http://itunes.apple.com/app/id6469592412"
        self.ANDROID_STORE_URL = "https://play.google.com/store/apps/details?id=com.melotmobile.kkshort"
        self.base_url = "https://graph.facebook.com/v21.0"

    def _load_config(self):
        try:
            with open('config/config.json', 'r') as f: return json.load(f)
        except: return {"default": {"country": "US", "daily_budget": 50, "target_platform": "iOS", "promo_method": "w2a"}, "strategy": {"CPI_THRESHOLD": 2.0}}

    def _extract_real_name_from_url(self, video_url):
        try:
            filename = unquote(video_url.split('/')[-1])
            name = filename.encode('ascii', 'ignore').decode('ascii')
            name = re.sub(r'[\(\)\[\]\._\-]', ' ', name)
            name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
            name = re.sub(r'\s(mp4|mov|mkv)$', '', name, flags=re.IGNORECASE)
            parts = name.split()
            blacklist = {'v1','v2','v3','eng','en','us','pt','br','es','espanol','1080p','720p','60fps','30fps','short','final','fixed','export','ios','android','ad','drama','mp4','bsj','kk','alta','kkshort','xxy','lzp','yl','lbj'}
            protected_words = {'a', 'i'}
            clean_parts = []
            for p in parts:
                p_lower = p.lower()
                if re.match(r'^\d{4,12}$', p) or p_lower in blacklist: continue
                if len(p) <= 1 and p_lower not in protected_words: continue
                clean_parts.append(p)
            result = " ".join(clean_parts).strip()
            return result if len(result) > 2 else None
        except: return None

    def create_campaign(self, drama_name, materials_list, target_language="英语"):
        try:
            token = self.access_token
            cfg = self._load_config().get('default', {})
            country, budget_cents = cfg.get('country', 'US'), int(cfg.get('daily_budget', 50)) * 100
            platform, method = cfg.get('target_platform', 'iOS'), cfg.get('promo_method', 'w2a')
            active_store_url = self.IOS_STORE_URL if platform == "iOS" else self.ANDROID_STORE_URL
            today = datetime.now().strftime('%Y%m%d')
            name_base = f"{drama_name}-{country}-{today}-{method}-Auto-{platform}-龙虾ai"
            real_drama_name = self._extract_real_name_from_url(materials_list[0]['video_url'])
            copy_seed_name = real_drama_name if real_drama_name else drama_name

            def do_create():
                res = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={'name': name_base, 'objective': 'OUTCOME_APP_PROMOTION', 'status': 'PAUSED', 'special_ad_categories': json.dumps(['NONE']), 'daily_budget': budget_cents, 'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 'access_token': token}).json()
                if 'error' in res and ('limit' in str(res['error']).lower() or 'volume' in str(res['error']).lower()):
                    old_camps = self.get_all_campaigns()
                    paused = [c for c in old_camps if c.get('effective_status') == 'PAUSED']
                    if paused: self.delete_campaign(paused[-1]['id']); return requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={'name': name_base, 'objective': 'OUTCOME_APP_PROMOTION', 'status': 'PAUSED', 'special_ad_categories': json.dumps(['NONE']), 'daily_budget': budget_cents, 'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 'access_token': token}).json()
                return res

            c_resp = do_create()
            c_id = c_resp.get('id')
            if not c_id: return {'status': 'error', 'error': f"Campaign Fail: {c_resp}"}

            targeting = {'geo_locations': {'countries': [country]}, 'device_platforms': ['mobile']}
            if platform == "iOS": targeting['user_os'] = ['iOS']
            elif platform == "Android": targeting['user_os'] = ['Android']

            as_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data={'name': f"{name_base}-AS", 'campaign_id': c_id, 'optimization_goal': 'APP_INSTALLS', 'destination_type': 'APP', 'billing_event': 'IMPRESSIONS', 'promoted_object': json.dumps({'application_id': self.meta_app_id, 'object_store_url': active_store_url}), 'targeting': json.dumps(targeting), 'status': 'PAUSED', 'access_token': token}).json().get('id')

            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy_res = writer.generate_batch_copy(copy_seed_name, target_language=target_language, count=len(materials_list))
            versions = copy_res.get('versions', [])
            
            ad_ids = []
            for idx, mat in enumerate(materials_list):
                curr_copy = versions[idx] if idx < len(versions) else (versions[0] if versions else {})
                v_res = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': mat['video_url'], 'access_token': token}).json()
                v_id = v_res.get('id')
                if not v_id: continue
                img_hash = None
                if mat['cover_url']:
                    i_res = requests.post(f"{self.base_url}/{self.ad_account_id}/adimages", data={'copy_from_url': mat['cover_url'], 'access_token': token}).json()
                    if 'images' in i_res: img_hash = i_res['images'][list(i_res['images'].keys())[0]]['hash']
                if not img_hash: img_hash = self._get_video_thumbnail_hash_smart(v_id, token)

                video_data = {'video_id': v_id, 'message': curr_copy.get('primary_text', f"Watch {copy_seed_name} now!"), 'title': curr_copy.get('headline', f"Watch {copy_seed_name}"), 'call_to_action': {'type': 'INSTALL_APP', 'value': {'link': active_store_url}}}
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

    def get_custom_insights(self, since, until, level='campaign'):
        """抓取指标数据 (支持 campaign 或 ad 级别)"""
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {'level': level, 'time_range': json.dumps({'since': since, 'until': until}), 'fields': 'campaign_id,ad_id,ad_name,spend,impressions,clicks,actions,purchase_roas', 'access_token': self.access_token, 'limit': 1000}
            resp = requests.get(url, params=params).json()
            res = {}
            for item in resp.get('data', []):
                key = item['ad_id'] if level == 'ad' else item['campaign_id']
                spend, imps, clicks = float(item.get('spend', 0)), int(item.get('impressions', 1)), int(item.get('clicks', 0))
                inst = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                purch = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] in ['purchase', 'fb_pixel_purchase'])
                roi = float(item['purchase_roas'][0]['value']) if item.get('purchase_roas') else 0
                res[key] = {'name': item.get('ad_name'), 'spend': spend, 'imps': imps, 'clicks': clicks, 'installs': inst, 'purchases': purch, 'roi': roi, 'ctr': clicks / imps if imps > 0 else 0, 'cvr': inst / clicks if clicks > 0 else 0, 'pur_cvr': purch / clicks if clicks > 0 else 0, 'cpm': spend / imps * 1000 if imps > 0 else 0, 'cpc': spend / clicks if clicks > 0 else 0, 'cpi': spend / inst if inst > 0 else 0, 'cpp': spend / purch if purch > 0 else 0}
            return res
        except: return {}

    # 🚀 [TASK 7.1] 新增：获取系列下的所有具体广告详情
    def get_ad_level_details(self, campaign_id, since, until):
        """抓取该系列下的具体赛马素材表现"""
        try:
            # 1. 抓取该系列下的所有 Ad 基础信息
            url = f"{self.base_url}/{campaign_id}/ads"
            params = {'fields': 'id,name,status,effective_status', 'access_token': self.access_token}
            ads_base = requests.get(url, params=params).json().get('data', [])
            
            # 2. 抓取该系列下 Ad 级别的数据表现
            insights = self.get_custom_insights(since, until, level='ad')
            
            # 合并数据
            results = []
            for ad in ads_base:
                ins = insights.get(ad['id'], {})
                results.append({**ad, **ins})
            return results
        except: return []

    def get_historical_insights(self, days=7):
        try:
            user_tz = timezone(timedelta(hours=-8))
            since = (datetime.now(user_tz) - timedelta(days=days)).strftime('%Y-%m-%d')
            until = datetime.now(user_tz).strftime('%Y-%m-%d')
            resp = requests.get(f"{self.base_url}/{self.ad_account_id}/insights", params={'level': 'campaign', 'time_increment': 1, 'time_range': json.dumps({'since': since, 'until': until}), 'fields': 'campaign_id,spend,actions,impressions', 'access_token': self.access_token}).json()
            hist = {}
            for item in resp.get('data', []):
                cid = item['campaign_id']
                if cid not in hist: hist[cid] = []
                inst = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                hist[cid].append({'cpi': float(item.get('spend', 0))/inst if inst>0 else 0, 'imps': int(item.get('impressions', 0))})
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
            spend, cpi, ctr, imps = ins.get('spend', 0), ins.get('cpi', 0), ins.get('ctr', 0), ins.get('imps', 0)
            if cpi > CPI_T and spend > 50: actions.append({'type': 'PAUSE', 'cid': cid, 'name': camp['name'], 'reason': f"CPI (${cpi:.2f}) > {CPI_T}", 'risk': (spend > 200)})
            elif ctr < 0.02 and imps > 1000: actions.append({'type': 'PAUSE', 'cid': cid, 'name': camp['name'], 'reason': f"CTR低 ({ctr*100:.2f}%)", 'risk': False})
            if history and cid in history:
                h = history[cid]
                if len(h) >= 3 and all(d['cpi'] > CPI_T for d in h[-3:]): actions.append({'type': 'BID', 'cid': cid, 'name': camp['name'], 'action': 'LOWER', 'reason': "CPI 连续 3 天超标"})
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
