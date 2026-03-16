import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

class Copywriter:
    """二级优化加固版：专家级文案决策引擎 (v2.11.10)"""
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    def generate_batch_copy(self, drama_name, target_language="英语", count=5):
        """[核心修复] 彻底杜绝中文干扰，强制输出目标语种"""
        
        # 语言映射处理
        lang_directive = target_language
        if target_language == "英语":
            lang_directive = "Native American English (for US Market)"

        prompt = f"""
        # Role
        You are a top-tier Meta Performance Marketing Expert specializing in short drama (ReelShort/AltaTV).
        
        # Task
        Create {count} highly engaging ad copies for the drama "{drama_name}".
        
        # CRITICAL RULE
        - OUTPUT LANGUAGE: MUST be 100% written in 【{lang_directive}】. 
        - DO NOT USE CHINESE in headline or primary_text.
        
        # Strategy (5 Different Hooks)
        1. Suspense: Open with a cliffhanger.
        2. Emotion: Focus on love, betrayal, or revenge.
        3. Power: Highlight the 'Alpha/Boss' tropes.
        4. FOMO: 'Everyone is watching' vibe.
        5. Action: Fast-paced plot description with strong CTA.
        
        # Format
        - Headline: Max 25 chars.
        - Primary Text: Max 125 chars. Mention 'AltaTV'.
        
        # Output JSON Format (Strict)
        {{
            "versions": [
                {{"headline": "Catchy headline in {target_language}", "primary_text": "High conversion text in {target_language}"}},
                ...
            ]
        }}
        """
        
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are a multi-lingual ad expert. You strictly follow the target language requirement. No Chinese allowed in output values."},
                {"role": "user", "content": prompt}
            ],
            "response_format": { "type": "json_object" }
        }
        try:
            resp = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=30).json()
            result = json.loads(resp["choices"][0]["message"]["content"])
            # 二次核查：防止模型调皮
            return result
        except Exception as e:
            print(f"❌ 文案生成失败: {e}")
            return {"versions": [{"headline": f"Watch {drama_name}", "primary_text": f"The hottest drama {drama_name} is on AltaTV now!"}] * count}

    def generate_copy(self, drama_name):
        return self.generate_batch_copy(drama_name, count=1)

    def match_drama(self, user_prompt, drama_list):
        if not self.api_key: return {"match_type": "none"}
        prompt = f"Match drama: {user_prompt}. List: {json.dumps(drama_list)}. JSON: {{'match_type': 'single/multiple/none', 'selection': '...', 'candidates': []}}"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": "gpt-4o", "messages": [{"role": "user", "content": prompt}], "response_format": { "type": "json_object" }}
        try:
            res = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload).json()
            return json.loads(res['choices'][0]['message']['content'])
        except: return {"match_type": "none"}
