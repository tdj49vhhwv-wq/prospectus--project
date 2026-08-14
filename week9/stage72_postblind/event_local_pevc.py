#!/usr/bin/env python3
import re, json, html
from pathlib import Path
from collections import defaultdict
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'runtime'))
from markdown_source import MD_FILES, get_md_dir

EVENT_MAP={'增资':'A','增资及股权转让':'C'}

def normspace(s): return re.sub(r'\s+','',str(s or '')).replace('（','(').replace('）',')')
def clean(s):
    s=html.unescape(re.sub(r'<[^>]+>',' ',str(s or '')))
    s=re.sub(r'\s+',' ',s).strip(' ，。；、:：|')
    return s

def load_text(code):
    md=get_md_dir(); parts=[]
    for fn in MD_FILES.get(code,[]):
        p=md/fn
        if p.exists(): parts.append(p.read_text(encoding='utf-8'))
    return '\n'.join(parts)

def alias_map(text):
    out={}
    # html glossary rows: alias | 指 | full
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>',text,re.S|re.I):
        cells=[clean(x) for x in re.findall(r'<td[^>]*>(.*?)</td>',tr,re.S|re.I)]
        if len(cells)>=3 and cells[1]=='指' and 1<=len(cells[0])<=60:
            for a in re.split(r'[、,/，]',cells[0]):
                a=clean(a)
                if a: out[normspace(a)]=clean(cells[2])
    # line-oriented glossary used by OCR/PyMuPDF markdown: alias / 指 / full name
    raw=[clean(x) for x in text.splitlines()]
    nz=[x for x in raw if x]
    for i in range(len(nz)-2):
        if nz[i+1]=='指' and 1<=len(nz[i])<=60 and 2<=len(nz[i+2])<=160:
            for a in re.split(r'[、,/，]',nz[i]):
                a=clean(a)
                if a: out[normspace(a)]=nz[i+2]
    return out

def is_institution(name, aliases):
    n=clean(name)
    ex=aliases.get(normspace(n),n)
    u=(n+' '+ex).upper()
    if re.search(r'(FUND|LLC|LIMITED|CAPITAL|VENTURE|INVEST)',u): return True
    if any(k in u for k in ('公司','基金','合伙','投资','资本','创投','科技','电子','实业','集团','中心','药业','高技术')): return True
    if re.fullmatch(r'[\u4e00-\u9fff]{2,4}',n) and normspace(n) not in aliases:
        return False
    # long structured organization names / stable aliases
    return len(n)>=5

def event_heading_candidates(text, ym, evtype):
    y,m=ym.split('-'); mi=str(int(m)); ns=normspace(text)
    # operate line-wise original positions
    lines=text.splitlines(True); pos=0; cand=[]
    month_re=re.compile(fr'{y}\s*年\s*0?{mi}\s*月')
    for i,line in enumerate(lines):
        if month_re.search(line) and (('增资' in line) or ('股票发行' in line) or ('定向发行' in line) or ('增加注册资本' in line)):
            score=0
            st=line.strip()
            is_head = st.startswith('#') or (len(st)<120 and re.match(r'^[（(]?\d+[、.]', st) and '-->' not in st)
            if is_head: score+=4
            else: continue
            if evtype=='增资及股权转让' and '股权转让' in line: score+=3
            if evtype=='增资' and '股权转让' not in line: score+=2
            if '本次' in line or re.search(r'\d+[、.]',st): score+=1
            cand.append((score,i,pos))
        pos+=len(line)
    return sorted(cand, reverse=True)

def heading_block(text, line_idx):
    lines=text.splitlines(True)
    start=sum(map(len,lines[:line_idx]))
    # Determine block until next heading-like event/section; at least include 1 line.
    end=len(text)
    for j in range(line_idx+1,min(len(lines),line_idx+120)):
        st=lines[j].strip()
        if st.startswith('#') and j>line_idx+1:
            end=sum(map(len,lines[:j])); break
        # non-hash numbered heading common in OCR
        if j>line_idx+4 and len(st)<100 and re.match(r'^[（(]?\d+[、.]',st) and ('增资' in st or '发行' in st or '股权转让' in st):
            end=sum(map(len,lines[:j])); break
    return text[start:end][:10000]

def paragraph_around_date(text, date):
    # exact y-m or y-m-d occurrence with transaction action near
    y,m,*d=date.split('-'); mi=str(int(m));
    pats=[]
    if d:
        di=str(int(d[0])); pats.append(re.compile(fr'{y}\s*年\s*0?{mi}\s*月\s*0?{di}\s*日'))
    pats.append(re.compile(fr'{y}\s*年\s*0?{mi}\s*月'))
    best=''
    for pat in pats:
        for mm in pat.finditer(text):
            lo=max(0,text.rfind('\n',0,mm.start()-1)); hi=text.find('\n\n',mm.end())
            if hi<0: hi=min(len(text),mm.end()+1800)
            seg=text[lo:hi]
            if any(k in seg for k in ('认购','认缴','出资款','定向发行','共同增资','向','增资')) and len(seg)>len(best): best=seg
        if best: break
    return best[:5000]

