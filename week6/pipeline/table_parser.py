"""
Markdown 表格解析器 — rowspan/colspan 展开 + 股东表识别

学习刘宇轩方法: 从MinerU markdown解析表格，处理合并单元格
对标老师要求: "真正实现表格rowspan/colspan展开"
"""
import re
from collections import defaultdict


def parse_markdown_table(md_text, start_pos=0):
    """
    从markdown文本中解析表格，处理合并单元格。

    招股书markdown中的表格合并单元格通常表现为:
      - rowspan: 连续多行某列为空（继承上一行的值）
      - colspan: 某行为空或合并符号（如"发行前"合并2列，下面分子列）

    Returns: list of dicts [{col1: val1, col2: val2, ...}, ...]
    """
    lines = md_text[start_pos:].split('\n')
    tables = []
    current_table = []
    in_table = False
    header_line = None
    sep_line = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 检测表格行（以|开头）
        if stripped.startswith('|') and '|' in stripped[1:]:
            if not in_table:
                in_table = True
                current_table = []
                header_line = stripped
                continue

            # 分隔行（|---|---|）
            if re.match(r'^\|[\s\-:|]+\|$', stripped):
                sep_line = stripped
                continue

            current_table.append(stripped)

        else:
            if in_table and current_table:
                # 表格结束，解析
                tables.append(_parse_table(header_line, sep_line, current_table))
                current_table = []
                header_line = None
                sep_line = None
                in_table = False

    # 最后一张表
    if in_table and current_table:
        tables.append(_parse_table(header_line, sep_line, current_table))

    return tables


def _parse_table(header, sep, rows):
    """解析单张表格，展开colspan/rowspan"""
    if not header or not rows:
        return []

    # 解析表头
    headers = [c.strip() for c in header.split('|')[1:-1]]
    if sep:
        # 分隔行可能包含对齐信息，忽略
        pass

    # 检测多行表头（如: 行1="发行前" 行2="股数(股) | 持股比例(%)"）
    # 合并多行表头形成一个完整的列名
    n_cols = len(headers)

    data = []
    for row in rows:
        cells = [c.strip() for c in row.split('|')[1:-1]]
        # 补齐不足的列
        while len(cells) < n_cols:
            cells.append('')
        data.append(cells[:n_cols])

    # rowspan展开: 空单元格继承上方同列的值
    for col_idx in range(n_cols):
        last_val = ''
        for row_idx in range(len(data)):
            if data[row_idx][col_idx] == '' or data[row_idx][col_idx] == '↑':
                data[row_idx][col_idx] = last_val
            else:
                last_val = data[row_idx][col_idx]

    # 构建dict结果
    result = []
    for row in data:
        row_dict = {}
        for j, h in enumerate(headers):
            if h:  # 跳过空表头
                row_dict[h] = row[j] if j < len(row) else ''
        if row_dict:
            result.append(row_dict)

    return result


def find_shareholder_tables(md_text):
    """
    在markdown中定位并解析所有股东持股表。

    识别关键字: "股东名称"、"持股数量"、"持股比例"、"股份"、"出资额"
    返回: [{page, snapshot_type, shareholders: [{name, shares, ratio, capital}]}]
    """
    all_tables = parse_markdown_table(md_text)

    shareholder_tables = []
    for table in all_tables:
        if not table:
            continue

        # 判断是否为股东持股表
        headers = list(table[0].keys()) if table else []
        header_text = ' '.join(headers)

        is_shareholder_table = any(kw in header_text for kw in [
            '股东', '持股', '出资', '股份', '比例', '姓名', '名称'
        ])

        if not is_shareholder_table:
            continue

        # 识别列名映射
        col_map = _identify_columns(headers)

        shareholders = []
        for row in table:
            name = ''
            for key in col_map['name']:
                if key in row and row[key]:
                    name = str(row[key]).strip()
                    break

            if not name or len(name) < 2:
                continue
            if re.search(r'^(合计|总计|序号|—|、|股东名称|姓\s*名)$', name):
                continue

            # 提取股数
            shares = None
            for key in col_map['shares']:
                if key in row and row[key]:
                    val = str(row[key]).replace(',', '').replace(' ', '')
                    try:
                        shares = float(val)
                        break
                    except ValueError:
                        continue

            # 提取比例
            ratio = None
            for key in col_map['ratio']:
                if key in row and row[key]:
                    m = re.search(r'([\d.]+)\s*%?', str(row[key]))
                    if m:
                        ratio = float(m.group(1))
                        break

            # 提取出资额
            capital = None
            for key in col_map['capital']:
                if key in row and row[key]:
                    val = str(row[key]).replace(',', '').replace(' ', '')
                    try:
                        capital = float(val)
                        break
                    except ValueError:
                        continue

            shareholders.append({
                'name': name[:200],
                'shares': shares,
                'ratio': ratio,
                'capital': capital,
            })

        if shareholders:
            shareholder_tables.append({
                'headers': headers,
                'shareholders': shareholders,
                'count': len(shareholders),
            })

    return shareholder_tables


def _identify_columns(headers):
    """识别表格列名→数据类型映射"""
    col_map = {
        'name': [],
        'shares': [],
        'ratio': [],
        'capital': [],
    }

    for h in headers:
        if re.search(r'(股东|姓名|名称|投资人|发起人)', h):
            col_map['name'].append(h)
        if re.search(r'(股数|持股数量|股份数量|持股.*股|股份)', h):
            col_map['shares'].append(h)
        if re.search(r'(持股比例|比例.*%|出资比例)', h):
            col_map['ratio'].append(h)
        if re.search(r'(出资额|注册资本|认缴|实缴)', h):
            col_map['capital'].append(h)

    # fallback: 第一列=名字, 最后两列=股数+比例
    if not col_map['name'] and headers:
        col_map['name'] = [headers[0]]
    if not col_map['shares'] and len(headers) >= 2:
        col_map['shares'] = [headers[1]]
    if not col_map['ratio'] and len(headers) >= 3:
        col_map['ratio'] = [headers[-1]]

    return col_map


def find_tables_near_page(md_text, page_num, page_marker='\f'):
    """在指定页码附近查找表格（MinerU markdown通常有分页标记）"""
    # 尝试多种分页标记
    markers = [
        f'第{page_num}页', f'Page {page_num}',
        f'\\- {page_num} \\-', f'({page_num})',
        f'p{page_num}', f'p{page_num}',
    ]

    start = 0
    # 找到页码标记位置
    for marker in markers:
        pos = md_text.find(marker)
        if pos >= 0:
            start = max(0, pos - 500)  # 从标记前500字符开始
            break

    if start == 0:
        return parse_markdown_table(md_text)

    # 解析标记附近的表格
    window = md_text[start:start + 5000]
    return parse_markdown_table(window)


if __name__ == '__main__':
    # 测试
    test_md = """
| 序号 | 股东名称 | 持股数量(股) | 持股比例(%) |
|------|---------|-------------|------------|
| 1 | 张三 | 10,000,000 | 62.97 |
| 2 | 李四 | 3,000,000 | 19.49 |
| 3 | 某投资有限公司 | 500,000 | 3.15 |
| | 合计 | 15,368,000 | 100.00 |
"""
    tables = parse_markdown_table(test_md)
    print(f"解析到 {len(tables)} 张表")
    for t in tables:
        print(f"  {len(t)} 行")
        for row in t:
            print(f"    {row}")
