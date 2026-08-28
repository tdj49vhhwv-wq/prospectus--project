#!/usr/bin/env python3
"""Week 10 Stage 5D — cross-board (Main/ChiNext/BSE) PE/VC extractor.

Self-contained extractor for canonical MinerU markdown of the DEV/VAL/BLIND
cross-board issuers.  The frozen Stage 7.2 parser under-fires on Main/ChiNext/BSE
disclosures that route PE/VC entry through 股权转让 tables (受让方 column),
设立/整体变更 发起人 tables, and 增资 prose ("由 X、Y 分别以货币认缴 A 万元").
"""
import re, json, html, sys, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'week9' / 'stage72_postblind'))
sys.path.insert(0, str(ROOT / 'week9' / 'stage72_postblind' / 'runtime'))
from markdown_source import MD_FILES, get_md_dir
from event_local_pevc import alias_map, normspace


# --------------------------------------------------------------------------- #
# MinerU OCR correction — rare-character misrecognition, inconsistent *within*
# the same document (both the correct and the misread form appear).  We normalize
# to the correct form before extraction so alias resolution + name matching agree.
# --------------------------------------------------------------------------- #
OCR_CORRECTIONS = {
    '尚顾祺能': '尚颀祺能',
    '捷泉元禾璞华': '疌泉元禾璞华',
    '走泉元禾璞华': '疌泉元禾璞华',
    '高领锡恒': '高瓴锡恒',  # 高瓴(Hillhouse)被 MinerU 错成"高领"
}


def _correct_ocr(text):
    for bad, good in OCR_CORRECTIONS.items():
        text = text.replace(bad, good)
    return text


# --------------------------------------------------------------------------- #
# text helpers
# --------------------------------------------------------------------------- #
def clean(s):
    s = html.unescape(re.sub(r'<[^>]+>', ' ', str(s or '')))
    s = re.sub(r'\s+', ' ', s).strip(' ，。；、:：|')
    return s


_LEAD = r'(?:万元|新增的注册资本|新增注册资本|新增股东|新股东|发行人与|根据发行人与|公司向|已收到|全部|其中|以及|由|向|共同|分别|股东|投资人|认购人|受让方|出资人|公司股东|同意|引进|吸收|原股东|各股东|除)'


def clean_name(n):
    n = clean(n)
    n = n.strip('（()）')
    n = n.lstrip('-—–·')
    while True:
        m = re.match(r'^' + _LEAD, n)
        if not m:
            break
        n = n[m.end():]
    return n.strip(' ，。；、:：()（）')


# --------------------------------------------------------------------------- #
# institutional classifier (alias-resolved)
# --------------------------------------------------------------------------- #
def is_institution(name, aliases):
    n = clean_name(name)
    if not n or len(n) < 2:
        return False
    # pure-ASCII (foreign) entity — digits allowed (e.g. "AAMS-1")
    if re.fullmatch(r'[A-Za-z0-9&\s.\-()（）]+', n) and re.search(r'[A-Za-z]{2}', n):
        return True
    # fund/batch number suffix (e.g. 麦岛6号, 疌泉元禾璞华一期) — institution despite digits
    if re.search(r'(一期|二期|三期|四期|五期|六期|七期|八期|一号|二号|三号|四号|五号|六号|壹号|贰号|叁号|肆号|伍号|\d+号|\d+期)', n):
        return True
    # Chinese/other names must not contain digits
    if re.search(r'\d', n):
        return False
    full = aliases.get(normspace(n), '')
    u = (n + ' ' + full).upper()
    if re.search(r'(FUND|LLC|LIMITED|CAPITAL|VENTURE|INVEST|CO\.|CORP|INC\b|LTD)', u):
        return True
    if any(k in u for k in ('公司', '基金', '合伙', '投资', '资本', '创投', '创业',
                            '中心', '集团', '实业', '产业', '控股', '证券', '银行',
                            '保险', '信托', '有限', '产投', '汇金', '股权')):
        return True
    return False


def is_employee_platform(name, aliases):
    """员工持股平台/计划 — alias (glossary) definition is the reliable signal."""
    n = normspace(clean_name(name))
    if not n:
        return False
    full = aliases.get(n, '')
    if re.search(r'员工(?:跟投)?(?:持股)?(?:平台|计划)', full):
        return True
    return False


# 散文句子被当成「名称」的动词标记（如「由华秦投资享有…履行国有出资人职责」被
# `由…出资` 正则误抽为「华秦投资享有」/「省人民政府授权…」）。合法股东名不含这些词。
_NAME_FRAGMENT_MARKERS = (
    '享有', '授权', '履行', '职责', '代为', '缴纳', '出资人', '复函', '批复',
    '确认', '出具', '说明', '收到', '支付', '验资',
)


def is_name_fragment(name):
    """散文句子碎片（非名称）——含动词/公文标记."""
    return any(mk in name for mk in _NAME_FRAGMENT_MARKERS)


