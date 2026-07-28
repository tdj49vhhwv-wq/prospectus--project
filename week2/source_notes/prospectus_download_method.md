# 招股说明书下载方法

## 方法一：手动下载（推荐用于少量文件）

### 巨潮资讯网
1. 访问 https://www.cninfo.com.cn
2. 在搜索框输入公司全称或股票代码
3. 点击"公告"标签
4. 筛选分类：选择"招股说明书"
5. 找到目标文件，点击PDF图标下载
6. 命名规则：`{公司简称}_招股书_{版本}_{日期}.pdf`

### 北京证券交易所
1. 访问 https://www.bse.cn
2. 进入"信息披露"栏目
3. 搜索公司名称
4. 下载招股说明书PDF

## 方法二：程序化下载（推荐用于批量）

### 使用项目脚本
```bash
cd /Users/zhaobingqing/Documents/GitHub/prospectus-pevc-project
python3 code/03_download_pdfs/downloader.py
```

### 下载逻辑
1. 从 `company_lists/week1_public_samples.csv` 读取 `prospectus_url` 字段
2. 使用 Python `urllib` 下载，设置 User-Agent 模拟浏览器
3. 验证 PDF 文件头 `%PDF`
4. 计算 MD5 校验，跳过已存在的文件
5. 下载记录写入 `logs/download_log.csv`

### 注意事项
- 添加 1-3 秒延迟，避免请求频率过高被封
- 部分网站可能需要处理 SSL 证书问题
- PDF 文件通常 5-30MB
- 下载后检查文件完整性（能否正常打开）

## 方法三：从金融终端导出

- 东方财富 Choice 终端 → IPO 中心 → 导出招股书链接
- 同花顺 iFinD → 新股发行 → 批量下载
- Wind 终端 → IPO 专题 → 招股说明书

## 版本选择规则

| 版本 | 说明 | 优先级 |
|------|------|:--:|
| 申报稿 | 首次提交的完整招股书，融资历史信息最完整 | ⭐⭐⭐ |
| 上会稿 | 经过反馈修改后的版本 | ⭐⭐ |
| 注册稿 | 证监会注册后的最终版本，部分历史信息可能简化 | ⭐ |
| 正式稿 | 发行前最终版本 | ⭐ |
