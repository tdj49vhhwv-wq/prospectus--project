# Week 2 PDF 手动获取URL — 操作指南

## 背景
巨潮资讯的招股书PDF链接格式为:
  https://static.cninfo.com.cn/finalpage/{日期}/{随机ID}.PDF
随机ID无法推算，必须在浏览器中搜索获取。

## 操作步骤（每家公司30秒，17家共约10分钟）

### 1. 打开CSV
用Excel/Numbers打开: `company_lists/week2_2025_company_list.csv`

### 2. 逐家搜索并填写URL
在浏览器打开搜索链接 → 找到完整招股说明书 → 复制PDF链接 → 填入CSV的prospectus_url列

注意区分:
  ✅ 要: "招股说明书" / "招股意向书" (300-800页, 5-15MB)
  ❌ 不要: "提示性公告" (5页) / "摘要" / "上市公告书" / "问询回复"

### 3. 搜索链接（复制到浏览器打开）

STAR003 思看科技 (688583):
  https://www.cninfo.com.cn/new/fulltextSearch?keyWord=688583

STAR004 兴福电子 (688545):
  https://www.cninfo.com.cn/new/fulltextSearch?keyWord=688545

STAR005 海博思创 (688411):
  https://www.cninfo.com.cn/new/fulltextSearch?keyWord=688411

STAR006 胜科纳米 (688757):
  https://www.cninfo.com.cn/new/fulltextSearch?keyWord=688757

STAR007 汉邦科技 (688755):
  https://www.cninfo.com.cn/new/fulltextSearch?keyWord=688755

STAR008 屹唐股份 (688729):
  https://www.cninfo.com.cn/new/fulltextSearch?keyWord=688729

STAR009 必贝特 (688759):
  https://www.cninfo.com.cn/new/fulltextSearch?keyWord=688759

STAR010 禾元生物 (688765):
  https://www.cninfo.com.cn/new/fulltextSearch?keyWord=688765

STAR011 西安奕材 (688783):
  https://www.cninfo.com.cn/new/fulltextSearch?keyWord=688783

STAR012 恒坤新材 (688727):
  https://www.cninfo.com.cn/new/fulltextSearch?keyWord=688727

STAR013 摩尔线程 (688795):
  https://www.cninfo.com.cn/new/fulltextSearch?keyWord=688795

STAR014 百奥赛图 (688796):
  https://www.cninfo.com.cn/new/fulltextSearch?keyWord=688796

STAR015 昂瑞微 (688790):
  https://www.cninfo.com.cn/new/fulltextSearch?keyWord=688790

STAR016 沐曦股份 (688802):
  https://www.cninfo.com.cn/new/fulltextSearch?keyWord=688802

STAR017 优迅股份 (688807):
  https://www.cninfo.com.cn/new/fulltextSearch?keyWord=688807

STAR018 健信超导 (688805):
  https://www.cninfo.com.cn/new/fulltextSearch?keyWord=688805

STAR019 强一股份 (688809):
  https://www.cninfo.com.cn/new/fulltextSearch?keyWord=688809

### 4. 填写prospectus_url
在巨潮页面中:
  1. 筛选"招股说明书"分类
  2. 点击完整的招股说明书（非摘要/非提示性公告）
  3. 详情页 → 右键PDF图标 → "复制链接地址"
  4. 粘贴到CSV的 prospectus_url 列
  5. 同时填写 prospectus_version (申报稿/注册稿/正式稿) 和 prospectus_date

### 5. 一键下载
填完URL后运行:
  python3 code/03_download_pdfs/download_week2.py