# --------------------------------------------------------------------------- #
# exclusion sets (employee platforms / tech founders)
# --------------------------------------------------------------------------- #
def _split_names(s):
    s = clean(s)
    s = re.sub(r'(?:系|为|是)(?:发行人|公司)?(?:的)?', '', s)
    out = []
    for p in re.split(r'[、，,、]|(?:及|和|与)(?=[一-鿿A-Za-z])', s):
        p = clean_name(p)
        if 2 <= len(p) <= 40 and not re.search(r'\d', p):
            out.append(p)
    return out


def employee_platforms(text):
    """员工持股平台/计划 names — from 股东性质 tables + prose lists."""
    plain = clean(text)
    out = set()
    # table: shareholder-name rows flagged 员工(跟投)(持股)(平台/计划)
    # 用表头定位「名称」列，避免只回看固定 2 格导致名称列较远时漏取
    for table in re.findall(r'<table.*?</table>', text, re.S | re.I):
        rows = parse_table(table)
        if len(rows) < 2:
            continue
        name_idx = _header_index(rows[0], ('股东名称', '股东姓名', '名称', '姓名', '股东'))
        for r in rows[1:]:
            if not r:
                continue
            if not any(re.search(r'员工(?:跟投)?(?:持股)?(?:平台|计划)', c) for c in r):
                continue
            cands = [r[name_idx]] if name_idx is not None and name_idx < len(r) else r
            for c in cands:
                n = clean_name(c)
                if n and 2 <= len(n) <= 20 and not re.search(r'\d', n):
                    out.add(normspace(n))
    # prose: "X(、Y) 均/系/为/是 (发行人/公司)(的) 员工(跟投)(持股)(平台/计划)"
    for mm in re.finditer(r'([^。；；]{2,200}?)(?:均)?(?:系|为|是)(?:发行人|公司)?(?:的)?员工(?:跟投)?(?:持股)?(?:平台|计划)', plain):
        for n in _split_names(mm.group(1)):
            out.add(normspace(n))
    # prose: "员工(跟投)(持股)平台/计划 X"
    for mm in re.finditer(r'员工(?:跟投)?(?:持股)?(?:平台|计划)\s*([一-鿿A-Za-z0-9&（）()·]{2,15})\s*(?:通过|以|向|系|为|经|持有|在)', plain):
        out.add(normspace(clean_name(mm.group(1))))
    return out


def tech_founders(text):
    plain = clean(text)
    out = set()
    for mm in re.finditer(r'(?:^|[。；：、，,\s])([一-鿿A-Za-z（）()]{2,40}?)\s*以(?:非货币财产|无形资产|专有生产技术|技术成果|专利|技术)[^。；]{0,40}?(?:出资|认缴)', plain):
        out.add(normspace(clean_name(mm.group(1))))
    return out


