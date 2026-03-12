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
    """二级优化决策版：AI 级联全透明探测引擎 (v2.11.0)"""
    def __init__(self):
        self.xmp = XMPDownloader()
        self.writer = Copywriter()

    def _ai_select_folder(self, folders, target_language):
        """[核心] 调用 AI 从一堆文件夹中选出最匹配语言的一个"""
        if not folders: return None
        
        folder_names = [{"name": f['name'], "id": f['id']} for f in folders]
        prompt = f"""
        你是一个素材库管理专家。当前目标语言是：{target_language}。
        请从以下文件夹列表中，选出最可能包含该语言素材的一个文件夹。
        
        列表：{json.dumps(folder_names, ensure_ascii=False)}
        
        决策规则：
        1. 优先选直接包含目标语言名称的（如 英语、EN、English）。
        2. 如果没有直接包含的，观察文件夹名是否暗示了该语言（如 US 代表英语，FR 代表法语）。
        3. 如果看起来都是设计师名字或日期（如 bsj, 0116），请选择第一个文件夹。
        4. 绝对不要选明确属于其他语言的文件夹。
        
        请只返回该文件夹的 ID。
        格式：{{"selected_id": 12345, "reason": "理由"}}
        """
        try:
            # 借用 Copywriter 的 AI 调用能力
            headers = {"Authorization": f"Bearer {self.writer.api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o", 
                "messages": [{"role": "user", "content": prompt}],
                "response_format": { "type": "json_object" }
            }
            res = requests.post(f"{self.writer.base_url}/chat/completions", headers=headers, json=payload, timeout=20).json()
            return json.loads(res['choices'][0]['message']['content'])
        except:
            return {"selected_id": folders[0]['id'], "reason": "AI 决策超时，默认选择第一个"}

    def process_request(self, prompt, enable_campaign=False):
        """[核心逻辑]：全透明 AI 探测流"""
        # 1. AI 初始意图解析
        intent_prompt = f"从指令 '{prompt}' 中提取剧名和目标语言。如果没提语言，默认为 '英语'。输出 JSON: {{'drama': 'xxx', 'lang': 'xxx'}}"
        try:
            headers = {"Authorization": f"Bearer {self.writer.api_key}", "Content-Type": "application/json"}
            payload = {"model": "gpt-4o", "messages": [{"role": "user", "content": intent_prompt}], "response_format": {"type": "json_object"}}
            intent_res = requests.post(f"{self.writer.base_url}/chat/completions", headers=headers, json=payload).json()
            intent = json.loads(intent_res['choices'][0]['message']['content'])
        except:
            intent = {"drama": prompt, "lang": "英语"}

        st.write(f"🎯 **意图识别**: 剧名 = `{intent['drama']}`, 目标语言 = `{intent['lang']}`")

        # 2. 锁定剧集
        root_folders = self.xmp.get_all_root_dramas()
        drama_names = [f['name'] for f in root_folders]
        match_result = self.writer.match_drama(intent['drama'], drama_names)
        
        if match_result['match_type'] == 'none': return False, "未找到剧集"
        if match_result['match_type'] == 'multiple':
            candidates = [f for f in root_folders if f['name'] in match_result['candidates']]
            return False, {'error_type': 'multiple_dramas', 'message': f"找到多部剧集，请选择：", 'candidates': candidates}

        target_name = match_result['selection']
        target_drama = next((f for f in root_folders if f['name'] == target_name), None)
        st.write(f"📁 **锁定根目录**: `{target_name}`")

        # 3. 🚀 级联 AI 探测
        current_id = target_drama['id']
        current_name = target_name
        final_materials = []
        
        for depth in range(4): # 最多钻 4 层
            sub_folders, materials = self.xmp.get_contents_of_folder(current_id)
            videos = [m for m in materials if m.get('material_type') == 'video']
            
            if videos:
                st.write(f"🎬 **发现素材**: 在目录 `{current_name}` 下找到 {len(videos)} 个视频")
                final_materials = videos
                break
            
            if sub_folders:
                st.write(f"🔍 **AI 决策**: 正在 `{current_name}` 中筛选匹配 **{intent['lang']}** 的路径...")
                decision = self._ai_select_folder(sub_folders, intent['lang'])
                selected_folder = next((f for f in sub_folders if f['id'] == decision['selected_id']), sub_folders[0])
                
                current_id = selected_folder['id']
                current_name = selected_folder['name']
                st.write(f"➡️ **进入**: `{current_name}` (理由: {decision.get('reason', 'AI 推荐')})")
            else:
                break

        if not final_materials:
            return False, f"在路径下未找到有效的视频素材。"

        # 4. 1-1-5 赛马采样
        sample_size = min(5, len(final_materials))
        selected_mats = random.sample(final_materials, sample_size)
        
        result_materials = []
        for m in selected_mats:
            result_materials.append({
                'name': m.get('material_name', '未命名'),
                'video_url': m.get('file_url'),
                'cover_url': m.get('cover_url') or m.get('thumb_url')
            })

        return True, {'drama': target_name, 'count': sample_size, 'materials': result_materials}
