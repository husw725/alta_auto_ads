import sys
import os
import random
import re
import json
import requests
from datetime import datetime, timedelta

# 设置 UTF-8 编码 (仅在非 Streamlit 环境下尝试)
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# 引用本地 skills 目录
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills'))

from skills.xmp_downloader import XMPDownloader
from skills.copywriter import Copywriter


class AutoMetaADS:
    """Meta ADS 素材自动选择器 - 精简版"""
    
    # 地区→语言映射表
    REGION_TO_LANGUAGE = {
        '美国': '英语',
        '印尼': '印尼语',
        '日本': '日语',
        '德国': '德语',
        '葡萄牙': '葡萄牙语',
        '西班牙': '西班牙语',
        '韩国': '韩语',
        '马来西亚': '马来西亚语',
        '马来西亚语': '马来西亚语',
    }
    
    # 默认语言
    DEFAULT_LANGUAGE = '英语'
    
    def __init__(self):
        self.xmp = XMPDownloader()
        self.copywriter = Copywriter()
    
    def _log(self, message):
        """打印日志"""
        print(f"📝 {message}")
    
    def parse_natural_language(self, user_input):
        """
        从自然语言中提取信息
        """
        result = {
            'drama_name': None,
            'region': None,
            'language': None,
            'designer': None,
            'date': None
        }
        
        # 1. 提取地区信息
        for region in self.REGION_TO_LANGUAGE.keys():
            if region in user_input:
                result['region'] = region
                break
        
        # 2. 如果提取到地区，转换为语言
        if result['region']:
            result['language'] = self.REGION_TO_LANGUAGE[result['region']]
        
        # 3. 提取剧名 - 智能提取
        drama_text = user_input
        
        # 去除前缀和干扰词
        stopwords = [
            '我要投', '我想投', '要投', '我想', '要', '投', '这部剧', '的这部剧', '的', '帮我投',
            '剧名是', '名字叫', '名字是', '剧名叫', '剧名', '名字', '这部叫'
        ]
        for word in stopwords:
            drama_text = drama_text.replace(word, '')
        
        # 去除地区信息（如果已提取）
        for region in self.REGION_TO_LANGUAGE.keys():
            if region + '地区' in drama_text:
                drama_text = drama_text.replace(region + '地区', '').strip()
            elif region in drama_text:
                drama_text = drama_text.replace(region, '').strip()
        
        # 去除标点和首尾空格
        drama_text = re.sub(r'^[，。,. ]+', '', drama_text)
        drama_text = re.sub(r'[，。,. ]+ 到$', '', drama_text)
        if drama_text.endswith('到'):
            drama_text = drama_text[:-1]
        
        drama_text = drama_text.strip().strip('，').strip('。').strip(',')
        
        # 提取剧名
        if drama_text:
            result['drama_name'] = drama_text
        
        # 4. 提取设计师信息
        if '设计师' in user_input:
            designer_pattern = r'设计师 ([\u4e00-\u9fa5a-zA-Z]+)'
            match = re.search(designer_pattern, user_input)
            if match:
                result['designer'] = match.group(1)
        
        # 5. 提取日期信息
        if '日期' in user_input or '今天' in user_input or '昨天' in user_input:
            result['date'] = 'recent'
        
        # 6. 如果没有指定语言，使用默认值
        if not result['language']:
            result['language'] = self.DEFAULT_LANGUAGE
        
        return result
    
    def find_drama_by_name(self, drama_name):
        """通过剧名查找剧集"""
        all_dramas = self.xmp.get_all_root_dramas()
        
        # 精确匹配
        exact_match_list = [d for d in all_dramas if d['name'] == drama_name]
        if exact_match_list:
            return exact_match_list, True
        
        # 使用语义匹配
        match_result = self.copywriter.match_drama(
            drama_name, 
            [d['name'] for d in all_dramas]
        )
        
        if match_result.get('match_type') == 'single':
            selected = match_result.get('selection')
            if selected:
                matched = [d for d in all_dramas if d['name'] == selected]
                return matched, True
        
        elif match_result.get('match_type') == 'multiple':
            candidates = match_result.get('candidates', [])
            matched = [d for d in all_dramas if d['name'] in candidates]
            return matched, False
        
        # 如果语义匹配没有结果，尝试模糊字符串匹配
        matched_dramas = [
            d for d in all_dramas 
            if drama_name.lower() in d['name'].lower() or d['name'].lower() in drama_name.lower()
        ]
        if not matched_dramas:
            return [], False
        
        return matched_dramas, False
    
    def find_folder_in_directory(self, parent_folder_id, folder_name):
        """在指定目录下查找文件夹（增加模糊匹配）"""
        sub_folders, _ = self.xmp.get_contents_of_folder(parent_folder_id)
        
        # 1. 精确匹配
        for folder in sub_folders:
            if folder['name'].lower() == folder_name.lower():
                return folder['id'], None
        
        # 2. 映射匹配 (英语 -> English/EN)
        lang_map = {
            '英语': ['english', 'en', 'us', 'gb'],
            '日语': ['japanese', 'jp'],
            '德语': ['german', 'de'],
            '印尼语': ['indonesian', 'id'],
            '葡萄牙语': ['portuguese', 'pt', 'br'],
            '西班牙语': ['spanish', 'es'],
            '韩语': ['korean', 'kr']
        }
        
        target_keywords = lang_map.get(folder_name, [folder_name.lower()])
        
        for folder in sub_folders:
            f_name_lower = folder['name'].lower()
            if any(kw in f_name_lower for kw in target_keywords):
                return folder['id'], None
        
        # 3. 实在找不到，返回第一个文件夹作为兜底（或者提示）
        available = ", ".join([f['name'] for f in sub_folders]) if sub_folders else "无"
        return None, f"未找到 '{folder_name}' 文件夹。可用文件夹：{available}"
    
    def find_nearest_date_folder(self, designer_folder_id):
        """向前查找最近有数据的日期文件夹"""
        current_date = datetime.now()
        
        # 向前查找最多 30 天
        for day_offset in range(30):
            target_date = current_date.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            target_date_str = (target_date - timedelta(days=day_offset)).strftime('%Y%m%d')
            
            sub_folders, materials = self.xmp.get_contents_of_folder(designer_folder_id)
            
            # 检查是否有这个日期文件夹或有视频素材
            found_folder = None
            for folder in sub_folders:
                if folder['name'] == target_date_str:
                    found_folder = folder
                    break
            
            if found_folder:
                date_folders, date_materials = self.xmp.get_contents_of_folder(found_folder['id'])
                if date_materials:
                    return found_folder['id'], folder['name']
            
            if materials:
                return None, target_date_str
        
        return None, None
    
    def process_request(self, user_input, enable_campaign=False):
        """
        处理用户请求
        
        Args:
            user_input: 自然语言输入
            enable_campaign: 是否启用自动创建 Campaign
        
        Returns:
            success, result
        """
        print("=" * 60)
        print("🤖 处理用户请求")
        print(f"输入：{user_input}")
        print("=" * 60)
        
        # Step 1: 解析自然语言
        print("\n📊 Step 1: 解析自然语言")
        parsed = self.parse_natural_language(user_input)
        print(f"  剧名：{parsed['drama_name']}")
        print(f"  地区：{parsed['region']}")
        print(f"  语言：{parsed['language']}")
        print(f"  设计师：{parsed['designer']}")
        print(f"  日期：{parsed['date']}")
        
        # Step 2: 查找剧集
        print("\n📁 Step 2: 查找剧集")
        matched_dramas, exact_match = self.find_drama_by_name(parsed['drama_name'])
        
        if not matched_dramas:
            return False, f"❌ 未找到剧集：{parsed['drama_name']}"
        
        if len(matched_dramas) > 1:
            drama_list = "\n".join([
                f"{i+1}. {d['name']} (ID: {d['id']})" for i, d in enumerate(matched_dramas)
            ])
            return False, {
                'error_type': 'multiple_dramas',
                'candidates': matched_dramas,
                'message': f"❓ 找到多个剧集，请回复数字编号选择：\n\n{drama_list}\n\n请问您指的是哪一个？"
            }
        
        drama = matched_dramas[0]
        print(f"  ✅ 选中剧集：{drama['name']} (ID: {drama['id']})")
        
        # Step 3: 查找语言文件夹
        print(f"\n📁 Step 3: 查找语言文件夹 '{parsed['language']}'")
        lang_folder_id, error = self.find_folder_in_directory(
            drama['id'], parsed['language']
        )
        
        if error:
            return False, f"❌ {error}"
        
        print(f"  ✅ 选中语言：{parsed['language']} (ID: {lang_folder_id})")
        
        # Step 4: 查找设计师文件夹
        print("\n📁 Step 4: 查找设计师文件夹")
        lang_folders, lang_materials = self.xmp.get_contents_of_folder(lang_folder_id)
        
        selected_video = None
        video_id = None
        video_detail = None
        designer_folder_id = None
        date_name = 'N/A'
        
        if lang_materials:
            selected_video = random.choice(lang_materials)
            video_id = selected_video['material_id']
            video_detail = selected_video
            print(f"  ✅ 在语言目录下找到视频")
        else:
            if not lang_folders:
                return False, "❌ 该语言目录下没有设计师文件夹也没有视频"
            
            designer = random.choice(lang_folders)
            print(f"  🎲 随机选择设计师：{designer['name']} (ID: {designer['id']})")
            designer_folder_id = designer['id']
            
            # Step 5: 查找最近日期
            print("\n📁 Step 5: 查找最近有数据的日期")
            date_folder_id, date_name = self.find_nearest_date_folder(designer_folder_id)
            
            if not date_name:
                return False, "❌ 没有找到任何有数据的日期文件夹"
            
            print(f"  ✅ 选中日期：{date_name}")
            
            # Step 6: 选择视频
            print("\n🎬 Step 6: 选择视频")
            date_folders, date_materials = self.xmp.get_contents_of_folder(
                date_folder_id
            ) if date_folder_id else (None, lang_materials)
            
            if not date_materials:
                return False, "❌ 该目录下没有视频"
            
            selected_video = random.choice(date_materials)
            video_id = selected_video['material_id']
            video_detail = selected_video
            
            print(f"  🎲 随机选择视频：{selected_video.get('name', '无名称')} (ID: {video_id})")
        
        # 获取真实视频链接（file_url）
        video_link = video_detail.get('file_url', '') if video_detail else ""
        
        # 准备结果
        result = {
            'drama': drama['name'],
            'language': parsed['language'],
            'designer': lang_folders[0]['name'] if lang_folders and not lang_materials else 'N/A',
            'date': date_name,
            'video': selected_video.get('material_name', '无名称') if selected_video else '无名称',
            'video_id': video_id,
            'video_link': video_link,
            'video_detail': video_detail
        }
        
        return True, result