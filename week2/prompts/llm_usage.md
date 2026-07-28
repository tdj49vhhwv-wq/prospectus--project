# LLM 使用说明

## 当前使用策略: 规则为主 + LLM为辅

LLM目前尚未接入自动流程（规则提取已覆盖80%事件类型），以下为LLM接入方案。

## LLM负责的场景

| 场景 | 规则盲区 | LLM方案 | 预期提升 |
|------|:--:|------|:--:|
| event_type="其他"分类 | 0% (36条) | Few-shot prompt + EventContext枚举 | 0→80% |
| 英文投资人名提取 | 0% (28条) | Named Entity Recognition | 0→75% |
| 金额/数量消歧 | 35%缺失 | CoT prompt + 单位关键词 | 35→85% |
| VIE事件拆分 | 0% (4条) | CoT prompt + 逐轮提取 | 0→60% |
| Auto ES噪声过滤 | 406条噪声 | LLM分类器过滤 | 噪声↓80% |

## 接入方式

```python
# pipeline/extract_with_llm.py
import anthropic  # 或 openai

def llm_extract(text_chunk, prompt_template):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt_template.format(text=text_chunk)}]
    )
    return json.loads(response.content[0].text)
```

## 成本估算 (8家公司, ~40MB文本, ~120K tokens)

| Variant | 每家公司token | 8家公司总token | 预估成本(Claude Sonnet) |
|------|:--:|:--:|:--:|
| A (零样本) | ~15K | ~120K | ~$0.36 |
| B (Few-shot) | ~25K | ~200K | ~$0.60 |
| C (CoT) | ~50K | ~400K | ~$1.20 |

## 安全性

- LLM输出必须经Pydantic校验后才可接受
- 温度=0时仍可能产生幻觉,不能信任裸JSON
- cross-check发现的待复核项优先人工验证,LLM建议仅作参考

## 替代方案 (当前使用)

如果LLM不可用,使用规则提取 + Pydantic守卫 + 人工复核:

```bash
# 纯规则流程 (无需API key)
bash pipeline/run.sh
```
