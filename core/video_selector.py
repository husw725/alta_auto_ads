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
    """二级优化回归版：AI 语义匹配 + 多素材赛马引擎 (v2.10.1)"""
    def __init__(self):
        self.xmp = XMPDownloader()
        self.writer = Copywriter()

    def process_request(self, prompt, enable_campaign=False):
        """[回归重构]：恢复 AI 语义匹配逻辑"""
        # 1. 获取所有剧名
        root_folders = self.xmp.get_all_root_dramas()
        drama_names = [f['name'] for f in root_folders]
        
        # 2. 🚀 使用 GPT-4o 进行语义匹配 (恢复核心能力)
        match_result = self.writer.match_drama(prompt, drama_names)
        
        if match_result['match_type'] == 'none':
            return False, f"未找到与 '{prompt}' 相关的剧集，请尝试输入更准确的剧名。"
        
        if match_result['match_type'] == 'multiple':
            # 将名称映射回原始对象
            candidates = [f for f in root_folders if f['name'] in match_result['candidates']]
            return False, {'error_type': 'multiple_dramas', 'message': f"找到多部匹配的剧集，请选择：", 'candidates': candidates}

        # 3. 锁定唯一匹配的目标剧集
        target_name = match_result['selection']
        target_drama = next((f for f in root_folders if f['name'] == target_name), None)
        if not target_drama: return False, "系统匹配出错，请刷新重试。"

        # 4. 递归向下钻取素材
        # 匹配逻辑：Drama -> Lang (English)
        lang_id = None
        sub_folders, _ = self.xmp.get_contents_of_folder(target_drama['id'])
        for f in sub_folders:
            if 'english' in f['name'].lower() or 'en' in f['name'].lower():
                lang_id = f['id']; break
        
        if not lang_id: return False, f"在该剧集下未找到英语 (English) 素材目录。"

        # 深度探测视频
        sub_f, materials = self.xmp.get_contents_of_folder(lang_id)
        if not materials and sub_f:
            # 进第一个子目录（通常是设计师目录）
            designer_id = sub_f[0]['id']
            # 查找日期文件夹
            d_folders, _ = self.xmp.fetch_folders_by_parent(designer_id)
            date_folders = [f for f in d_folders if re.match(r'^\d{4}$', f['name'])]
            if date_folders:
                date_folders.sort(key=lambda x: x['name'], reverse=True)
                final_id = date_folders[0]['id']
            else:
                final_id = designer_id
            _, materials = self.xmp.get_contents_of_folder(final_id)

        # 5. 🚀 1-1-5 赛马采样 (保留新功能)
        video_materials = [m for m in materials if m.get('material_type') == 'video']
        if not video_materials: return False, f"在目录中未找到有效的视频素材。"

        sample_size = min(5, len(video_materials))
        selected_mats = random.sample(video_materials, sample_size)
        
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
