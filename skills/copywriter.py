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
        """[核心] 以投流专家身份一次性生成多套高转化文案"""
        prompt = f"""
        # Role
        你是一位拥有10年经验的 Meta 全球性能广告专家 (Performance Marketing Expert)，专注于短剧 (ReelShort/Drama) 赛道。
        
        # Task
        请为短剧《{drama_name}》生成 {count} 套具有极高 CTR (点击率) 和 CVR (转化率) 的 Meta 广告文案。
        
        # Requirements
        1. **目标语言**：必须完全使用【{target_language}】撰写。要求用词地道，符合当地短剧受众的阅读习惯，拒绝机械翻译。
        2. **心理钩子 (Hooks)**：每套文案必须基于不同的转化逻辑：
           - 版本1 (Suspense): 悬念钩子，在文案开头抛出一个无法拒绝的问题。
           - 版本2 (Emotion): 情感共鸣，击中人性中的爱恨、背叛或反转点。
           - 版本3 (Boss/Alpha): 霸总/强者逻辑，强调身份反差和爽点。
           - 版本4 (FOMO): 迫切感，强调“全网都在看”或“今日高潮片段”。
           - 版本5 (Action-Oriented): 引导逻辑，直接描述精彩剧情并强力引导下载。
        3. **格式限制**：
           - **Headline (标题)**: 25字符以内，像新闻头条一样具有抓手力。
           - **Primary Text (正文)**: 125字符以内。前两行必须抓住眼球。必须包含对应用 'AltaTV' 的指引。
        
        # Output Format (JSON Only)
        {{
            "versions": [
                {{"headline": "冲击力标题", "primary_text": "高转化正文"}},
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
