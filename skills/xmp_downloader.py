import os
import time
import hashlib
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

class XMPDownloader:
    def __init__(self):
        self.client_id = os.getenv("XMP_CLIENT_ID")
        self.client_secret = os.getenv("XMP_CLIENT_SECRET")
        self.base_url = "https://xmp-open.mobvista.com"
        self.folder_url = "https://xmp-open.nativex.com"

    def _generate_sign(self, timestamp):
        return hashlib.md5(f"{self.client_secret}{timestamp}".encode('utf-8')).hexdigest()

    @st.cache_data(ttl=64800)
    def fetch_folders_by_parent(_self, parent_id):
        """[OPTIMIZED] 按需获取子文件夹列表"""
        timestamp = int(time.time())
        sign = _self._generate_sign(timestamp)
        url = f"{_self.folder_url}/v1/media/folder/list"
        
        # 构建请求参数
        payload = {
            "client_id": _self.client_id, 
            "timestamp": timestamp, 
            "sign": sign, 
            "page": 1, 
            "page_size": 1000, 
            "folder_type": 2
        }
        
        # 修正：根据报错，这里必须传数组 [parent_id]
        if parent_id is not None:
            payload["parent_folder_id"] = [int(parent_id)]
            
        try:
            resp = requests.post(url, json=payload, timeout=10).json()
            if resp.get("code") == 0:
                data = resp.get("data", [])
                
                # 由于 API 在传 [0] 时可能返回全量，所以这里依然保留过滤逻辑
                if not parent_id or int(parent_id) == 0:
                    return [
                        {"name": f.get('folder_name'), "id": f.get('folder_id')} 
                        for f in data 
                        if f.get('folder_name') and str(f.get('parent_folder_id')) == "0"
                    ]
                
                return [{"name": f.get('folder_name'), "id": f.get('folder_id')} for f in data if f.get('folder_name')]
            else:
                print(f"XMP API Error: {resp.get('code')} - {resp.get('msg')}")
                return []
        except Exception as e:
            print(f"XMP Fetch Error: {e}")
            return []

    def get_all_root_dramas(self):
        """获取根目录剧集 (parent_id=0)"""
        return self.fetch_folders_by_parent(0)

    def get_contents_of_folder(self, folder_id):
        """获取指定目录下的内容 (子文件夹 + 素材)"""
        sub_folders = self.fetch_folders_by_parent(folder_id)
        materials = self._fetch_material_list_cached(folder_id)
        return sub_folders, materials

    @st.cache_data(ttl=28800)
    def _fetch_material_list_cached(_self, folder_id):
        """[FIXED] 修正 folder_id 为数组格式"""
        timestamp = int(time.time())
        sign = _self._generate_sign(timestamp)
        url = f"{_self.base_url}/v2/media/material/list"
        
        # 关键修正：将 folder_id 包装成列表 [folder_id]
        payload = {
            "client_id": _self.client_id, 
            "timestamp": timestamp, 
            "sign": sign, 
            "folder_id": [int(folder_id)], # 必须是数组 [12345]
            "page": 1, 
            "page_size": 100
        }
        
        try:
            resp = requests.post(url, json=payload, timeout=10).json()
            if resp.get("code") != 0:
                print(f"XMP API Error {resp.get('code')}: {resp.get('msg')}")
                return []
            
            data = resp.get("data")
            if isinstance(data, list): return data
            if isinstance(data, dict): return data.get("list") or []
            return []
        except Exception as e:
            print(f"Fetch Error: {e}")
            return []

    def smart_navigate(_self, prompt, target_country="US"):
        """
        智能导航到对应语言的目录
        
        Args:
            prompt: 用户提示
            target_country: 目标国家 (US/GB/BR 等)
        
        Returns:
            folder_id, folder_name
        """
        # 语言映射
        lang_keywords = {
            "english": ["en", "english", "英语", "us", "gb", "ca", "au"],
            "german": ["de", "german", "德语"],
            "portuguese": ["pt", "portuguese", "葡萄牙语", "br", "brazil"],
        }
        
        # 检测用户提示中的语言
        prompt_lower = prompt.lower() if prompt else ""
        selected_lang = "english"  # 默认英语
        
        for lang, keywords in lang_keywords.items():
            if any(kw in prompt_lower for kw in keywords):
                selected_lang = lang
                break
        
        # 获取根目录
        root_folders = self.get_all_root_dramas()
        
        # 假设第一个剧集是目标剧集
        if not root_folders:
            return None, "没有可用的剧集"
        
        root_folder = root_folders[0]
        
        # 在剧集中查找对应语言的文件夹
        sub_folders, _ = self.get_contents_of_folder(root_folder['id'])
        
        # 模糊匹配语言文件夹
        for folder in sub_folders:
            folder_name = folder['name'].lower()
            if any(kw in folder_name for kw in lang_keywords[selected_lang]):
                return folder['id'], folder['name']
        
        # 如果没有找到语言文件夹，返回剧集本身
        return root_folder['id'], root_folder['name']