import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

class Copywriter:
    """二级优化版：多语种批量文案专家 (v2.0.0)"""
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    def generate_batch_copy(self, drama_name, target_language="英语", count=5):
        """[核心] 一次性生成多套不同角度的翻译文案"""
        prompt = f"""
        你是一个全球顶级的短剧投流专家。请为短剧《{drama_name}》生成 {count} 套 Meta 广告文案。
        要求：
        1. 目标语言：必须完全使用【{target_language}】撰写。
        2. 目标应用：AltaTV (短剧 App)。
        3. 文案风格：每套文案的切入点必须不同（如：悬疑钩子、情感共鸣、霸总反转、剧情高潮、App 强推）。
        4. 格式规范：
           - Headline: 25个字符以内，极具冲击力。
           - Primary Text: 125个字符以内，引导用户下载观看。
        
        请严格按 JSON 输出，不要有任何额外说明：
        {{
            "versions": [
                {{"headline": "...", "primary_text": "..."}},
                ...
            ]
        }}
        """
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4o",
            "messages": [{"role": "system", "content": "你是一个只输出 JSON 的多语种投流文案专家。"}, {"role": "user", "content": prompt}],
            "response_format": { "type": "json_object" }
        }
        try:
            resp = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=30).json()
            return json.loads(resp["choices"][0]["message"]["content"])
        except Exception as e:
            print(f"❌ 文案生成失败: {e}")
            # 基础保底
            return {"versions": [{"headline": f"Watch {drama_name}", "primary_text": f"The hottest drama {drama_name} is on AltaTV now!"}] * count}

    # 保留旧接口兼容性
    def generate_copy(self, drama_name):
        return self.generate_batch_copy(drama_name, count=1)

    def match_drama(self, user_prompt, drama_list):
        """[SEMANTIC MATCH] 保持原有 GPT-4o 匹配逻辑"""
        if not self.api_key: return {"match_type": "none"}
        prompt = f"从列表中匹配剧名：{user_prompt}。列表：{json.dumps(drama_list, ensure_ascii=False)}。JSON 格式：{{'match_type': 'single/multiple/none', 'selection': '...', 'candidates': []}}"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": "gpt-4o", "messages": [{"role": "user", "content": prompt}], "response_format": { "type": "json_object" }}
        try:
            res = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload).json()
            return json.loads(res['choices'][0]['message']['content'])
        except: return {"match_type": "none"}
