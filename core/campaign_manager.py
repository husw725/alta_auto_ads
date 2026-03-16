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
    """二级优化稳健版：素材名动态提取文案 + 赛马 (v2.11.8)"""
    
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
        except: return {"default": {"country": "US", "daily_budget": 50}, "strategy": {"CPI_THRESHOLD": 2.0, "ROI_THRESHOLD": 0.5}}

    def _extract_real_name_from_url(self, video_url):
        """[核心算法] 从视频链接中剥离出纯净剧名"""
        try:
            filename = unquote(video_url.split('/')[-1])
            # 去除非 ASCII 字符 (如中文备注)
            name = filename.encode('ascii', 'ignore').decode('ascii')
            # 替换特殊符号为空格
            name = re.sub(r'[\(\)\[\]\._\-]', ' ', name)
            # 处理驼峰命名
            name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
            # 移除后缀
            name = re.sub(r'\s(mp4|mov|mkv)$', '', name, flags=re.IGNORECASE)
            
            parts = name.split()
            blacklist = {'v1','v2','v3','eng','en','us','pt','br','es','espanol','1080p','720p','60fps','30fps','short','final','fixed','export','ios','android','ad','drama','mp4','bsj','kk','alta','kkshort'}
            
            clean_parts = []
            for p in parts:
                p_lower = p.lower()
                # 排除纯数字(日期/序号)、黑名单、单个字母
                if re.match(r'^\d{4,12}$', p) or p_lower in blacklist or (p.isdigit() and len(p) < 5) or len(p) <= 1:
                    continue
                clean_parts.append(p)
            
            result = " ".join(clean_parts).strip()
            return result if len(result) > 2 else None
        except: return None

    def create_campaign(self, drama_name, materials_list, target_language="英语"):
        """创建 Campaign (🚀 支持素材名实时动态文案)"""
        try:
            token = self.access_token
            cfg = self._load_config().get('default', {})
            country = cfg.get('country', 'US')
            budget_cents = int(cfg.get('daily_budget', 50)) * 100
            today = datetime.now().strftime('%Y%m%d')
            
            # --- 🚀 [核心改进]：从第一个视频中提取“真实的英文剧名”用于文案 ---
            real_drama_name = self._extract_real_name_from_url(materials_list[0]['video_url'])
            # 如果提取失败（比如全是中文），回退到原始剧名
            copy_seed_name = real_drama_name if real_drama_name else drama_name
            print(f"🎯 提取纯净剧名用于文案: [{copy_seed_name}]")
            
            # 基础名依然保持您的命名规范
            name_base = f"{drama_name}-{country}-{today}-w2a-Auto-龙虾ai"

            # 自动修复上限
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

            as_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data={'name': f"{name_base}-AS", 'campaign_id': c_id, 'optimization_goal': 'APP_INSTALLS', 'destination_type': 'APP', 'billing_event': 'IMPRESSIONS', 'promoted_object': json.dumps({'application_id': self.meta_app_id, 'object_store_url': self.official_store_url}), 'targeting': json.dumps({'geo_locations': {'countries': [country]}, 'device_platforms': ['mobile'], 'user_os': ['iOS']}), 'status': 'PAUSED', 'access_token': token}).json().get('id')

            # 生成批量文案 (使用提取出的纯净名)
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
                
                video_data = {'video_id': v_id, 'message': curr_copy.get('primary_text', f"Watch {copy_seed_name} now!"), 'title': curr_copy.get('headline', f"Watch {copy_seed_name}"), 'call_to_action': {'type': 'INSTALL_APP', 'value': {'link': self.official_store_url}}}
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
                spend = float(item.get('spend', 0))
                imps = int(item.get('impressions', 1))
                clicks = int(item.get('clicks', 0))
                inst = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                purch = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] in ['purchase', 'fb_pixel_purchase'])
                roi = float(item['purchase_roas'][0]['value']) if item.get('purchase_roas') else 0
                res[cid] = {'spend': spend, 'imps': imps, 'clicks': clicks, 'installs': inst, 'roi': roi, 'ctr': clicks/imps, 'cvr': inst/clicks if clicks>0 else 0, 'cpm': spend/imps*1000, 'cpc': spend/clicks if clicks>0 else 0, 'cpi': spend/inst if inst>0 else 0, 'cpp': spend/purch if purch>0 else 0}
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
            spend, cpi, ctr, imps = ins.get('spend', 0), ins.get('cpi', 0), ins.get('ctr', 0), ins.get('imps', 0)
            if cpi > CPI_T and spend > 50: actions.append({'type': 'PAUSE', 'cid': cid, 'name': camp['name'], 'reason': f"CPI (${cpi:.2f}) > {CPI_T}", 'risk': (spend > 200)})
            elif ctr < 0.02 and imps > 1000: actions.append({'type': 'PAUSE', 'cid': cid, 'name': camp['name'], 'reason': f"CTR低 ({ctr*100:.2f}%)", 'risk': False})
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
        try:
            if action['type'] == 'PAUSE': return self.update_campaign_status(action['cid'], 'PAUSED')
            if action['type'] == 'BUDGET': return requests.post(f"{self.base_url}/{action['cid']}", data={'daily_budget': int(action['value'] * 100), 'access_token': self.access_token}).json().get('success', False)
            return True
        except: return False

    def _get_video_thumbnail_hash_smart(self, vid, token):
        for i in range(3):
            try:
                time.sleep(5)
                r = requests.get(f"{self.base_url}/{vid}", params={'fields': 'thumbnails', 'access_token': token}).json()
                if 'thumbnails' in r and r['thumbnails']['data']: return r['thumbnails']['data'][0].get('hash')
            except: pass
        return None
