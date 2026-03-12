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
    """二级优化版：多素材赛马决策引擎 (v2.0.0)"""
    def __init__(self):
        self.xmp = XMPDownloader()
        self.writer = Copywriter()

    def parse_natural_language(self, prompt):
        """解析用户意图"""
        return {
            'drama_name': prompt.replace('投', '').replace('上架', '').strip(),
            'language': 'english',
            'country': 'US'
        }

    def find_drama_by_name(self, name):
        """深度模糊匹配剧集目录"""
        root_folders = self.xmp.get_all_root_dramas()
        matches = []
        name_clean = name.lower().replace(' ', '')
        
        for f in root_folders:
            f_name = f['name'].lower().replace(' ', '')
            if name_clean in f_name or f_name in name_clean:
                matches.append(f)
        
        # 优先级排序：完全匹配 > 包含
        matches.sort(key=lambda x: len(x['name']))
        return matches, (len(matches) == 1 and matches[0]['name'].lower() == name.lower())

    def find_folder_in_directory(self, parent_id, target_name):
        """在目录下查找匹配的语言/类型文件夹"""
        sub_folders, _ = self.xmp.get_contents_of_folder(parent_id)
        for f in sub_folders:
            if target_name.lower() in f['name'].lower():
                return f['id'], None
        return None, "未找到目标文件夹"

    def find_nearest_date_folder(self, parent_id):
        """查找最近日期命名的子文件夹 (如 0108, 1220)"""
        folders, _ = self.xmp.get_contents_of_folder(parent_id)
        date_folders = [f for f in folders if re.match(r'^\d{4}$', f['name'])]
        if date_folders:
            date_folders.sort(key=lambda x: x['name'], reverse=True)
            return date_folders[0]['id'], date_folders[0]['name']
        return None, None

    def process_request(self, prompt, enable_campaign=False):
        """[核心重构]：支持多素材提取逻辑 (Task 1.1-1.3)"""
        parsed = self.parse_natural_language(prompt)
        matched_dramas, is_exact = self.find_drama_by_name(parsed['drama_name'])

        if not matched_dramas: return False, f"未找到名为 '{parsed['drama_name']}' 的剧集"
        if len(matched_dramas) > 1 and not is_exact:
            return False, {'error_type': 'multiple_dramas', 'message': f"找到多部匹配的剧集，请选择：", 'candidates': matched_dramas}

        target_drama = matched_dramas[0]
        
        # 1. 递归向下钻取到视频素材层
        # Drama -> Lang (English) -> Designer (Optional) -> Date (Optional)
        lang_id, err = self.find_folder_in_directory(target_drama['id'], parsed['language'])
        if not lang_id: return False, err

        sub_f, materials = self.xmp.get_contents_of_folder(lang_id)
        
        # 深度探测逻辑：如果当前层没视频，进第一个子目录搜
        if not materials and sub_f:
            designer_id = sub_f[0]['id']
            date_id, _ = self.find_nearest_date_folder(designer_id)
            final_id = date_id if date_id else designer_id
            _, materials = self.xmp.get_contents_of_folder(final_id)

        # 2. 🚀 [TASK 1.1] 1-1-5 赛马采样逻辑
        video_materials = [m for m in materials if m.get('material_type') == 'video']
        if not video_materials: return False, "该目录下未找到视频素材"

        # 采样上限 5 个
        sample_size = min(5, len(video_materials))
        selected_materials = random.sample(video_materials, sample_size)
        
        # 3. [TASK 1.3] 结构化返回列表
        result_materials = []
        for m in selected_materials:
            result_materials.append({
                'name': m.get('material_name', '未命名素材'),
                'video_url': m.get('file_url'),
                'cover_url': m.get('cover_url') or m.get('thumb_url') # 兼容性取图
            })

        result = {
            'drama': target_drama['name'],
            'count': sample_size,
            'materials': result_materials
        }
        
        return True, result