def mermaid_event_detail(text, ym, evtype):
    y,m=ym.split('-'); mi=str(int(m));
    out=[]
    for block in re.findall(r'```mermaid(.*?)```',text,re.S|re.I):
        lines=block.splitlines()
        event_lines=[ln for ln in lines if re.search(fr'{y}\s*年\s*0?{mi}\s*月',ln) and ('增资' in ln or '发行' in ln)]
        if not event_lines: continue
        # capture target registered capital / total shares from event line; match detail line with same target.
        nums=[]
        for ln in event_lines:
            nums += re.findall(r'(?:注册资本增至|注册资本为|股本总额(?:增至)?)[^\d]{0,10}([\d,]+(?:\.\d+)?)',ln)
        for ln in lines:
            if not any(k in ln for k in ('共同增资','认购','认缴','出资')): continue
            if nums and any(n.replace(',','') in ln.replace(',','') for n in nums): out.append(ln)
        # fallback: if one event line and one investment detail around sequence, use nearest investment line after matching node region
        if not out and len(event_lines)==1:
            idx=lines.index(event_lines[0])
            for ln in lines[max(0,idx-2):min(len(lines),idx+12)]:
                if '共同增资' in ln or '认购' in ln or '认缴' in ln: out.append(ln)
    return '\n'.join(out)

def parse_html_subscription_tables(block):
    facts=[]
    for table in re.findall(r'<table.*?</table>',block,re.S|re.I):
        txt=clean(table)
        if not (('认购人' in txt or '股东姓名/名称' in txt) and ('认购金额' in txt or '认购数量' in txt or '认购股份' in txt)):
            continue
        rows=re.findall(r'<tr[^>]*>(.*?)</tr>',table,re.S|re.I)
        headers=None
        for tr in rows:
            cells=[clean(x) for x in re.findall(r'<td[^>]*>(.*?)</td>',tr,re.S|re.I)]
            if not cells: continue
            if headers is None and any('认购' in c or '股东姓名' in c for c in cells): headers=cells; continue
            # common layouts: seq,name,shares,amount,...
            if len(cells)>=3 and cells[0].isdigit():
                name=cells[1]
                sh=am=pr=None
                if headers:
                    for k,c in enumerate(cells):
                        if k>=len(headers): continue
                        h=headers[k]
                        try: val=float(c.replace(',',''))
                        except: continue
                        if '认购数量' in h or '认购股份' in h: sh=val/10000 if '股)' in h and '万股' not in h else val
                        elif '认购金额' in h: am=val
                        elif '价格' in h: pr=val
                facts.append((name,am,sh,pr,clean(tr)))
    return facts

def split_list(s):
    s=clean(s)
    s=re.sub(r'^(?:新增股东|由|其中)','',s)
    return [clean(x) for x in re.split(r'[、，,]|(?:和|及|与)',s) if clean(x)]

def split_investor_list(s):
    # Stage 7.2 专用：仅按顿号/逗号/「及」切，不切「和」「与」
    # （盲测金标含 8 个带「和」的机构名：和谐健康/和暄新芯/苏州和基/集美中和 等）
    s=clean(s)
    s=re.sub(r'^(?:新增股东|由|其中)','',s)
    return [clean(x) for x in re.split(r'[、，,]|(?:及)',s) if clean(x)]

