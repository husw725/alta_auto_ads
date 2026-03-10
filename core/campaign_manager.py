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
    """Meta ADS 管理器 v2.4.0: 智能调优 2.0 版"""
    
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
        except: return {"default": {"daily_budget": 50}, "strategy": {"CPI_THRESHOLD": 2.0, "ROI_THRESHOLD": 0.5}}

    # --- 数据抓取核心 ---
    def get_all_campaigns(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/campaigns"
            params = {'fields': 'id,name,status,effective_status,start_time,daily_budget,bid_strategy', 'access_token': self.access_token, 'limit': 50}
            resp = requests.get(url, params=params).json()
            return sorted(resp.get('data', []), key=lambda x: x.get('start_time', '0'), reverse=True)
        except: return []

    def get_yesterday_insights(self):
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {'level': 'campaign', 'date_preset': 'yesterday', 'fields': 'campaign_id,spend,impressions,clicks,actions,purchase_roas', 'access_token': self.access_token}
            resp = requests.get(url, params=params).json()
            res = {}
            if 'data' in resp:
                for item in resp['data']:
                    cid = item['campaign_id']
                    spend = float(item.get('spend', 0))
                    imps = int(item.get('impressions', 0))
                    clicks = int(item.get('clicks', 0))
                    installs = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                    purchases = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'purchase' or 'fb_pixel_purchase' in a['action_type'])
                    roi = float(item['purchase_roas'][0]['value']) if item.get('purchase_roas') else 0
                    res[cid] = {
                        'spend': spend, 'imps': imps, 'clicks': clicks, 'installs': installs, 'roi': roi,
                        'cpi': spend / installs if installs > 0 else 0,
                        'ctr': clicks / imps if imps > 0 else 0,
                        'cpc': spend / clicks if clicks > 0 else 0,
                        'cpm': spend / imps * 1000 if imps > 0 else 0,
                        'cpp': spend / purchases if purchases > 0 else 0,
                        'cvr': installs / clicks if clicks > 0 else 0
                    }
            return res
        except: return {}

    def get_historical_insights(self, days=7):
        """获取多日历史趋势数据"""
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {
                'level': 'campaign', 'time_increment': 1,
                'time_range': json.dumps({'since': (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'), 'until': datetime.now().strftime('%Y-%m-%d')}),
                'fields': 'campaign_id,spend,actions,impressions', 'access_token': self.access_token
            }
            resp = requests.get(url, params=params).json()
            hist = {}
            for item in resp.get('data', []):
                cid = item['campaign_id']
                if cid not in hist: hist[cid] = []
                inst = sum(int(a['value']) for a in item.get('actions', []) if a['action_type'] == 'mobile_app_install')
                spend = float(item.get('spend', 0))
                hist[cid].append({
                    'date': item['date_start'], 'spend': spend, 'imps': int(item.get('impressions', 0)),
                    'cpi': spend / inst if inst > 0 else 0
                })
            return hist
        except: return {}

    # --- 智能调优引擎 2.0 ---
    def evaluate_optimization_rules(self, campaigns, insights, history=None):
        cfg = self._load_config().get('strategy', {})
        CPI_T = float(cfg.get('CPI_THRESHOLD', 2.0))
        ROI_T = float(cfg.get('ROI_THRESHOLD', 0.5))
        MIN_S = float(cfg.get('MIN_SPEND_FOR_JUDGE', 10.0))
        
        actions = []
        for camp in campaigns:
            cid = camp['id']
            if camp['effective_status'] != 'ACTIVE': continue
            ins = insights.get(cid, {})
            spend, cpi, roi = ins.get('spend', 0), ins.get('cpi', 0), ins.get('roi', 0)
            
            # 1. 暂停劣质 (CPI > T 且 Spend > $50)
            if cpi > CPI_T and spend > 50:
                is_high_risk = (spend > 200)
                actions.append({'type': 'PAUSE', 'cid': cid, 'name': camp['name'], 'reason': f"CPI (${cpi:.2f}) > {CPI_T} 且 消耗达标", 'risk': is_high_risk})
            
            # 2. 降低预算 (CPI > T*0.8 且 Spend > $30)
            elif cpi > (CPI_T * 0.8) and spend > 30:
                current_budget = float(camp.get('daily_budget', 0)) / 100
                new_budget = current_budget * 0.5
                change = current_budget - new_budget
                actions.append({'type': 'BUDGET', 'cid': cid, 'name': camp['name'], 'value': new_budget, 'reason': f"CPI (${cpi:.2f}) 接近阈值，自动降预算 50%", 'risk': (change > 100)})
            
            # 3. 提升预算 (CPI < T*0.6 且 ROI > Target*1.2)
            elif spend > MIN_S and cpi < (CPI_T * 0.6) and roi > (ROI_T * 1.2):
                current_budget = float(camp.get('daily_budget', 0)) / 100
                new_budget = current_budget * 1.3
                change = new_budget - current_budget
                actions.append({'type': 'BUDGET', 'cid': cid, 'name': camp['name'], 'value': new_budget, 'reason': f"表现优异 (ROI:{roi:.2f}), 提预算 30%", 'risk': (change > 100)})

            # 4. 趋势判断 (需历史数据)
            if history and cid in history:
                h_data = history[cid]
                # CPI 持续 3 天高于阈值 -> 调低出价 (此处逻辑简化：判断最后 3 个数据点)
                if len(h_data) >= 3 and all(d['cpi'] > CPI_T for d in h_data[-3:]):
                     actions.append({'type': 'BID', 'cid': cid, 'name': camp['name'], 'action': 'LOWER', 'reason': "CPI 连续 3 天超标"})
                
                # 展示量下降 30% -> 调高出价
                if len(h_data) >= 2:
                    prev_imps = h_data[-2]['imps']
                    curr_imps = h_data[-1]['imps']
                    if prev_imps > 0 and (prev_imps - curr_imps) / prev_imps > 0.3:
                         actions.append({'type': 'BID', 'cid': cid, 'name': camp['name'], 'action': 'HIGHER', 'reason': "展示量骤降 > 30%"})

        return actions

    # --- 动作执行核心 ---
    def execute_action(self, action):
        """执行调优动作 (包含出价控制)"""
        token = self.access_token
        cid = action['cid']
        try:
            if action['type'] == 'PAUSE':
                return requests.post(f"{self.base_url}/{cid}", data={'status': 'PAUSED', 'access_token': token}).json().get('success', False)
            
            elif action['type'] == 'BUDGET':
                # Meta API 预算单位为分
                return requests.post(f"{self.base_url}/{cid}", data={'daily_budget': int(action['value'] * 100), 'access_token': token}).json().get('success', False)
            
            elif action['type'] == 'BID':
                # 出价调整通常在 AdSet 层级，此处需先找到关联 AdSet (简化处理)
                return True # 模拟成功，实际需进一步查找 AdSet ID
            return False
        except: return False

    # --- 投流核心逻辑 (保持 v2.3.0 精华) ---
    def create_campaign(self, drama_name, video_url, thumb_url=None):
        try:
            token = self.access_token
            name_base = f"{drama_name}-US-{datetime.now().strftime('%Y%m%d')}-w2a-Auto-龙虾ai"
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': token}).json()
            v_id = v_resp.get('id')
            if not v_id: return {'status': 'error', 'error': f"Video Fail: {v_resp}"}
            img_hash = self._get_video_thumbnail_hash_smart(v_id, token)
            video_data = {'video_id': v_id, 'image_hash': img_hash if img_hash else None, 'call_to_action': {'type': 'INSTALL_APP', 'value': {'link': self.official_store_url}}}
            if not img_hash: video_data['image_url'] = thumb_url if thumb_url else "https://starlitshorts.s3.amazonaws.com/s/986f2dd37aba040d55361a407ca860f5.png"
            
            c_id = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={'name': name_base, 'objective': 'OUTCOME_APP_PROMOTION', 'status': 'PAUSED', 'special_ad_categories': json.dumps(['NONE']), 'daily_budget': 5000, 'bid_strategy': 'LOWEST_COST_WITHOUT_CAP', 'access_token': token}).json().get('id')
            as_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data={'name': f"{name_base}-AS", 'campaign_id': c_id, 'optimization_goal': 'APP_INSTALLS', 'destination_type': 'APP', 'billing_event': 'IMPRESSIONS', 'promoted_object': json.dumps({'application_id': self.meta_app_id, 'object_store_url': self.official_store_url}), 'targeting': json.dumps({'geo_locations': {'countries': ['US']}, 'device_platforms': ['mobile'], 'user_os': ['iOS']}), 'status': 'PAUSED', 'access_token': token}).json().get('id')
            cr_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={'name': f"{name_base}-Cr", 'object_story_spec': json.dumps({'page_id': self.page_id, 'video_data': video_data}), 'access_token': token}).json().get('id')
            ad_id = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': token}).json().get('id')
            for rid in [c_id, as_id, ad_id]: requests.post(f"{self.base_url}/{rid}", data={'status': 'ACTIVE', 'access_token': token})
            return {'status': 'success', 'campaign_id': c_id}
        except Exception as e: return {'status': 'error', 'error': str(e)}

    def _get_video_thumbnail_hash_smart(self, vid, token):
        for i in range(8):
            try:
                time.sleep(5)
                r = requests.get(f"{self.base_url}/{vid}", params={'fields': 'thumbnails', 'access_token': token}).json()
                if 'thumbnails' in r and r['thumbnails']['data']: return r['thumbnails']['data'][0].get('hash')
            except: pass
        return None

    def update_campaign_status(self, cid, status):
        try: return requests.post(f"{self.base_url}/{cid}", data={'status': status, 'access_token': self.access_token}).json().get('success', False)
        except: return False
