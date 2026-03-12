import sys
import os
import random
import re
import json
import requests
import streamlit as st
from datetime import datetime, timedelta
from skills.xmp_downloader import XMPDownloader
from skills.copywriter import Copywriter

# 设置 UTF-8 编码
os.environ['PYTHONIOENCODING'] = 'utf-8'

class AutoMetaADS:
    """二级优化稳健版：选择锁定 + 全透明探测 (v2.11.1)"""
    def __init__(self):
        self.xmp = XMPDownloader()
        self.writer = Copywriter()

    def _ai_select_folder(self, folders, target_language):
        if not folders: return None
        folder_names = [{"name": f['name'], "id": f['id']} for f in folders]
        prompt = f"目标语言：{target_language}。从列表中选出最匹配的文件夹 ID。列表：{json.dumps(folder_names, ensure_ascii=False)}。格式：{{'selected_id': 123, 'reason': '...'}}"
        try:
            headers = {"Authorization": f"Bearer {self.writer.api_key}", "Content-Type": "application/json"}
            payload = {"model": "gpt-4o", "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}}
            res = requests.post(f"{self.writer.base_url}/chat/completions", headers=headers, json=payload, timeout=20).json()
            return json.loads(res['choices'][0]['message']['content'])
        except: return {"selected_id": folders[0]['id'], "reason": "AI 响应超时，选择首位"}

    def process_request(self, prompt, enable_campaign=False):
        """[核心重构] 增加精确名称识别，防止多选一循环 (v2.11.1)"""
        root_folders = self.xmp.get_all_root_dramas()
        drama_names = [f['name'] for f in root_folders]

        # 1. 🚀 [TASK] 优先尝试精确名称匹配 (如果用户已经选过了，这里会命中)
        target_drama = next((f for f in root_folders if f['name'] == prompt), None)
        target_lang = "英语" # 默认值

        if target_drama:
            target_name = target_drama['name']
            st.write(f"✅ **精确匹配成功**: 锁定剧集 `{target_name}`")
        else:
            # 2. 如果不是精确名称，走 AI 意图解析
            intent_prompt = f"从指令 '{prompt}' 中提取剧名和目标语言。没提则默认英语。输出 JSON: {{'drama': 'xxx', 'lang': 'xxx'}}"
            try:
                headers = {"Authorization": f"Bearer {self.writer.api_key}", "Content-Type": "application/json"}
                payload = {"model": "gpt-4o", "messages": [{"role": "user", "content": intent_prompt}], "response_format": {"type": "json_object"}}
                res = requests.post(f"{self.writer.base_url}/chat/completions", headers=headers, json=payload).json()
                intent = json.loads(res['choices'][0]['message']['content'])
                target_lang = intent['lang']
                st.write(f"🎯 **意图识别**: 剧名 = `{intent['drama']}`, 目标语言 = `{target_lang}`")
                
                # 再次尝试语义匹配
                match_result = self.writer.match_drama(intent['drama'], drama_names)
                if match_result['match_type'] == 'none': return False, f"未找到剧集 '{intent['drama']}'"
                if match_result['match_type'] == 'multiple':
                    candidates = [f for f in root_folders if f['name'] in match_result['candidates']]
                    return False, {'error_type': 'multiple_dramas', 'message': f"找到多部剧集，请选择：", 'candidates': candidates}
                
                target_name = match_result['selection']
                target_drama = next((f for f in root_folders if f['name'] == target_name), None)
            except: return False, "AI 解析异常"

        if not target_drama: return False, "无法锁定目标剧集"

        # 3. 级联 AI 探测 (保持原有透明逻辑)
        current_id = target_drama['id']
        current_name = target_name
        final_materials = []
        
        for depth in range(4):
            sub_folders, materials = self.xmp.get_contents_of_folder(current_id)
            videos = [m for m in materials if m.get('material_type') == 'video']
            if videos:
                st.write(f"🎬 **探测成功**: 在 `{current_name}` 下找到 {len(videos)} 个视频")
                final_materials = videos
                break
            if sub_folders:
                st.write(f"🔍 **AI 决策**: 寻找匹配 `{target_lang}` 的子路径...")
                decision = self._ai_select_folder(sub_folders, target_lang)
                selected_folder = next((f for f in sub_folders if f['id'] == decision['selected_id']), sub_folders[0])
                current_id, current_name = selected_folder['id'], selected_folder['name']
                st.write(f"➡️ **进入**: `{current_name}` ({decision.get('reason','')})")
            else: break

        if not final_materials: return False, f"未找到有效视频素材。"

        # 4. 1-1-5 赛马采样
        sample_size = min(5, len(final_materials))
        selected_mats = random.sample(final_materials, sample_size)
        
        result_mats = []
        for m in selected_mats:
            result_mats.append({'name': m.get('material_name', '未命名'), 'video_url': m.get('file_url'), 'cover_url': m.get('cover_url') or m.get('thumb_url')})

        return True, {'drama': target_name, 'count': sample_size, 'materials': result_mats}