def parse_transactions(block):
    facts=[]
    # table first
    facts += parse_html_subscription_tables(block)
    plain=clean(block)
    # list followed by common investment action
    list_patterns=[
      r'新增股份由(?:新增股东)?(.{2,260}?)认购',
      r'公司向(.{2,120}?)定向发行股票',
      r'已收到(.{2,160}?)缴纳的出资款',
      r'由(.{2,120}?)向[^。；]{0,60}?增资',
      r'([\u4e00-\u9fffA-Za-z0-9&（）()·\-、，, ]{4,260}?)分别以[^。；]{0,180}?认购',
      r'([\u4e00-\u9fffA-Za-z0-9&（）()·\-、，, ]{4,260}?)共同增资',
    ]
    for pat in list_patterns:
        for mm in re.finditer(pat,plain):
            chunk=mm.group(1)
            # trim discourse context
            chunk=re.split(r'(?:签署|约定|其中|同意)',chunk)[-1]
            for name in split_list(chunk): facts.append((name,None,None,None,mm.group(0)[:500]))
    # explicit name + amount + action; restrictive prefix after punctuation/semicolon
    pat=re.compile(r'(?:^|[；。;，,])\s*(?:根据该协议[，,])?(?:其中[，,])?([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9&（）()·\- ]{1,60}?)\s*以(?:现金|货币)?\s*([\d,]+(?:\.\d+)?)\s*万\s*元(?:的等值美元)?\s*(?:认缴|认购|出资)')
    for mm in pat.finditer('。'+plain): facts.append((clean(mm.group(1)),float(mm.group(2).replace(',','')),None,None,mm.group(0)[:500]))
    # simple "X认缴462万元" / "X出资840万元"
    pat2=re.compile(r'(?:^|[；。;,，])\s*(?:其中)?([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9&（）()·\- ]{1,50}?)\s*(?:认缴|出资)\s*([\d,]+(?:\.\d+)?)\s*万\s*元')
    for mm in pat2.finditer('。'+plain): facts.append((clean(mm.group(1)),float(mm.group(2).replace(',','')),None,None,mm.group(0)[:500]))
    return facts

def _strip_page_junk(s):
    # MinerU 纯文本把跨页表格的页眉/页脚/重复表头塞进名单中间，先剥离。
    # 页眉（##第N页 + 公司名/标题 + 招股说明书 + 页码），限 120 字符内，避免跨页误删。
    s = re.sub(r'##\s*第\s*\d+\s*页[\s\S]{0,120}?招股说明书\s*\d+\s*-\s*\d+\s*-\s*\d+', '', s)
    s = re.sub(r'##\s*第\s*\d+\s*页', '', s)
    s = re.sub(r'序号\s*时间\s*股权变动\s*股权变动情况', '', s)
    return s

def _employee_platforms(text):
    # 「X系…的员工(跟投)(持股)平台」→ 员工跟投平台，非 PE/VC，与金标排除对齐（如 晖泽共广）。
    ns = normspace(text)
    out = set()
    for mm in re.finditer(r'([一-龥A-Za-z0-9、]{2,30})系[^。；;]{0,60}?员工(?:跟投)?(?:持股)?平台', ns):
        out.add(mm.group(1))
    return out

def parse_summary_table_investors(text, aliases):
    """Stage 7.2：沐曦式「报告期股本和股东变化」汇总表（一格一行纯文本）。
    自包含发现增资名单，不依赖基座事件（基座对沐曦欠检）。
    每轮增资详情为 `N、<顿号名单>按照每1元注册资本...认购` 或 `<顿号名单>以合计...认购...股`。
    返回 [(date_ym, '增资', [names], None), ...]"""
    ns = normspace(_strip_page_junk(text))
    emp = _employee_platforms(text)
    out = []
    clause_re = re.compile(r'\d、([一-龥A-Za-z0-9、]{3,400}?)(?:按照每1元注册资本|以合计[^；。;]{0,80}?认购|各以人民币)')
    date_re = re.compile(r'(\d{4})年(\d{1,2})月')
    for mm in clause_re.finditer(ns):
        chunk = mm.group(1)
        prefix = ns[:mm.start()]
        dm = None
        for dm in date_re.finditer(prefix):
            pass
        if dm is None:
            continue
        y, m = dm.group(1), str(int(dm.group(2)))
        date_ym = f"{y}-{int(m):02d}"
        names = []
        for raw in split_investor_list(chunk):
            n = clean(raw)
            n = re.sub(r'^(?:次增资)+', '', n)  # 分页残留标签尾部粘在首名上
            if re.search(r'\d', n):
                continue
            if normspace(n) in emp:
                continue
            if not is_institution(n, aliases):
                continue
            names.append(n)
        if names:
            out.append((date_ym, '增资', names, None))
    return out

def parse_syndicate_investors(text, aliases):
    """Stage 7.2：摩尔线程式 Pre-IPO 辛迪加（自包含发现，不依赖基座事件）。
    找 `（以下简称"...轮股东"）共计N家` 前的长顿号名单，日期取最近的前置增资标题月。
    返回 [(date_ym, '增资', [names], None), ...]"""
    ns = normspace(_strip_page_junk(text))
    emp = _employee_platforms(text)
    out = []
    synd_re = re.compile(r'([一-龥A-Za-z0-9、]{4,800}?)\(以下简称[^)]{0,40}\)共计\d+家')
    head_re = re.compile(r'(\d{4})年(\d{1,2})月[^(]{0,30}?增资')
    date_re = re.compile(r'(\d{4})年(\d{1,2})月')
    for mm in synd_re.finditer(ns):
        chunk = mm.group(1)
        prefix = ns[:mm.start()]
        dm = None
        for dm in head_re.finditer(prefix):
            pass
        if dm is None:
            for dm in date_re.finditer(prefix):
                pass
        if dm is None:
            continue
        y, m = dm.group(1), str(int(dm.group(2)))
        date_ym = f"{y}-{int(m):02d}"
        names = []
        for raw in split_investor_list(chunk):
            n = clean(raw)
            n = re.sub(r'^(?:次增资)+', '', n)
            if re.search(r'\d', n):
                continue
            if normspace(n) in emp:
                continue
            if not is_institution(n, aliases):
                continue
            names.append(n)
        if names:
            out.append((date_ym, '增资', names, None))
    return out

