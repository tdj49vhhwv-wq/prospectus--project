# Week 6 — data/ 目录

## 数据清单

### PDF 源文件
- 存放位置: `week1/data/week1PDF/` (8家公司招股书 PDF)
- 存放位置: `week1/data/week2PDF/` (19家科创板 PDF)

### Markdown 解析文本
- 存放位置: `week1/review/` (MinerU 解析的 Markdown 文件)

### 数据清单文件

| 文件 | 路径 |
|------|------|
| PDF 清单 | `week1/data/pdf_manifest.csv` |
| Week 2 公司列表 | `week2/week2_public_8.csv` |

## 可复跑输入

统一运行入口: `pipeline/run.py`

```bash
# 安装依赖
pip install -r requirements.txt

# 运行全部8家公司
python pipeline/run.py

# 或单家公司
python pipeline/run.py --code 920100
```
