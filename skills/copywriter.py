import os
import json
import requests
from dotenv import load_dotenv
from skills.xmp_downloader import XMPDownloader

load_dotenv()

class Copywriter:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.downloader = XMPDownloader()

    def get_all_dramas(self):
        """获取所有剧集名称列表"""
        try:
            all_dramas = self.downloader.get_all_root_dramas()
            return [drama["name"] for drama in all_dramas if drama.get("name")]
        except Exception as e:
            print(f"❌ 获取剧名列表失败：{e}")
            return []

    def match_drama(self, user_prompt, drama_list):
        """
        [SEMANTIC MATCH] 
        使用 gpt-4o 进行深度语义匹配。
        """
        if not self.api_key:
            return {"match_type": "none"}

        prompt = f"""
        你是一个专业的 Meta 投放助手。用户会给你一个投流指令，包含他想投的剧名。
        你的任务是从【可选剧名列表】中找出最匹配的那一个。
        
        【待匹配剧名列表】: {json.dumps(drama_list, ensure_ascii=False)}
        【用户原始指令】: "{user_prompt}"
        
        匹配规则：
        1. 忽略"投"、"广告"、"开始"、"现在"、"上架"、"到"、"地区"等干扰词。
        2. 识别核心词。例如"FFAS"应该匹配到"FFAS-新"。
        3. 只要"感觉上"是指这部剧，就优先选择。
        4. 如果指令非常模糊，且有多个选项（如 FFAS-新 和 FFAS-旧），请返回 multiple 模式。
        5. 重点！有些剧名包含连字符或后缀（如 -新、-A、-1），用户可能省略这些，请智能匹配。
        
        请严格按 JSON 输出:
        {{
            "match_type": "single" | "multiple" | "none",
            "selection": "选中的剧名",
            "candidates": ["候选 1", "候选 2", ...]
        }}
        """
        
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4o", 
            "messages": [{"role": "user", "content": prompt}],
            "response_format": { "type": "json_object" },
            "temperature": 0
        }
        
        try:
            response = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=20)
            json_resp = response.json()
            if 'choices' not in json_resp:
                return {"match_type": "none"}
            return json.loads(json_resp['choices'][0]['message']['content'])
        except Exception as e:
            print(f"❌ Match Error: {e}")
            return {"match_type": "none"}

    def generate_copy(self, asset_analysis, product_name="AltaTV"):
        """生成 Meta 广告文案"""
        prompt = f"针对素材分析：{asset_analysis}，为应用《{product_name}》生成 3 套 Meta 广告文案。要求包含 Headline(25 字) 和 Primary Text(125 字)。格式为 JSON。"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4o",
            "messages": [{"role": "system", "content": "你是一个只输出 JSON 的文案专家。"}, {"role": "user", "content": prompt}],
            "response_format": { "type": "json_object" }
        }
        try:
            resp = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=30).json()
            return json.loads(resp["choices"][0]["message"]["content"])
        except:
            return {"versions": [{"angle": "默认", "headline": "New Drama Alert!", "primary_text": "Watch on AltaTV.", "cta": "LEARN_MORE"}]}