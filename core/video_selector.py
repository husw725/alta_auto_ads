import sys
import os
import random
import re
import json
import requests
from datetime import datetime, timedelta
from skills.xmp_downloader import XMPDownloader
from skills.copywriter import Copywriter

# 设置 UTF-8 编码
os.environ['PYTHONIOENCODING'] = 'utf-8'

class AutoMetaADS:
    """二级优化稳健版：精准语言过滤 + 1-1-5 赛马 (v2.10.6)"""
    def __init__(self):
        self.xmp = XMPDownloader()
        self.writer = Copywriter()

    def process_request(self, prompt, enable_campaign=False):
        """[核心重构]：增强型路径匹配，带语言黑名单过滤"""
        # 1. 获取所有剧名
        root_folders = self.xmp.get_all_root_dramas()
        drama_names = [f['name'] for f in root_folders]
        
        # 2. 🚀 使用 GPT-4o 进行语义匹配
        match_result = self.writer.match_drama(prompt, drama_names)
        
        if match_result['match_type'] == 'none':
            return False, f"未找到与 '{prompt}' 相关的剧集。"
        
        if match_result['match_type'] == 'multiple':
            candidates = [f for f in root_folders if f['name'] in match_result['candidates']]
            return False, {'error_type': 'multiple_dramas', 'message': f"找到多部匹配的剧集，请选择：", 'candidates': candidates}

        target_name = match_result['selection']
        target_drama = next((f for f in root_folders if f['name'] == target_name), None)
        if not target_drama: return False, "系统匹配出错，请重试。"

        # 3. 🚀 [增强] 递归向下探测素材 (带语言隔离)
        def find_materials_recursively(folder_id, depth=0):
            if depth > 4: return None # 深度加深到 4 层
            
            sub_folders, materials = self.xmp.get_contents_of_folder(folder_id)
            videos = [m for m in materials if m.get('material_type') == 'video']
            
            # 如果当前层就有视频，且不是明显的非英语目录，直接返回
            if videos: return videos
            
            # --- 语言分类 ---
            lang_keywords = ['english', 'en', '英语', 'us', 'uk', 'global']
            blacklist = ['法语', '西语', '德语', '印尼语', '日语', '韩语', 'french', 'spanish', 'german', 'indonesian', 'japanese', 'korean']
            
            # A. 优先寻找命中关键词的文件夹
            for sf in sub_folders:
                f_name_lower = sf['name'].lower()
                if any(kw in f_name_lower for kw in lang_keywords):
                    res = find_materials_recursively(sf['id'], depth + 1)
                    if res: return res
            
            # B. 如果没有显式命中，进通用文件夹，但必须避开黑名单
            for sf in sub_folders:
                f_name_lower = sf['name'].lower()
                # 排除黑名单中的语言
                if any(bk in f_name_lower for bk in blacklist):
                    continue
                # 排除可能是其他非英语标识的文件夹 (可选，目前先放行 generic)
                res = find_materials_recursively(sf['id'], depth + 1)
                if res: return res
            
            return None

        # 开始探测
        final_videos = find_materials_recursively(target_drama['id'])
        
        if not final_videos:
            return False, f"在剧集 '{target_name}' 下未探测到有效的英语视频素材。"

        # 4. 🚀 1-1-5 赛马采样
        sample_size = min(5, len(final_videos))
        selected_mats = random.sample(final_videos, sample_size)
        
        result_materials = []
        for m in selected_mats:
            result_materials.append({
                'name': m.get('material_name', '未命名素材'),
                'video_url': m.get('file_url'),
                'cover_url': m.get('cover_url') or m.get('thumb_url')
            })

        return True, {
            'drama': target_drama['name'],
            'count': sample_size,
            'materials': result_materials
        }