def _glossary_rows(text):
    """Yield (normed-alias, full) for every glossary row (alias | 指 | full)."""
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', text, re.S | re.I):
        cells = [clean(x) for x in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', tr, re.S | re.I)]
        if len(cells) >= 3 and cells[1] == '指':
            full = cells[2]
            for a in re.split(r'[、,/，]', cells[0]):
                a = clean(a)
                if a:
                    yield normspace(a), full


def _full2alias(text):
    """反向别名表：全称/曾用名/名称片段 -> {简称}."""
    rev = {}
    for a, full in _glossary_rows(text):
        a = normspace(a)
        rev.setdefault(normspace(full), set()).add(a)
        for seg in re.split(r'[，,、；“”"\'\s（）()]+', full):
            seg = seg.strip('“”"\'')
            if 2 <= len(seg) <= 60 and re.search(r'(公司|集团|有限|合伙|企业|中心|研究院)', seg):
                rev.setdefault(normspace(seg), set()).add(a)
    return rev


def _is_truncated(nn):
    """全称含未闭合括号 —— MinerU 截断产物（如「…合伙企业(有限合伙」缺右括号）。"""
    return nn.count('(') != nn.count(')') or nn.count('（') != nn.count('）')


def _canonical_short(nn, full2alias):
    """全称/片段 -> 最短简称（gold 用简称对齐）。含截断括号容错。

    例: 陕西原上智谷股权投资合伙企业(有限合伙 -> 原上智谷
    """
    for key in (nn, nn.rstrip('（）()')):
        aliases = full2alias.get(key)
        if aliases:
            return min(aliases, key=len)
    # 截断的尾缀「（有限合伙」/「(有限合伙」剥离后重试
    base = re.sub(r'[（(]有限合伙[）)]?$', '', nn)
    if base != nn and base in full2alias:
        return min(full2alias[base], key=len)
    return None


def controllers(text):
    """控股股东/实际控制人 + 其控制的企业 + 发行人自身子公司/分公司 + 同受控制的关联方.

    这些是发行人的控制体系内实体（含国有控股股东内部重组方），而非 PE/VC。
    """
    out = set()
    full2alias = _full2alias(text)
    for a, full in _glossary_rows(text):
        if re.search(r'(控股股东|实际控制人|控制的其他企业|原控股股东|吸收合并|第一大股东)', full):
            out.add(a)

    # 关系表：按表头定位「名称」列与「关系/类型」列，关系命中关键词 → 名称入集
    sub_pat = re.compile(r'^(?:全资|控股|参股)?子公司$|^分公司$')          # 子公司表（短标签）
    rel_pat = re.compile(r'(?:控股股东|实际控制人).{0,10}控制的企业|控制的其他企业'
                         r'|同受.{0,14}控制')                            # 关联方表（短句）
    for table in re.findall(r'<table.*?</table>', text, re.S | re.I):
        rows = parse_table(table)
        if len(rows) < 2:
            continue
        hdr = rows[0]
        name_idx = _header_index(hdr, ('名称', '姓名', '企业', '公司', '股东'))
        rel_idx = _header_index(hdr, ('关联关系', '与发行人关系', '与公司关系', '关系', '子公司类型', '企业类型', '类型'))
        if rel_idx is None or name_idx is None:
            continue
        for r in rows[1:]:
            if rel_idx >= len(r):
                continue
            rel = r[rel_idx].strip()
            if not rel:
                continue
            if not (sub_pat.fullmatch(rel) or (len(rel) <= 24 and rel_pat.search(rel))):
                continue
            n = clean_name(r[name_idx])
            if not n or not (2 <= len(n) <= 60) or _is_num(n) or re.search(r'^(序号|合计|注|发行|是否)', n):
                continue
            fn = normspace(n)
            out.add(fn)
            out.update(full2alias.get(fn, ()))

    # 散文（收紧）：控股股东/实际控制人/第一大股东 的身份
    plain = clean(text)
    for mm in re.finditer(r'(?:控股股东|实际控制人|第一大股东)(?:系|为|是)?([一-鿿A-Za-z（）()]{2,16})', plain):
        n = clean_name(mm.group(1))
        if n and not re.search(r'^(及|和|与|其|的|所|之|为|系|是|承诺|已|将|就|对|向|出|履|持|直|控|变|未|不|均|作|声|情|根|凭|即|公|前|分|第|截|据|符|认|结|发|报|期|内|外|上|下|相|主|并)', n):
            out.add(normspace(n))
    for mm in re.finditer(r'([一-鿿A-Za-z（）()]{2,16})(?:系|为|是)(?:发行人|公司)?(?:的)?(?:控股股东|实际控制人|第一大股东)', plain):
        n = clean_name(mm.group(1))
        if n:
            out.add(normspace(n))
    return out


def issuer_names(text):
    """发行人自身及其惯用简称/别称 + 前身（避免把发行人自己当成受让方/认购方 PE/VC）。"""
    issuer_full = None
    for a, full in _glossary_rows(text):
        if '发行人' in a or a in ('发行人', '公司', '本公司', '股份公司'):
            issuer_full = normspace(full)
            break
    out = set()
    if issuer_full:
        out.add(issuer_full)
        for a, full in _glossary_rows(text):
            if normspace(full) == issuer_full:
                out.add(a)
    # 前身实体（"系发行人/XX 前身"）—— 也是发行人自身，非 PE/VC
    for a, full in _glossary_rows(text):
        if '前身' in full and ('发行人' in full or '公司' in full or '股份' in full):
            out.add(a)
    return out


def holding_spvs(text):
    """非基金型财务投资主体 —— 持股 SPV（员工平台/自然人合投），非 PE/VC 基金.

    ① 企业管理/管理咨询型合伙企业（原规则，无守卫）。
    ② 「服务/咨询」型合伙或中心，且全称不含 PE/VC 特征词（基金/股权/投资/创业/
       创投/私募/资本/产投）—— 例：上海骁墨(信息技术服务中心)、财智创享(咨询服务合伙)。
       PE/VC 基金与投资机构全称必含特征词，故守卫可安全区分二者。
    """
    out = set()
    for a, full in _glossary_rows(text):
        # ① 企业管理/管理咨询型合伙企业 —— 原规则
        if re.search(r'(企业管理|管理咨询).{0,6}合伙', full):
            out.add(a)
            continue
        # ② 服务/咨询型合伙或中心 —— 有守卫，避免误杀含「股权投资」等的基金
        if re.search(r'(基金|私募|股权|投资|创业|创投|资本|产投)', full):
            continue
        if re.search(r'(服务|咨询).{0,10}(?:合伙|中心|企业)', full):
            out.add(a)
    return out


# --------------------------------------------------------------------------- #
# section splitting + heading detection
# --------------------------------------------------------------------------- #
def split_sections(text):
    lines = text.splitlines(True)
    sections = []
    cur_head = None
    cur_body = []
    for line in lines:
        m = re.match(r'^(#{1,4})\s+(.*?)\s*$', line)
        if m and '-->' not in line:
            if cur_head is not None:
                sections.append((cur_head, ''.join(cur_body)))
            cur_head = m.group(2).strip()
            cur_body = []
        else:
            cur_body.append(line)
    if cur_head is not None:
        sections.append((cur_head, ''.join(cur_body)))
    return sections


def heading_date_ym(heading):
    m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月', heading)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    return None


def heading_event(heading):
    h = heading
    # affiliate/related-party disposal disclosures (关联方置出) — not issuer history
    if '股权转让情况' in h and '发行人' not in h:
        return None
    if '关联方' in h or '置出' in h:
        return None
    # 协议条款/特殊约定讨论（非历史事件，如「…股权转让协议特殊条款…」）
    if '特殊条款' in h:
        return None
    if '特殊投资约定' in h or '投资约定' in h or '投资协议' in h:
        return '增资'
    if '设立后的' in h or '股本变化情况' in h or '股权变化情况' in h:
        return '增资'
    if ('股权转让' in h or '股份转让' in h) and '增资' in h:
        return '增资及股权转让'
    if '股权转让' in h or '股份转让' in h:
        return '股权转让'
    # 「X 受让…股份」= 股权转让（排除「受让方」名词性标题，如「受让方…外汇登记手续」）
    if '受让' in h and '受让方' not in h and '股份' in h:
        return '股权转让'
    if '整体变更' in h or re.search(r'股份(?:有限)?公司设立', h) or ('股份有限公司' in h and '设立' in h):
        return '整体变更'
    if ('有限公司' in h and '设立' in h) or '首期出资' in h or '设立及' in h:
        return '设立'
    if ('增资' in h or '增加注册资本' in h or '定向发行' in h or '发行股票' in h
            or '股票发行' in h or '发行新股' in h or '现金增资' in h or '发行融资' in h):
        return '增资'
    return None


def prose_date_ym(body):
    plain = clean(body)

    def ym(m):
        return f"{m.group(1)}-{int(m.group(2)):02d}"

    # 完成日优先：验资「截至 X 年 X 月 …（已）收到」的实缴到账月（gold 口径）
    #   注意取「截至…收到」的到账月，而非《验资报告》出具日（常晚 1-3 个月）。
    for m in re.finditer(r'截至\s*(\d{4})\s*年\s*(\d{1,2})\s*月[^。；]{0,20}?(?:收到|已收到)', plain):
        return ym(m)
    # 次选：变更登记 / 工商登记（无验资实缴段落时，取登记完成月）
    for m in re.finditer(r'(\d{4})\s*年\s*(\d{1,2})\s*月[^。；]{0,40}?(?:变更登记|工商登记)', plain):
        return ym(m)
    # 再次：无异议函（北交所定向发行核准月；窗口放宽，函名较长时仍可命中）
    for m in re.finditer(r'(\d{4})\s*年\s*(\d{1,2})\s*月[^。；]{0,60}?(?:无异议)', plain):
        return ym(m)
    # 再次：发行/增资（排除「签署…协议」预备动作 + 「挂牌…公告」上市后公告，其月≠完成月）
    for m in re.finditer(r'(\d{4})\s*年\s*(\d{1,2})\s*月[^。；]{0,30}?(?:发行股份|发行股票|定向发行|增资)', plain):
        if re.search(r'(协议|签署|挂牌|公告|公开转让)', m.group(0)):
            continue
        return ym(m)
    # 末选：股东大会（程序性决议月）
    for m in re.finditer(r'(\d{4})\s*年\s*(\d{1,2})\s*月[^。；]{0,30}?(?:股东大会)', plain):
        return ym(m)
    m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月', plain)
    if m:
        return ym(m)
    return None


def overall_change_date_ym(body):
    """整体变更 completion date (工商登记/换发/创立大会), NOT the 审计基准日.

    股改基准日（"以 X 日为基准日...整体变更"）是审计基准，并非改制完成日。
    完成日应是换发营业执照 / 工商变更登记 / 创立大会的日期。
    """
    plain = clean(body)

    def ym(m):
        return f"{m.group(1)}-{int(m.group(2)):02d}"

    # Priority 1: 工商登记/换发/核发/领取营业执照 —— 完成日
    for m in re.finditer(
        r'(\d{4})\s*年\s*(\d{1,2})\s*月[^。；]{0,40}?(?:换发|核发|领取|完成.*?登记|工商登记|变更登记)',
        plain,
    ):
        if '基准日' not in m.group(0):
            return ym(m)
    # Priority 2: 创立大会 / 发起设立 —— 股份公司设立日
    for m in re.finditer(
        r'(\d{4})\s*年\s*(\d{1,2})\s*月[^。；]{0,40}?(?:创立大会|发起设立)',
        plain,
    ):
        if '基准日' not in m.group(0):
            return ym(m)
    # Priority 3: 整体变更 / 变更为股份有限公司 —— 排除基准日描述
    for m in re.finditer(
        r'(\d{4})\s*年\s*(\d{1,2})\s*月[^。；]{0,30}?(?:整体变更|变更为股份有限公司)',
        plain,
    ):
        if '基准日' not in m.group(0):
            return ym(m)
    return None


# --------------------------------------------------------------------------- #
# HTML table helpers
# --------------------------------------------------------------------------- #
def parse_table(html_table):
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html_table, re.S | re.I)
    out = []
    for tr in rows:
        cells = [clean(x) for x in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', tr, re.S | re.I)]
        if cells:
            out.append(cells)
    return out


def _header_index(cells, keywords):
    for i, c in enumerate(cells):
        if any(k in c for k in keywords):
            return i
    return None


def _is_num(s):
    return re.fullmatch(r'[\d.,%\s]+', s) is not None


def extract_transfer_names(body):
    """受让方 column of a 转让方/受让方 table (rowspan-safe)."""
    names = []
    for table in re.findall(r'<table.*?</table>', body, re.S | re.I):
        rows = parse_table(table)
        if not rows:
            continue
        tj = _header_index(rows[0], ('受让方',))
        if tj is None:
            continue
        for r in rows[1:]:
            # use the explicit 受让方 column when it holds a name
            if tj < len(r) and r[tj] and not _is_num(r[tj]) and '合计' not in r[tj]:
                names.append(clean_name(r[tj]))
                continue
            # rowspan merges the 转让方 cell away → first non-numeric non-transferor cell
            for c in r:
                c2 = clean_name(c)
                if not c2 or '合计' in c2 or '转让方' in c2 or '开曼' in c2:
                    continue
                if _is_num(c2):
                    continue
                names.append(c2)
                break
    return names


def extract_shareholder_names(body):
    names = []
    for table in re.findall(r'<table.*?</table>', body, re.S | re.I):
        rows = parse_table(table)
        if not rows:
            continue
        nj = _header_index(rows[0], ('股东姓名', '股东名称', '股东姓名或名称', '发起人'))
        if nj is None:
            continue
        for r in rows[1:]:
            if nj >= len(r):
                continue
            n = clean_name(r[nj])
            if n and '合计' not in n and not _is_num(n):
                names.append(n)
    return names


def extract_summary_change_rows(body):
    rows = []
    for table in re.findall(r'<table.*?</table>', body, re.S | re.I):
        trs = parse_table(table)
        if not trs:
            continue
        ti = _header_index(trs[0], ('时间', '变动类型'))
        ci = _header_index(trs[0], ('具体变化情况', '变化情况', '具体情况'))
        if ti is None or ci is None:
            continue
        for r in trs[1:]:
            if ti >= len(r) or ci >= len(r):
                continue
            m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月', r[ti])
            if not m:
                continue
            date_ym = f"{m.group(1)}-{int(m.group(2)):02d}"
            if '股权转让' in r[ti] and '增资' not in r[ti]:
                etype = '股权转让'
            elif '整体变更' in r[ti]:
                etype = '整体变更'
            elif '设立' in r[ti]:
                etype = '设立'
            else:
                etype = '增资'
            rows.append((date_ym, etype, r[ci]))
    return rows


# --------------------------------------------------------------------------- #
# prose investor extraction (operates on whitespace-stripped text)
# --------------------------------------------------------------------------- #
def _split_prose_names(chunk):
    s = clean(chunk)
    s = re.sub(r'(?:新股东|新增股东|由|其中|以及)', '', s)
    out = []
    for p in re.split(r'[、，,、]|(?:及|和|与)(?=[一-鿿A-Za-z])', s):
        p = clean_name(p)
        if 2 <= len(p) <= 40 and not re.search(r'\d', p):
            out.append(p)
    return out


def extract_prose_investors(body, event_type):
    ns = normspace(body)  # strip ALL whitespace (MinerU inserts intra-char spaces)
    names = []

    if event_type == '股权转让':
        for mm in re.finditer(r'(?:转让给|转让予|转让至|转让与)([一-鿿A-Za-z（）()]{2,40}?)(?=[、。；，,]|用于|$)', ns):
            names.append(clean_name(mm.group(1)))
        return names

    # 与 X、Y（简称…）签订…投资协议  (BSE 特殊投资约定)
    for mm in re.finditer(r'与([一-鿿A-Za-z（）()、，,]{2,300}?)[（(]简称', ns):
        names += _split_prose_names(mm.group(1))

    # 向X定向发行(股票)  —— (?<!定) 避免误匹配「定向发行」自带的「向」
    for mm in re.finditer(r'(?<!定)向([一-鿿A-Za-z（）()]{2,40}?)(?:定向发行|非公开发行)', ns):
        names.append(clean_name(mm.group(1)))

    # 由 名单 (顿号分隔) …认缴/认购/出资
    for mm in re.finditer(r'由(?:新股东|新增股东)?([一-鿿A-Za-z0-9&（）()·、，,]{2,400}?)(?:分别|共同)?(?:以[^。；，、]{0,40}?)?(?:认缴|认购|出资|增资)', ns):
        names += _split_prose_names(mm.group(1))

    # individual "X(以…)?(认缴|认购|出资) 数额"
    for mm in re.finditer(r'([一-鿿A-Za-z（）()][一-鿿A-Za-z0-9&（）()·\-]{0,39}?)(?:以[^。；，、]{0,25}?)?(?:认缴|认购|出资)\s*[\d,]', ns):
        n = clean_name(mm.group(1))
        if n:
            names.append(n)

    return names


def extract_capital_receipt_names(body):
    """「X以货币资金…实缴…出资额」——北交所报告期增资扩股散文的投资者全称。

    gold 用释义表简称（新世电子/罗实投资/韵仪投资），全称需在 add 前转简称。
    """
    ns = normspace(body)
    out = []
    for mm in re.finditer(r'([一-鿿A-Za-z0-9（）()·]{2,60}?)以货币资金', ns):
        n = clean_name(mm.group(1))
        if n and 2 <= len(n) <= 60:
            out.append(n)
    return out


def extract_receipt_names(body):
    """「已收到 X、Y 缴纳(的)出资款」——北交所定向发行验资报告口径。

    例: 截至 2022年8月9 日，公司已收到稳正景明、长泽创投缴纳的出资款 2,374.40万元。
    名单在「收到」与「缴纳/缴付」之间，顿号或「及/和/与」分隔；简称已在释义表。
    （自然人认购人由 is_institution 在 add 阶段过滤，不新增 FP。）
    """
    ns = normspace(body)
    out = []
    for mm in re.finditer(r'收到([一-鿿A-Za-z0-9&（）()·、，,]{2,300}?)(?:等)?(?:缴纳|缴付)', ns):
        out += _split_prose_names(mm.group(1))
    return out


# --------------------------------------------------------------------------- #
# heading-embedded investor names (增资/转让轮次的投资者常直接写在标题里)
# --------------------------------------------------------------------------- #
def extract_heading_investors(heading):
    ns = normspace(heading)
    names = []
    # 引入/引进 X、Y、Z（等股东/投资者/机构）
    for m in re.finditer(r'(?:引入|引进)([一-鿿A-Za-z0-9（）()、，,]{2,300}?)(?:等)?(?:股东|投资者|机构|成为|$)', ns):
        names += _split_prose_names(m.group(1))
    # X 受让 …（受让方位于"受让"之前）
    for m in re.finditer(r'([一-鿿A-Za-z（）()]{2,40}?)受让', ns):
        names.append(clean_name(m.group(1)))
    return names


# --------------------------------------------------------------------------- #
# 增资/发行 table subscriber column (增资股东/新增股东/发行对象/认购人…)
# --------------------------------------------------------------------------- #
def extract_subscriber_names(body):
    names = []
    for table in re.findall(r'<table.*?</table>', body, re.S | re.I):
        rows = parse_table(table)
        if not rows:
            continue
        nj = _header_index(rows[0], ('增资股东', '新增股东', '发行对象', '认购人', '认缴人', '受让股东', '出资人'))
        if nj is None:
            continue
        for r in rows[1:]:
            if nj >= len(r):
                continue
            n = clean_name(r[nj])
            if n and '合计' not in n and not _is_num(n):
                names.append(n)
    return names


# --------------------------------------------------------------------------- #
# "新增股东情况" 专项披露（主板/创业板申报前12个月 + 北交所报告期3年）
#   (A) 表格：新增股东 | … | 取得股份的时间及方式（行内带日期+方式）
#   (B) 子标题：新增外部股东情况 → "（N）X经营、投资情况"
# --------------------------------------------------------------------------- #
def extract_recent_new_shareholders(text):
    out = []  # (date_ym, event, name)

    # (A) table form
    for table in re.findall(r'<table.*?</table>', text, re.S | re.I):
        rows = parse_table(table)
        if not rows:
            continue
        nj = _header_index(rows[0], ('新增股东', '股东名称', '股东姓名'))
        dj = _header_index(rows[0], ('取得股份', '时间及方式', '入股时间', '取得时间'))
        if nj is None or dj is None:
            continue
        for r in rows[1:]:
            if nj >= len(r) or dj >= len(r):
                continue
            n = clean_name(r[nj])
            if not n or '合计' in n or _is_num(n):
                continue
            m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月', r[dj])
            if not m:
                continue
            date_ym = f"{m.group(1)}-{int(m.group(2)):02d}"
            et = '股权转让' if ('转让' in r[dj] or '受让' in r[dj]) else '增资'
            out.append((date_ym, et, n))

    # (B) 新增外部股东情况 subsection headings
    cur_date = None
    for ln in text.splitlines():
        s = ln.strip()
        if not s.startswith('#'):
            continue
        h = s.lstrip('#').strip()
        if '新增外部股东情况' in h or '新增股东情况' in h:
            d = heading_date_ym(h)
            if d:
                cur_date = d
            continue
        m = re.match(r'^[（(]?\d+[）)、.]?\s*(.{2,25}?)(?:经营、投资情况|经营情况及合规|投资情况)', h)
        if cur_date and m:
            out.append((cur_date, '增资', m.group(1)))
            continue
        cur_date = None

    return out


# --------------------------------------------------------------------------- #
# 对赌条款 / 特殊投资约定表（协议名称 | 签署时间 | 签署主体 | 特殊权利内容）
# --------------------------------------------------------------------------- #
def _party_names(before_label):
    """「投资方」名单片段 → 名称列表（剥离「发行人」party 标签前缀，rowspan 溢出）。"""
    s = re.sub(r'^发行人(?:及|、|，|与|和)?', '', clean(before_label))
    return _split_prose_names(s)


def extract_investment_contract_rows(text):
    """从对赌条款/特殊投资约定表抽取 (date_ym, event, investor)。

    gold 日期口径 = 投资合同书 / 股份转让合同书 的签署月（301658 验证：问鼎投资
    投资合同书 2021.11.25 → 2021-11，而非股本变化表的增资完成月 2021-12）。
    「投资方」= 新进 PE/VC；「转让给 X」= 股份转让受让方。
    """
    out = []
    for table in re.findall(r'<table.*?</table>', text, re.S | re.I):
        rows = parse_table(table)
        if not rows:
            continue
        name_i = _header_index(rows[0], ('协议名称', '合同名称', '协议'))
        time_i = _header_index(rows[0], ('签署时间', '签署日期', '签订时间', '签订日期'))
        subj_i = _header_index(rows[0], ('签署主体', '签订主体', '主体'))
        cont_i = _header_index(rows[0], ('权利内容', '特殊权利', '主要内容', '内容'))
        if name_i is None or time_i is None or subj_i is None:
            continue
        for r in rows[1:]:
            if name_i >= len(r) or time_i >= len(r):
                continue
            nm, tm = r[name_i], r[time_i]
            sj = r[subj_i] if subj_i < len(r) else ''
            ct = r[cont_i] if cont_i is not None and cont_i < len(r) else ''
            m = re.search(r'(\d{4})\s*[.．年]\s*(\d{1,2})\s*[.．月]', tm)
            if not m:
                continue
            date_ym = f"{m.group(1)}-{int(m.group(2)):02d}"
            is_transfer = '股份转让' in nm or '股权转让' in nm
            etype = '股权转让' if is_transfer else ('增资' if ('投资合同' in nm or '增资' in nm) else None)
            if etype is None:
                continue
            ns = normspace(sj)
            # 「X、Y（合称"投资方"）」/「X（"投资方"）」；排除「（」「）」防跨 label 误取
            for mm in re.finditer(r'([^（(）)]{1,300}?)[（(][^）)]{0,12}?投资方', ns):
                for n in _party_names(mm.group(1)):
                    out.append((date_ym, etype, n))
            # 股份转让受让方：「…转让给 X」
            if is_transfer:
                nc = normspace(ct)
                for mm in re.finditer(r'转让给([一-鿿A-Za-z0-9（）()]{2,40}?)(?=[。；，,]|$)', nc):
                    out.append((date_ym, '股权转让', clean_name(mm.group(1))))
    return out


# --------------------------------------------------------------------------- #
# per-company extraction (two-pass: non-整体变更 first, then 整体变更 de-dup)
# --------------------------------------------------------------------------- #
def extract_company(code):
    md = get_md_dir()
    parts = []
    for fn in MD_FILES.get(code, []):
        p = md / fn
        if p.exists():
            parts.append(p.read_text(encoding='utf-8'))
    text = _correct_ocr('\n'.join(parts))
    if not text:
        return []

    aliases = alias_map(text)
    full2alias = _full2alias(text)
    emp = employee_platforms(text)
    tech = tech_founders(text)
    ctl = controllers(text)
    spv = holding_spvs(text)
    iss = issuer_names(text)

    rows = []
    seen = set()
    seen_prior = set()  # names extracted in a non-整体变更 event

    def canon_key(nn):
        """名称的 canonical 全称键 —— 别名→全称归一，使「厦门联和」与「联和二期」
        指向同一实体（整体变更发起人去重时按同一股东跳过）。"""
        return normspace(aliases.get(nn, nn)).upper()

    def add(date_ym, etype, name, evidence=''):
        name = clean_name(name)
        if not name:
            return
        # 验资报告句内噪声（「…收到了 X 等 N 名股东的…」「…收到了 X 和 Y 缴纳的」）
        if re.search(r'(收到|缴纳|名股东)', name):
            return
        # 散文句子碎片（「由华秦投资享有…」「省人民政府授权…履行国有出资人职责」）
        if is_name_fragment(name):
            return
        if not is_institution(name, aliases):
            return
        nn = normspace(name)
        # rowspan 截断碎片（「长久集团」被拆成「长」+「久集团」）：短名以基金/公司后缀
        # 结尾、且非释义表别名 → 拒（「深创投」3 字但尾缀「创投」非「投资」，不受影响）。
        if (len(nn) <= 3
                and re.search(r'(集团|公司|基金|合伙|投资|资本|有限|中心|控股|实业|证券|银行|保险|信托)$', nn)
                and nn not in aliases):
            return
        # 仅对「截断的全称」（括号未闭合）归一为简称；干净全称保持原样
        # （gold 命名口径不一致：920098 用简称，DEV 920008 用全称）。
        if _is_truncated(nn):
            short = _canonical_short(nn, full2alias)
            if short:
                name = short
                nn = normspace(name)
        if nn in emp or nn in tech or nn in ctl or nn in spv or nn in iss or is_employee_platform(name, aliases):
            return
        key = (code, date_ym[:7], etype, nn.upper())
        if key in seen:
            return
        seen.add(key)
        rows.append({
            'stock_code': code, 'subscription_date': date_ym, 'event_context': etype,
            'subscriber_name': name, 'amount_subscribed': None,
            'shares_subscribed': None, 'price_per_share': None,
            'evidence_text': evidence[:500], 'extraction_method': 'stage5d_cross_board',
            'source': 'heading_or_table',
        })
        if etype != '整体变更':
            seen_prior.add(canon_key(nn))

    # pre-pass: "新增股东情况" 专项披露（最近一年/申报前12个月 新增股东）
    for d, et, n in extract_recent_new_shareholders(text):
        add(d, et, n, evidence='recent_new_shareholder')

    # pre-pass: 对赌条款/特殊投资约定表（投资合同书/股份转让合同书 → 日期+投资方）
    for d, et, n in extract_investment_contract_rows(text):
        add(d, et, n, evidence='investment_contract')

    sections = split_sections(text)
    overall_change = []
    parent_ctx = None  # (date_ym, etype) from the most recent dated event heading

    for heading, body in sections:
        date_ym = heading_date_ym(heading)
        etype = heading_event(heading)
        is_child = bool(re.match(r'^[（(]\d+[）)]', heading))

        # 结构感知：「增资(和/及)股权转让」/「股权转让」父标题下，「(N)…」子条目
        # 继承父级日期；合并事件口径（gold 用「增资及股权转让」统一命名）。
        if etype in ('增资及股权转让', '股权转让') and date_ym is not None:
            parent_ctx = (date_ym, etype)
        elif is_child and parent_ctx is not None and date_ym is None and etype in ('增资', '股权转让'):
            date_ym = parent_ctx[0]
            if parent_ctx[1] == '增资及股权转让':
                etype = '增资及股权转让'
        elif not is_child:
            # 离开父标题子树（新的顶层标题）→ 清空继承上下文
            parent_ctx = None

        # 报告期股本变化汇总表 (undated heading, rows carry date+detail)
        if etype is None and any(k in heading for k in ('股本和股东变化', '股本变化情况', '股东变化情况', '股本及股东变化')):
            for d, et, detail in extract_summary_change_rows(body):
                if et == '设立':
                    continue
                if et == '整体变更':
                    overall_change.append((d, body))
                    continue
                for n in extract_prose_investors(detail, et):
                    add(d, et, n, evidence=detail)

        if etype is None:
            continue
        if date_ym is None:
            date_ym = prose_date_ym(body)
        if date_ym is None:
            continue

        # investor names embedded directly in the section heading
        for n in extract_heading_investors(heading):
            add(date_ym, etype, n, evidence=clean(body)[:200])

        if etype == '整体变更':
            overall_change.append((date_ym, body))
            continue

        if etype == '股权转让':
            tnames = extract_transfer_names(body)
            if tnames:
                for n in tnames:
                    add(date_ym, '股权转让', n, evidence=clean(body)[:200])
            else:
                for n in extract_prose_investors(body, '股权转让'):
                    add(date_ym, '股权转让', n, evidence=clean(body)[:200])

        elif etype == '设立':
            snames = extract_shareholder_names(body)
            if snames:
                for n in snames:
                    add(date_ym, '设立', n, evidence=clean(body)[:200])
            else:
                for n in extract_prose_investors(body, '设立'):
                    add(date_ym, '设立', n, evidence=clean(body)[:200])

        else:  # 增资 / 增资及股权转让
            for n in extract_prose_investors(body, '增资'):
                add(date_ym, etype, n, evidence=clean(body)[:200])
            # 北交所报告期增资散文「X以货币资金…实缴…出资额」：全称→释义表简称
            for n in extract_capital_receipt_names(body):
                short = _canonical_short(normspace(n), full2alias)
                add(date_ym, etype, short or n, evidence=clean(body)[:200])
            # 北交所定向发行验资散文「已收到 X、Y 缴纳的出资款」
            for n in extract_receipt_names(body):
                add(date_ym, etype, n, evidence=clean(body)[:200])
            for n in extract_subscriber_names(body):
                add(date_ym, etype, n, evidence=clean(body)[:200])
            if etype == '增资及股权转让':
                for n in extract_transfer_names(body):
                    add(date_ym, '增资及股权转让', n, evidence=clean(body)[:200])

    # second pass: 整体变更 发起人, keeping only names not seen in earlier events
    for date_ym, body in overall_change:
        d2 = overall_change_date_ym(body) or date_ym
        snames = extract_shareholder_names(body)
        if snames:
            for n in snames:
                if canon_key(normspace(n)) in seen_prior:
                    continue
                add(d2, '整体变更', n, evidence=clean(body)[:200])
        else:
            for n in extract_prose_investors(body, '整体变更'):
                if canon_key(normspace(n)) in seen_prior:
                    continue
                add(d2, '整体变更', n, evidence=clean(body)[:200])

    return rows


def build(out_dir, codes):
    out_dir.mkdir(parents=True, exist_ok=True)
    for code in codes:
        rows = extract_company(code)
        path = out_dir / f"{code}_subscription_flow.jsonl"
        path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows),
                        encoding='utf-8')
        print(code, 'rows', len(rows))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--companies', nargs='*', required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    build(args.out, args.companies)