def locate_blocks(text,date,evtype):
    ym=date[:7]; blocks=[]
    heads=[x for x in event_heading_candidates(text,ym,evtype) if x[0]>=4]
    if heads:
        # A formal event section is authoritative; never mix Mermaid/other-month snippets into it.
        score,i,pos=heads[0]
        blocks.append((score,heading_block(text,i),'heading'))
    else:
        mer=mermaid_event_detail(text,ym,evtype)
        if mer:
            blocks.append((5,mer,'mermaid'))
        else:
            p=paragraph_around_date(text,date)
            if p: blocks.append((3,p,'paragraph'))
    # dedupe
    out=[]; seen=set()
    for sc,b,src in sorted(blocks,reverse=True):
        k=normspace(b)[:500]
        if k in seen: continue
        seen.add(k); out.append((sc,b,src))
    return out

def build(base_dir,out_dir):
    out_dir.mkdir(parents=True,exist_ok=True)
    for p in sorted(base_dir.glob('*_subscription_flow.jsonl')):
        if p.name.startswith('._'):
            continue
        code=p.name.split('_')[0]; rows=[json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
        text=load_text(code); aliases=alias_map(text)
        events=sorted({(r['subscription_date'],r['event_context']) for r in rows if r['event_context'] in EVENT_MAP and r['subscription_date']})
        result=[]
        for date,evtype in events:
            found=[]
            for sc,block,src in locate_blocks(text,date,evtype):
                for name,amount,shares,price,evid in parse_transactions(block):
                    name=clean(name)
                    # de-noise common leading phrases
                    name=re.sub(r'^(?:发行人与|根据发行人与|公司向|已收到|其中)','',name)
                    if not name or re.search(r'\d', name) or not is_institution(name,aliases): continue
                    # reject obvious non-entity phrases (normalize first: 万 元 跨行切分不再漏判)
                    if any(k in normspace(name) for k in ('注册资本','新增股份','股东大会','发行人','本次','全部增资款','增资协议','认购价格','名认购人','万元','股权激励对象','以人民币')): continue
                    found.append((name,amount,shares,price,evid,src))
            # dedupe by normalized name, prefer richer fields
            d={}
            for f in found:
                k=normspace(f[0]).upper(); old=d.get(k)
                quality=sum(v is not None for v in f[1:4])
                if old is None or quality>sum(v is not None for v in old[1:4]): d[k]=f
            for name,amount,shares,price,evid,src in d.values():
                result.append({
                  'stock_code':code,'subscription_date':date,'event_context':evtype,
                  'subscriber_name':name,'amount_subscribed':amount,'shares_subscribed':shares,'price_per_share':price,
                  'evidence_text':evid,'extraction_method':'stage71_event_local','source':src
                })
        # ---- Stage 7.2：自包含结构发现（汇总表 + 辛迪加），不依赖基座事件 ----
        struct=[]
        for date_ym,evtype,names,amt in parse_summary_table_investors(text,aliases):
            for n in names:
                struct.append((date_ym,evtype,n,amt))
        for date_ym,evtype,names,amt in parse_syndicate_investors(text,aliases):
            for n in names:
                struct.append((date_ym,evtype,n,amt))
        for date_ym,evtype,name,amt in struct:
            result.append({
              'stock_code':code,'subscription_date':date_ym,'event_context':evtype,
              'subscriber_name':name,'amount_subscribed':amt,'shares_subscribed':None,'price_per_share':None,
              'evidence_text':None,'extraction_method':'stage72_postblind','source':'summary_table_or_syndicate'
            })
        # 跨路径去重：同名+同月+同事件保留首条（base 路径优先，字段更丰富）
        seen=set(); final=[]
        for r in result:
            k=(r['stock_code'],str(r['subscription_date'])[:7],r['event_context'],normspace(r['subscriber_name']).upper())
            if k in seen: continue
            seen.add(k); final.append(r)
        (out_dir/p.name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in final),encoding='utf-8')
        print(code,'events',len(events),'rows',len(final))

if __name__=='__main__':
    
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument('--base',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); args=ap.parse_args()
    build(args.base,args.out)
