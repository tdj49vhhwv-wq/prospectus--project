"""
LLM 提取器 — DeepSeek 驱动，处理正则无法覆盖的多投资人/复合事件

用法:
  extractor = LLMExtractor()
  records = extractor.extract_subscriptions(text, company, page)
"""
import json, os, re, time
from pathlib import Path
from datetime import datetime
import requests

MODEL = "deepseek-chat"
BASE_URL = "https://api.deepseek.com"


def get_api_key() -> str:
    """Return the DeepSeek API key from the environment."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "缺少 DEEPSEEK_API_KEY。请先设置环境变量，再运行 LLM 提取。"
        )
    return api_key

SUBSCRIPTION_PROMPT = """你是招股书融资信息提取专家。从文本中提取所有增资/出资/股权转让事件。

## 输出（纯JSON数组，不要markdown包裹）
[
  {
    "subscriber_name": "投资方全称",
    "amount_subscribed": 金额数字(万元, float),
    "shares_subscribed": 股数(万股, float),
    "price_per_share": 每股价格(元, float),
    "event_context": "增资|股权转让|设立|整体变更|吸收合并",
    "evidence_text": "原文逐字摘录(不超过150字)"
  }
]

## 金额提取规则（重要！）
- "XX万元" → amount_subscribed=XX (数字，不是null)
- "注册资本XX万元" → 如果是设立事件，amount_subscribed=XX
- "转让价格XX万元" → 这是股权转让，amount_subscribed填转让金额，event_context="股权转让"
- "XX万股" → shares_subscribed=XX
- "XX元/股"或"XX元/注册资本" → price_per_share=XX
- 文中没提到的字段填null，不编造

## 事件分类规则
- 提到"设立""成立""出资设立" → event_context="设立"
- 提到"增资""认购""认缴新增" → event_context="增资"
- 提到"转让""转让予""转让给" → event_context="股权转让"
- 提到"整体变更""折股""股份公司" → event_context="整体变更"
- 提到"吸收合并" → event_context="吸收合并"

## 规则
1. 一段文本多个投资方 → 每人一条记录
2. 金额从原文提取数字，不要写null如果原文有数字
3. 不编造事件，不推测金额
4. 资本公积转增不算增资
5. 无融资事件返回 []

## 示例
输入："金浦临港基金、金浦科创基金和上海骁墨分别以7,000万元、3,000万元和1,500万元认购新增注册资本840万元、360万元和180万元。"
输出：
[{"subscriber_name":"金浦临港基金","amount_subscribed":7000,"shares_subscribed":840,"price_per_share":8.3333,"event_context":"增资","evidence_text":"金浦临港基金以7,000万元认购新增注册资本840万元"}]

输入："黄学英向复星惟盈转让37.3190万元注册资本，转让价格1,922.8571万元"
输出：
[{"subscriber_name":"复星惟盈","amount_subscribed":1922.8571,"shares_subscribed":null,"price_per_share":51.52,"event_context":"股权转让","evidence_text":"黄学英向复星惟盈转让37.3190万元注册资本，转让价格1,922.8571万元"}]

## 待提取文本
{section_text}"""


class LLMExtractor:
    def __init__(self, model=MODEL, max_retries=3, sleep_sec=1):
        self.model = model
        self.max_retries = max_retries
        self.sleep_sec = sleep_sec
        self.call_count = 0

    def _call_api(self, prompt: str) -> str:
        """调用 DeepSeek API"""
        headers = {
            "Authorization": f"Bearer {get_api_key()}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
        }

        for attempt in range(self.max_retries):
            try:
                resp = requests.post(
                    f"{BASE_URL}/v1/chat/completions",
                    headers=headers, json=payload, timeout=60
                )
                if resp.status_code == 200:
                    self.call_count += 1
                    return resp.json()["choices"][0]["message"]["content"]
                else:
                    print(f"  API错误 {resp.status_code}: {resp.text[:100]}")
                    time.sleep(self.sleep_sec * (attempt + 1))
            except Exception as e:
                print(f"  网络错误: {e}")
                time.sleep(self.sleep_sec * (attempt + 1))

        return "[]"

    def extract_subscriptions(self, text: str, company: dict) -> list[dict]:
        """
        从文本中提取订阅事件

        Returns: list of dicts，每个dict是一条subscription记录
        """
        if not text or len(text) < 20:
            return []

        prompt = SUBSCRIPTION_PROMPT.replace("{section_text}", text[:4000])

        raw = self._call_api(prompt)

        # 解析JSON（可能被markdown代码块包裹）
        json_str = raw.strip()
        # 去掉可能的markdown包裹
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]

        try:
            records = json.loads(json_str)
        except json.JSONDecodeError:
            # 尝试提取JSON数组
            m = re.search(r'\[.*\]', json_str, re.DOTALL)
            if m:
                try:
                    records = json.loads(m.group(0))
                except:
                    return []
            else:
                return []

        # 补充元数据
        for r in records:
            r["company_name"] = company.get("name", "")
            r["stock_code"] = company.get("code", "")
            r["extraction_method"] = "llm_deepseek"
            r["extracted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            r["data_source"] = "pdf_disclosed"

        return records

    def batch_extract(self, texts: list[tuple[str, dict]]) -> list[dict]:
        """批量提取"""
        all_records = []
        for text, company in texts:
            records = self.extract_subscriptions(text, company)
            all_records.extend(records)
            print(f"  {company.get('name','')[:8]}: {len(records)}条 (文本{len(text)}字)")
            time.sleep(self.sleep_sec)
        return all_records


if __name__ == "__main__":
    # 测试：用gold里一条正则无法拆分的样本
    test_text = "2020年9月，金浦临港基金、金浦科创基金和上海骁墨与本次增资前公司股东签署《投资协议》，约定金浦临港基金、金浦科创基金和上海骁墨分别以7,000万元、3,000万元和1,500万元认购发行人新增注册资本840万元、360万元和180万元。新增股份的认购价格为8.3333元/股。"

    extractor = LLMExtractor()
    records = extractor.extract_subscriptions(
        test_text,
        {"name": "友升股份", "code": "603418"}
    )

    print(f"提取到 {len(records)} 条记录:")
    for r in records:
        print(f"  {r['subscriber_name']}: {r.get('amount_subscribed')}万元, {r.get('shares_subscribed')}万股, @{r.get('price_per_share')}元/股")
    print(f"\nAPI调用次数: {extractor.call_count}")
