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
    """二级优化稳健版：三维语言隔离 + 1-1-5 赛马 (v2.11.2)"""
    def __init__(self):
        self.xmp = XMPDownloader()
        self.writer = Copywriter()
        # 定义语言黑名单，用于安全降级
        self.lang_blacklist = {
            "英语": ["法语", "德语", "西语", "日语", "韩语", "印尼语", "french", "german", "spanish", "japanese", "korean"],
            "法语": ["英语", "德语", "西语", "english", "german", "spanish"]
        }

    def _ai_select_folder(self, folders, target_language):
        """[核心] AI 决策文件夹进入路径"""
        if not folders: return None
        folder_names = [{"name": f['name'], "id": f['id']} for f in folders]
        prompt = f"""
        你是一个素材库管理专家。当前目标语言是：{target_language}。
        请从以下列表中选出最匹配该语言的一个文件夹 ID。
        
        列表：{json.dumps(folder_names, ensure_ascii=False)}
        
        规则：
        1. 必须匹配 {target_language}。
        2. 绝对不能选明确标有其他语言名称的文件夹。
        
        只返回 JSON: {{"selected_id": 123, "reason": "..."}}
        """
        try:
            headers = {"Authorization": f"Bearer {self.writer.api_key}", "Content-Type": "application/json"}
            payload = {"model": "gpt-4o", "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}}
            res = requests.post(f"{self.writer.base_url}/chat/completions", headers=headers, json=payload, timeout=20).json()
            return json.loads(res['choices'][0]['message']['content'])
        except: return None

    def process_request(self, prompt, enable_campaign=False):
        """[核心重构]：带三维防御的探测流 (v2.11.2)"""
        root_folders = self.xmp.get_all_root_dramas()
        
        # 1. 指令解析
        target_drama = next((f for f in root_folders if f['name'] == prompt), None)
        target_lang = "英语" # 默认

        if target_drama:
            target_name = target_drama['name']
        else:
            intent_prompt = f"从指令 '{prompt}' 中提取剧名和目标语言。没提则默认 '英语'。JSON: {{'drama': 'xxx', 'lang': 'xxx'}}"
            try:
                headers = {"Authorization": f"Bearer {self.writer.api_key}", "Content-Type": "application/json"}
                payload = {"model": "gpt-4o", "messages": [{"role": "user", "content": intent_prompt}], "response_format": {"type": "json_object"}}
                res = requests.post(f"{self.writer.base_url}/chat/completions", headers=headers, json=payload).json()
                intent = json.loads(res['choices'][0]['message']['content'])
                target_lang = intent['lang']
                st.write(f"🎯 **意图识别**: 剧名=`{intent['drama']}`, 语言=`{target_lang}`")
                
                drama_names = [f['name'] for f in root_folders]
                match_result = self.writer.match_drama(intent['drama'], drama_names)
                if match_result['match_type'] == 'none': return False, "未找到剧集"
                if match_result['match_type'] == 'multiple':
                    return False, {'error_type': 'multiple_dramas', 'message': "找到多部剧集：", 'candidates': [f for f in root_folders if f['name'] in match_result['candidates']]}
                target_name = match_result['selection']
                target_drama = next((f for f in root_folders if f['name'] == target_name), None)
            except: return False, "AI 解析异常"

        if not target_drama: return False, "无法锁定剧集"
        st.write(f"📁 **根目录**: `{target_name}`")

        # 2. 级联探测 (带安全防御)
        current_id, current_name = target_drama['id'], target_name
        final_videos = []
        
        for depth in range(4):
            sub_folders, materials = self.xmp.get_contents_of_folder(current_id)
            # 过滤出符合语言倾向的视频名 (第三层防御)
            potential_videos = [m for m in materials if m.get('material_type') == 'video']
            
            # 🚀 [防御加固]：即便是当前层发现视频，也要核对视频名字里的语言
            safe_videos = []
            exclude_langs = self.lang_blacklist.get(target_lang, [])
            for v in potential_videos:
                v_name = v.get('material_name', '').lower()
                if not any(bad_lang in v_name for bad_lang in exclude_langs):
                    safe_videos.append(v)

            if safe_videos:
                st.write(f"🎬 **探测成功**: 在 `{current_name}` 下锁定 {len(safe_videos)} 个安全视频")
                final_videos = safe_videos
                break
            
            if sub_folders:
                st.write(f"🔍 **AI 决策**: 筛选匹配 `{target_lang}` 的路径...")
                decision = self._ai_select_folder(sub_folders, target_lang)
                
                # 🚀 [防御加固]：AI 选不出时，手动排除黑名单文件夹后选首个
                selected_id = decision.get('selected_id') if decision else None
                selected_folder = next((f for f in sub_folders if f['id'] == selected_id), None)
                
                if not selected_folder:
                    st.write("⚠️ AI 决策受阻，启动手动安全过滤降级...")
                    safe_folders = [f for f in sub_folders if not any(bad in f['name'].lower() for bad in exclude_langs)]
                    selected_folder = safe_folders[0] if safe_folders else sub_folders[0]
                
                current_id, current_name = selected_folder['id'], selected_folder['name']
                st.write(f"➡️ **进入**: `{current_name}`")
            else: break

        if not final_videos: return False, f"未找到符合 {target_lang} 条件的视频。"

        # 3. 1-1-5 赛马
        sample_size = min(5, len(final_videos))
        selected_mats = random.sample(final_videos, sample_size)
        result_mats = [{'name': m['material_name'], 'video_url': m['file_url'], 'cover_url': m.get('cover_url') or m.get('thumb_url')} for m in selected_mats]

        return True, {'drama': target_name, 'count': sample_size, 'materials': result_mats}
