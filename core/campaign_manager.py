import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class CampaignManager:
    """管理 Meta ADS Campaign 的创建、监控、修改与效果分析"""
    
    def __init__(self):
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')
        self.page_id = os.getenv('META_PAGE_ID')
        self.pixel_id = os.getenv('META_PIXEL_ID')
        self.app_link = os.getenv('APP_DOWNLOAD_LINK')
        self.base_url = "https://graph.facebook.com/v21.0"
        self.media_buyer = "Auto ADS"

    def _load_dynamic_config(self):
        with open('config/config.json', 'r') as f:
            return json.load(f).get('default', {})

    def get_yesterday_insights(self):
        """获取昨日消耗数据"""
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            params = {
                'level': 'campaign',
                'date_preset': 'yesterday',
                'fields': 'campaign_id,spend,impressions,inline_link_clicks,actions',
                'access_token': self.access_token,
                'limit': 100
            }
            resp = requests.get(url, params=params).json()
            insights_map = {}
            if 'data' in resp:
                for item in resp['data']:
                    conversions = 0
                    if 'actions' in item:
                        for action in item['actions']:
                            if action['action_type'] in ['mobile_app_install', 'purchase', 'offsite_conversion.fb_pixel_purchase']:
                                conversions += int(action['value'])
                    insights_map[item['campaign_id']] = {
                        'spend': float(item.get('spend', 0)),
                        'conversions': conversions,
                        'cpi': float(item.get('spend', 0)) / conversions if conversions > 0 else 0
                    }
            return insights_map
        except:
            return {}

    def get_all_campaigns(self):
        """获取所有 Campaign 列表"""
        try:
            url = f"{self.base_url}/{self.ad_account_id}/campaigns"
            params = {'fields': 'name,status,effective_status,start_time', 'access_token': self.access_token, 'limit': 50}
            resp = requests.get(url, params=params).json()
            if 'data' in resp:
                return sorted(resp['data'], key=lambda x: x.get('start_time', '0'), reverse=True)
            return []
        except:
            return []

    def update_campaign_status(self, campaign_id, status):
        """修改状态"""
        try:
            url = f"{self.base_url}/{campaign_id}"
            params = {'status': status, 'access_token': self.access_token}
            return requests.post(url, data=params).json().get('success', False)
        except:
            return False

    def create_campaign(self, drama_name, video_url):
        """创建 Campaign (使用 config.json 中的策略)"""
        try:
            # 加载实时配置
            cfg = self._load_dynamic_config()
            country = cfg.get('country', 'US')
            budget = cfg.get('daily_budget', 50.0)
            goal = cfg.get('optimization_goal', 'MOBILE_APP_INSTALLS')
            
            today = datetime.now().strftime("%Y%m%d")
            name_base = f"{drama_name}-{country}-{today}-Auto-{self.media_buyer}"
            
            # 1. Upload Video
            v_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/advideos", data={'file_url': video_url, 'access_token': self.access_token}).json()
            if 'id' not in v_resp: return {'status': 'error', 'error': 'Video upload failed'}
            v_id = v_resp['id']
            
            # 2. Create Campaign
            c_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/campaigns", data={'name': name_base, 'objective': 'OUTCOME_SALES', 'status': 'PAUSED', 'access_token': self.access_token}).json()
            c_id = c_resp['id']
            
            # 3. Create AdSet
            as_payload = {
                'name': f"{name_base}-AS",
                'campaign_id': c_id,
                'daily_budget': int(budget * 100),
                'optimization_goal': 'OFFSITE_CONVERSIONS' if goal == 'CONTENT_VIEW' else 'OFFSITE_CONVERSIONS', 
                'billing_event': 'IMPRESSIONS',
                'promoted_object': json.dumps({'pixel_id': self.pixel_id, 'custom_event_type': 'CONTENT_VIEW' if goal == 'CONTENT_VIEW' else 'MOBILE_APP_INSTALLS'}),
                'targeting': json.dumps({'geo_locations': {'countries': [country]}, 'device_platforms': ['mobile']}),
                'status': 'PAUSED',
                'access_token': self.access_token
            }
            # 强制适配 Mobile App Install 逻辑
            if goal == "MOBILE_APP_INSTALLS":
                as_payload['optimization_goal'] = "OFFSITE_CONVERSIONS" # 某些 API 版本要求通过 Pixel 事件优化安装
                # 如果是纯应用安装 Objective，某些 API 要求用 APP_INSTALLS 优化
            
            as_resp = requests.post(f"{self.base_url}/{self.ad_account_id}/adsets", data=as_payload).json()
            as_id = as_resp.get('id')
            
            # 4. Creative & Ad
            from skills.copywriter import Copywriter
            writer = Copywriter()
            copy = writer.generate_copy(drama_name).get('versions', [{}])[0]
            story_spec = {'page_id': self.page_id, 'video_data': {'video_id': v_id, 'message': copy.get('primary_text', 'Watch now!')}}
            cr_id = requests.post(f"{self.base_url}/{self.ad_account_id}/adcreatives", data={'name': f"{name_base}-Cr", 'object_story_spec': json.dumps(story_spec), 'access_token': self.access_token}).json().get('id')
            ad_id = requests.post(f"{self.base_url}/{self.ad_account_id}/ads", data={'name': f"{name_base}-Ad", 'adset_id': as_id, 'creative': json.dumps({'creative_id': cr_id}), 'status': 'PAUSED', 'access_token': self.access_token}).json().get('id')
            
            return {'status': 'success', 'campaign_id': c_id, 'adset_id': as_id, 'ad_id': ad_id}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
