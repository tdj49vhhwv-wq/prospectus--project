# 网站数据采集方法

## 采集策略

### 1. 巨潮资讯网 (cninfo.com.cn) — 主要来源

**搜索方式**:
- 按公司名称搜索: `https://www.cninfo.com.cn/new/fulltextSearch?key=公司名称`
- 按股票代码搜索: `https://www.cninfo.com.cn/new/fulltextSearch?key=股票代码`

**筛选条件**:
- 公告类型: 招股说明书
- 时间范围: IPO年度前后1年
- 排序: 按日期倒序

**采集字段**:
- 公告标题
- 公告日期
- PDF下载链接 (格式: `https://static.cninfo.com.cn/finalpage/YYYY-MM-DD/xxx.PDF`)

### 2. 北京证券交易所 (bse.cn)

**搜索方式**:
- 信息披露 → 公司公告 → 输入股票代码
- 筛选"招股说明书"类别

**PDF链接格式**:
- `https://www.bse.cn/disclosure/YYYY/YYYY-MM-DD/xxx.pdf`

### 3. 上交所/深交所

**上交所科创板** (kcb.sse.com.cn):
- IPO项目 → 招股说明书

**深交所创业板** (listing.szse.cn):
- IPO信息 → 招股说明书

## 反爬措施

- 请求间隔: 3-5秒/次
- User-Agent: 模拟Chrome浏览器
- 单次批量不超过20个文件
- 失败重试: 最多3次，指数退避
