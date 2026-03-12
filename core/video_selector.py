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
    """二级优化稳健版：全语种适配 + 1-1-5 赛马 (v2.10.4)"""
    def __init__(self):
        self.xmp = XMPDownloader()
        self.writer = Copywriter()

    def process_request(self, prompt, enable_campaign=False):
        """[核心重构]：增强型路径匹配，支持全语种关键词"""
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

        # 3. 锁定剧集
        target_name = match_result['selection']
        target_drama = next((f for f in root_folders if f['name'] == target_name), None)
        if not target_drama: return False, "系统匹配出错，请重试。"

        # 4. 🚀 [增强] 递归向下探测素材
        def find_materials_recursively(folder_id, depth=0):
            if depth > 3: return None
            
            sub_folders, materials = self.xmp.get_contents_of_folder(folder_id)
            videos = [m for m in materials if m.get('material_type') == 'video']
            
            # 如果当前层就有视频，直接返回
            if videos: return videos
            
            # 搜索子目录：优先寻找“语言”目录
            lang_keywords = ['english', 'en', '英语', 'us', 'uk', 'global']
            for sf in sub_folders:
                if any(kw in sf['name'].lower() for kw in lang_keywords):
                    # 进语言目录深挖
                    res = find_materials_recursively(sf['id'], depth + 1)
                    if res: return res
            
            # 如果没找到显式语言目录，进第一个子目录试试 (兜底逻辑)
            if sub_folders:
                return find_materials_recursively(sub_folders[0]['id'], depth + 1)
            
            return None

        # 开始探测
        final_videos = find_materials_recursively(target_drama['id'])
        
        if not final_videos:
            return False, f"在剧集 '{target_name}' 下未探测到任何视频素材，请检查 XMP 目录结构。"

        # 5. 🚀 1-1-5 赛马采样
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
