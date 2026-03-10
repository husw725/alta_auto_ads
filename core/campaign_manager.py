import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """管理 Meta ADS Campaign 的创建、监控、修改与深度效果分析 (智能优化版)"""
    
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        self.pixel_id = os.getenv('META_PIXEL_ID')
        self.app_link = os.getenv('APP_DOWNLOAD_LINK')
        self.base_url = "https://graph.facebook.com/v21.0"
        self.media_buyer = "Auto ADS"

    def _load_config(self):
        try:
            with open('config/config.json', 'r') as f:
                return json.load(f)
        except:
            return {"default": {"country": "US", "daily_budget": 50}, "strategy": {"CPI_THRESHOLD": 2.0}}

    def get_historical_insights(self, days=7):
        """抓取过去几天的每日数据，用于趋势分析"""
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {
                'level': 'campaign',
                'time_range': json.dumps({'since': (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'), 'until': datetime.now().strftime('%Y-%m-%d')}),
                'time_increment': 1, # 按天切分
                'fields': 'campaign_id,spend,impressions,inline_link_clicks,actions,purchase_roas',
                'access_token': self.access_token,
                'limit': 500
            }
            resp = requests.get(url, params=params).json()
            history = {} # {cid: [day1_data, day2_data, ...]}
            if 'data' in resp:
                for item in resp['data']:
                    cid = item['campaign_id']
                    if cid not in history: history[cid] = []
                    
                    # 基础计算
                    spend = float(item.get('spend', 0))
                    installs = 0
                    if 'actions' in item:
                        for action in item['actions']:
                            if action['action_type'] == 'mobile_app_install': installs += int(action['value'])
                    
                    history[cid].append({
                        'date': item.get('date_start'),
                        'spend': spend,
                        'imps': int(item.get('impressions', 0)),
                        'installs': installs,
                        'cpi': spend / installs if installs > 0 else 0
                    })
            return history
        except:
            return {}

    def get_all_campaigns(self):
        """获取所有 Campaign 及其详细出价/预算信息"""
        try:
            # 加入 adsets 信息获取以拿到出价详情
            url = f"{self.base_url}/{self.ad_account_id}/adsets"
            params = {
                'fields': 'name,status,effective_status,campaign_id,daily_budget,lifetime_budget,bid_amount,billing_event,optimization_goal',
                'access_token': self.access_token,
                'limit': 100
            }
            resp = requests.get(url, params=params).json()
            adsets_map = {}
            if 'data' in resp:
                for item in resp['data']:
                    db = float(item.get('daily_budget', 0)) / 100
                    lb = float(item.get('lifetime_budget', 0)) / 100
                    adsets_map[item['campaign_id']] = {
                        'adset_id': item['id'],
                        'budget': db if db > 0 else lb,
                        'bid': float(item.get('bid_amount', 0)) / 100
                    }
            
            # 获取 Campaign 基础信息
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
        except:
            return []

    def evaluate_optimization_rules(self, campaigns, insights, history):
        """核心规则引擎：评估每一条广告是否触发优化动作"""
        cfg = self._load_config()
        strat = cfg.get('strategy', {})
        threshold = strat.get('CPI_THRESHOLD', 2.0)
        roi_target = strat.get('ROI_THRESHOLD', 0.5)
        min_spend = strat.get('MIN_SPEND_FOR_JUDGE', 10.0)
        
        actions = []
        for c in campaigns:
            cid = c['id']
            aid = c.get('adset_id')
            name = c['name']
            if not aid or c['effective_status'] != 'ACTIVE': continue
            
            ins = insights.get(cid, {})
            spend = ins.get('spend', 0)
            cpi = ins.get('cpi', 0)
            roi = ins.get('roi', 0)
            h_data = history.get(cid, [])
            
            # --- 规则 1: 暂停劣质 ---
            if cpi > threshold and spend > 50:
                actions.append({'type': 'PAUSE', 'cid': cid, 'name': name, 'reason': f"CPI (${cpi:.2f}) > 阈值且花费 > $50", 'high_risk': spend > 200})
            
            # --- 规则 2: 降低预算 (50%) ---
            elif cpi > (threshold * 0.8) and spend > 30:
                new_b = c['budget'] * 0.5
                actions.append({'type': 'BUDGET', 'cid': cid, 'aid': aid, 'name': name, 'value': new_b, 'reason': f"CPI (${cpi:.2f}) 偏高，降低预算至 ${new_b:.2f}", 'high_risk': abs(new_b - c['budget']) > 100})
            
            # --- 规则 3: 提升预算 (30%) ---
            elif cpi < (threshold * 0.6) and roi > (roi_target * 1.2) and spend > min_spend:
                new_b = c['budget'] * 1.3
                actions.append({'type': 'BUDGET', 'cid': cid, 'aid': aid, 'name': name, 'value': new_b, 'reason': f"表现优异 (CPI:${cpi:.2f}, ROI:{roi:.2f})，提升预算至 ${new_b:.2f}", 'high_risk': abs(new_b - c['budget']) > 100})

            # --- 规则 4: 调低出价 (10%) ---
            # 持续 3 天高于阈值
            if len(h_data) >= 3 and all(d['cpi'] > threshold for d in h_data[-3:]):
                curr_bid = c['bid'] if c['bid'] > 0 else (threshold * 0.8) # 兜底出价计算
                new_bid = curr_bid * 0.9
                actions.append({'type': 'BID', 'cid': cid, 'aid': aid, 'name': name, 'value': new_bid, 'reason': "CPI 连续 3 天高于阈值，调低出价 10%"})

            # --- 规则 5: 调高出价 (10%) ---
            # 展示量持续下降超过 30% (对比前天 vs 昨天)
            if len(h_data) >= 2:
                yest_imps = h_data[-1]['imps']
                before_imps = h_data[-2]['imps']
                if before_imps > 0 and (before_imps - yest_imps) / before_imps > 0.3:
                    curr_bid = c['bid'] if c['bid'] > 0 else (threshold * 0.8)
                    new_bid = curr_bid * 1.1
                    actions.append({'type': 'BID', 'cid': cid, 'aid': aid, 'name': name, 'value': new_bid, 'reason': "展示量下降 > 30%，调高出价 10%"})

        return actions

    def execute_action(self, action):
        """执行最终动作"""
        try:
            token = self.access_token
            if action['type'] == 'PAUSE':
                return requests.post(f"{self.base_url}/{action['cid']}", data={'status': 'PAUSED', 'access_token': token}).json().get('success', False)
            elif action['type'] == 'BUDGET':
                return requests.post(f"{self.base_url}/{action['aid']}", data={'daily_budget': int(action['value'] * 100), 'access_token': token}).json().get('success', False)
            elif action['type'] == 'BID':
                return requests.post(f"{self.base_url}/{action['aid']}", data={'bid_amount': int(action['value'] * 100), 'access_token': token}).json().get('success', False)
        except:
            return False

    def get_yesterday_insights(self):
        """获取昨日全维度深度数据"""
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {
                'level': 'campaign',
                'date_preset': 'yesterday',
                'fields': 'campaign_id,spend,impressions,inline_link_clicks,actions,purchase_roas,cpm',
                'access_token': self.access_token,
                'limit': 100
            }
            resp = requests.get(url, params=params).json()
            insights_map = {}
            if 'data' in resp:
                for item in resp['data']:
                    cid = item['campaign_id']
                    spend = float(item.get('spend', 0))
                    imps = int(item.get('impressions', 0))
                    clicks = int(item.get('inline_link_clicks', 0))
                    installs = 0
                    if 'actions' in item:
                        for action in item['actions']:
                            if action['action_type'] == 'mobile_app_install': installs += int(action['value'])
                    roi = 0
                    if 'purchase_roas' in item: roi = float(item['purchase_roas'][0]['value']) if item['purchase_roas'] else 0

                    insights_map[cid] = {
                        'spend': spend, 'imps': imps, 'clicks': clicks, 'installs': installs,
                        'roi': roi, 'ctr': (clicks / imps) if imps > 0 else 0,
                        'cvr': (installs / clicks) if clicks > 0 else 0,
                        'cpi': (spend / installs) if installs > 0 else 0
                    }
            return insights_map
        except:
            return {}

    def create_campaign(self, drama_name, video_url):
        """创建 Campaign (默认直接激活)"""
        try:
            cfg_full = self._load_config()
            cfg = cfg_full.get('default', {})
            country = cfg.get('country', 'US')
            budget = cfg.get('daily_budget', 50.0)
            goal = cfg.get('optimization_goal', 'MOBILE_APP_INSTALLS')
            
            today = datetime.now().strftime("%Y%m%d")
            name_base = f"{drama_name}-{country}-{today}-Auto-{self.media_buyer}"
            
            # 1. Upload Video
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': self.access_token}).json()
            if 'id' not in v_resp: return {'status': 'error', 'error': 'Video upload failed'}
            v_id = v_resp['id']
            
            # 2. Create Campaign (Set ACTIVE)
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={'name': name_base, 'objective': 'OUTCOME_SALES', 'status': 'ACTIVE', 'access_token': self.access_token}).json()
            c_id = c_resp['id']
            
            # 3. Create AdSet (Set ACTIVE)
            as_payload = {
                'name': f"{name_base}-AS",
                'campaign_id': c_id,
                'daily_budget': int(budget * 100),
                'optimization_goal': 'OFFSITE_CONVERSIONS',
                'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({'pixel_id': self.pixel_id, 'custom_event_type': 'CONTENT_VIEW' if goal == 'CONTENT_VIEW' else 'MOBILE_APP_INSTALLS'}),
                'targeting': json.dumps({'geo_locations': {'countries': [country]}, 'device_platforms': ['mobile']}),
                'status': 'ACTIVE',
                'access_token': self.access_token
            }
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data=as_payload).json()
            as_id = as_resp.get('id')
            
            # 4. Creative & Ad (Set ACTIVE)
            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy = writer.generate_copy(drama_name).get('versions', [{}])[0]
            story_spec = {'page_id': self.page_id, 'video_data': {'video_id': v_id, 'message': copy.get('primary_text', 'Watch now!')}}
            cr_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={'name': f"{name_base}-Cr", 'object_story_spec': json.dumps(story_spec), 'access_token': self.access_token}).json().get('id')
            ad_id = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'ACTIVE', 'access_token': self.access_token}).json().get('id')
            
            return {'status': 'success', 'campaign_id': c_id, 'adset_id': as_id, 'ad_id': ad_id}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
