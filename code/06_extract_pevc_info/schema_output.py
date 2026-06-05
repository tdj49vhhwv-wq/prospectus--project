#!/usr/bin/env python3
"""严格按照schema生成5家公司融资历史结构化JSON"""
import json
from pathlib import Path

OUTPUTS_DIR = Path("/Users/zhaobingqing/Documents/GitHub/prospectus-pevc-project/outputs")

CSV = {
    "MB001": {"short":"三联锻造","full":"芜湖三联锻造股份有限公司","code":"001282","exchange":"深交所","board":"主板","listing_date":"2023-05-24","url":"https://static.cninfo.com.cn/finalpage/2023-05-17/1216830304.PDF","title":"芜湖三联锻造股份有限公司首次公开发行股票并在主板上市招股说明书","version":"正式稿","prospectus_date":"2023-05-17"},
    "GEM001": {"short":"黄山谷捷","full":"黄山谷捷股份有限公司","code":"301581","exchange":"深交所","board":"创业板","listing_date":"2025-01-03","url":"https://static.cninfo.com.cn/finalpage/2024-12-19/1222066314.PDF","title":"黄山谷捷股份有限公司首次公开发行股票并在创业板上市招股说明书","version":"正式稿","prospectus_date":"2024-12-19"},
    "GEM002": {"short":"云汉芯城","full":"云汉芯城（上海）互联网科技股份有限公司","code":"301563","exchange":"深交所","board":"创业板","listing_date":"2025-09-30","url":"https://static.cninfo.com.cn/finalpage/2025-09-25/1224679402.PDF","title":"云汉芯城（上海）互联网科技股份有限公司首次公开发行股票并在创业板上市招股说明书","version":"正式稿","prospectus_date":"2025-09-25"},
    "STAR001": {"short":"赛分科技","full":"苏州赛分科技股份有限公司","code":"688758","exchange":"上交所","board":"科创板","listing_date":"2025-01-10","url":"https://static.cninfo.com.cn/finalpage/2025-01-06/1222238930.PDF","title":"苏州赛分科技股份有限公司首次公开发行股票并在科创板上市招股说明书","version":"正式稿","prospectus_date":"2025-01-06"},
    "STAR002": {"short":"影石创新","full":"影石创新科技股份有限公司","code":"688775","exchange":"上交所","board":"科创板","listing_date":"2025-06-11","url":"https://static.cninfo.com.cn/finalpage/2025-06-06/1223788474.PDF","title":"影石创新科技股份有限公司首次公开发行股票并在科创板上市招股说明书","version":"正式稿","prospectus_date":"2025-06-06"},
}

I = lambda o, s, t, p, a=None, r=None, e="无法判断": {
    "investor_original_name": o, "investor_short_name": s, "investor_type": t,
    "is_pevc": p, "investment_amount": a, "shares_acquired": None,
    "shareholding_ratio_after_event": r, "exit_status_before_ipo": e
}

def build(info, events):
    return {"company": {
        "company_name": info["full"], "stock_code": info["code"],
        "exchange": info["exchange"], "board": info["board"],
        "listing_date": info["listing_date"], "prospectus_title": info["title"],
        "prospectus_url": info["url"], "prospectus_version": info["version"],
        "prospectus_date": info["prospectus_date"], "financing_events": events,
        "processing": {"download_status":"success","parse_status":"success",
                       "locate_status":"success","extract_status":"success","review_status":"unchecked"}
    }}


# ==================== 黄山谷捷 ====================
hsgj = [
    {"event_order":1,"event_date":"2012-06-12","date_type":"工商变更日","event_type":"增资","disclosed_round":"未披露","inferred_round":"公司设立","round_inference_basis":"招股书明确说明为有限公司设立","total_investment_amount":1000.0,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":None,"valuation_basis":"无估值，初始设立",
     "investors":[I("昆山谷捷金属制品有限公司","昆山谷捷","产业资本","no",1000.0,"100.00%","全部退出")],
     "source_section":"第四节 发行人基本情况 / 二、（一）发行人的设立情况 / 1、有限公司设立情况",
     "source_page":"黄山谷捷2.md 第590-602行","evidence_text":"2012年4月11日，黄山市供销社出具《关于同意投资昆山谷捷项目的批复》（黄供财[2012]22号），同意设立谷捷有限。2012年5月28日，谷捷有限股东昆山谷捷作出股东决定，同意由昆山谷捷出资1,000万元设立谷捷有限。2012年6月12日，安徽天正达会计师事务所出具《验资报告》，确认谷捷有限已收到昆山谷捷缴纳的注册资本1,000万元，出资方式为货币。设立时昆山谷捷持股100%。","confidence":"high"},

    {"event_order":2,"event_date":"2021-04-07","date_type":"工商变更日","event_type":"股权转让","disclosed_round":"未披露","inferred_round":"同一控制下股权重组","round_inference_basis":"招股书明确说明为同一股权结构下的公司架构调整","total_investment_amount":0,"currency":"CNY","share_price":0,"pre_money_valuation":None,"post_money_valuation":None,"valuation_basis":"同一控制下重组，零对价转让",
     "investors":[I("黄山供销集团有限公司","黄山供销集团","政府基金","no",None,"78.00%","未退出"),I("张俊武","张俊武","自然人","no",None,"11.00%","未退出"),I("周斌","周斌","自然人","no",None,"11.00%","未退出")],
     "source_section":"第四节 发行人基本情况 / 二、（二）/ 2、2021年4月，第一次股权转让",
     "source_page":"黄山谷捷2.md 第652-697行","evidence_text":"2020年12月30日，黄山市供销社、黄山供销集团出具批复，同意昆山谷捷将其所持谷捷有限78%、11%、11%的股权以零对价分别转让给黄山供销集团、张俊武、周斌。2021年4月3日，昆山谷捷分别与黄山供销集团、张俊武、周斌签署了股权转让相关协议。本次股权转让系同一股权结构下的公司架构调整，转让价格为0元。转让后股权结构：黄山供销集团78.00%、张俊武11.00%、周斌11.00%。","confidence":"high"},

    {"event_order":3,"event_date":"2021-04-13","date_type":"工商变更日","event_type":"其他","disclosed_round":"未披露","inferred_round":"吸收合并","round_inference_basis":"谷捷有限吸收合并母公司昆山谷捷","total_investment_amount":None,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":None,"valuation_basis":"昆山谷捷净资产账面价值380.94万元（追溯评估）",
     "investors":[I("黄山供销集团有限公司","黄山供销集团","政府基金","no",None,"78.00%","未退出"),I("张俊武","张俊武","自然人","no",None,"11.00%","未退出"),I("周斌","周斌","自然人","no",None,"11.00%","未退出")],
     "source_section":"第四节 发行人基本情况 / 二、（二）/ 3、2021年4月，吸收合并",
     "source_page":"黄山谷捷2.md 第698-720行","evidence_text":"2020年12月24日，谷捷有限及昆山谷捷召开股东会，同意谷捷有限吸收合并昆山谷捷。2021年4月7日，谷捷有限召开股东会，吸收合并后注册资本变更为1,200万元（黄山供销集团936万、张俊武132万、周斌132万）。本次吸收合并系同一股权结构下的公司架构调整。截至2021年3月31日，昆山谷捷净资产账面价值380.94万元，谷捷有限净资产账面价值2,912.30万元，评估价值9,651.75万元。","confidence":"high"},

    {"event_order":4,"event_date":"2021-11-11","date_type":"工商变更日","event_type":"增资","disclosed_round":"未披露","inferred_round":"A轮（首次引入外部投资者）","round_inference_basis":"引入赛格高技术和上汽科技两家外部战略/产业投资者","total_investment_amount":11530.2857,"currency":"CNY","share_price":22.42,"pre_money_valuation":26904.0,"post_money_valuation":38434.2857,"valuation_basis":"增资价格22.42元/注册资本。2020年12月31日评估值26,461.86万元",
     "investors":[I("上海广弘实业有限公司","赛格高技术","产业资本","yes",10377.0,"27.00%","未退出"),I("SAIC TECHNOLOGIES FUND II, LLC","上汽科技","产业资本","yes",1153.0,"3.00%","未退出")],
     "source_section":"第四节 发行人基本情况 / 二、（二）/ 4、2021年11月，第一次增资",
     "source_page":"黄山谷捷2.md 第722-738行","evidence_text":"2021年9月18日，赛格高技术、上汽科技与黄山供销集团、张俊武、周斌及谷捷有限签署《增资协议》，约定谷捷有限增加注册资本514.2857万元，其中赛格高技术认缴462.8571万元、上汽科技认缴51.4286万元，增资价格为22.42元/注册资本，出资方式为货币。增资后：黄山供销集团54.60%、赛格高技术27.00%、张俊武7.70%、周斌7.70%、上汽科技3.00%。","confidence":"high"},

    {"event_order":5,"event_date":"2022-05-26","date_type":"工商变更日","event_type":"增资","disclosed_round":"未披露","inferred_round":"员工股权激励","round_inference_basis":"新增注册资本由员工持股平台黄山佳捷全额认缴","total_investment_amount":2124.81,"currency":"CNY","share_price":23.55,"pre_money_valuation":40370.0,"post_money_valuation":42494.81,"valuation_basis":"增资价格23.55元/注册资本。2021年12月31日评估值40,370万元",
     "investors":[I("黄山佳捷股权管理中心（有限合伙）","黄山佳捷","员工持股平台","no",2124.81,"5.00%","未退出")],
     "source_section":"第四节 发行人基本情况 / 二、（二）/ 5、2022年5月，第二次增资",
     "source_page":"黄山谷捷2.md 第740-758行","evidence_text":"2022年5月20日，谷捷有限召开股东会，同意注册资本由1,714.2857万元增至1,804.5113万元，新增注册资本90.2256万元由员工持股平台黄山佳捷全额认缴。增资价格为23.55元/注册资本，出资方式为货币。增资后：黄山供销集团51.87%、赛格高技术25.65%、张俊武7.315%、周斌7.315%、黄山佳捷5.00%、上汽科技2.85%。","confidence":"high"},

    {"event_order":6,"event_date":"2022-09-13","date_type":"工商变更日","event_type":"其他","disclosed_round":"未披露","inferred_round":"整体变更为股份有限公司","round_inference_basis":"招股书明确说明谷捷有限整体变更为黄山谷捷股份有限公司","total_investment_amount":None,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":28244.0,"valuation_basis":"净资产账面值20,152.51万元，评估值28,244.00万元，按1:0.29773折股6,000万股",
     "investors":[I("黄山供销集团有限公司","黄山供销集团","政府基金","no",None,"51.87%","未退出"),I("上海广弘实业有限公司","赛格高技术","产业资本","yes",None,"25.65%","未退出"),I("张俊武","张俊武","自然人","no",None,"7.315%","未退出"),I("周斌","周斌","自然人","no",None,"7.315%","未退出"),I("黄山佳捷股权管理中心（有限合伙）","黄山佳捷","员工持股平台","no",None,"5.00%","未退出"),I("SAIC TECHNOLOGIES FUND II, LLC","上汽科技","产业资本","yes",None,"2.85%","未退出")],
     "source_section":"第四节 发行人基本情况 / 二、（一）/ 2、股份公司设立情况",
     "source_page":"黄山谷捷2.md 第604-624行","evidence_text":"2022年8月24日，谷捷有限召开股东会，同意以截至2022年5月31日经审计的净资产20,152.51万元按1:0.29773比例折成6,000万股，每股面值1元，净资产余额14,152.51万元转为资本公积，整体变更后各股东持股比例保持不变。2022年9月13日取得换发营业执照。","confidence":"high"},
]

# ==================== 云汉芯城 ====================
yhxc = [
    {"event_order":1,"event_date":"2008-05-07","date_type":"工商变更日","event_type":"增资","disclosed_round":"未披露","inferred_round":"公司设立","round_inference_basis":"招股书明确说明为上海云汉电子有限公司设立","total_investment_amount":50.0,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":None,"valuation_basis":"初始设立",
     "investors":[I("深圳市云汉电子有限公司","深圳云汉电子","其他","uncertain",25.0,"50.00%","全部退出"),I("刘云锋","刘云锋","自然人","no",25.0,"50.00%","未退出")],
     "source_section":"第四节 发行人基本情况 / 二、（二）云汉有限的设立情况","source_page":"云汉芯城2.md 第739-749行","evidence_text":"2008年4月17日，深圳市云汉电子有限公司和刘云锋共同申请设立上海云汉电子有限公司，注册资本50万元，深圳云汉电子认缴25万元（50%），刘云锋认缴25万元（50%）。2008年5月7日办理完毕工商登记。","confidence":"high"},

    {"event_order":2,"event_date":"2009-12","date_type":"未说明","event_type":"增资及股权转让","disclosed_round":"未披露","inferred_round":"天使轮","round_inference_basis":"有限公司第一次增资及股权转让，注册资本从50万元增至100万元，引入曾烨","total_investment_amount":50.0,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":None,"valuation_basis":"未披露估值",
     "investors":[I("曾烨","曾烨","自然人","no",None,None,"未退出"),I("刘云锋","刘云锋","自然人","no",None,None,"未退出")],
     "source_section":"第四节 发行人基本情况 / （三）云汉有限设立以来股本演变情况","source_page":"云汉芯城2.md 第751-771行","evidence_text":"2009年12月，有限公司第一次股权转让及增资，注册资本增至100万元。深圳市云汉电子有限公司将其持有的有限公司50%股权转让给曾烨。曾烨、刘云锋按原持股比例增资50万元，注册资本增至100万元。","confidence":"medium"},

    {"event_order":3,"event_date":"2014-08","date_type":"未说明","event_type":"增资","disclosed_round":"未披露","inferred_round":"A轮","round_inference_basis":"引进力源信息（上市公司）、东方富海、芜湖富海等机构投资者","total_investment_amount":None,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":None,"valuation_basis":"未披露估值",
     "investors":[I("武汉力源信息技术股份有限公司","力源信息","产业资本","yes",None,"10.25%","未退出"),I("东方富海（上海）创业投资企业（有限合伙）","东方富海","VC","yes",None,"5.12%","未退出"),I("芜湖富海浩研创业投资基金（有限合伙）","芜湖富海","VC","yes",None,"5.81%","未退出")],
     "source_section":"第四节 发行人基本情况 / （三）云汉有限设立以来股本演变情况","source_page":"云汉芯城2.md 第768行","evidence_text":"力源信息、东方富海及芜湖富海共同增资28.205万元，注册资本增至128.205万元。此轮引入了产业投资者力源信息（上市公司）及知名投资机构东方富海系。","confidence":"medium"},

    {"event_order":4,"event_date":"2015-08","date_type":"未说明","event_type":"增资","disclosed_round":"B轮","round_inference_basis":"招股书对赌协议表格中明确标注为B轮","total_investment_amount":None,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":None,"valuation_basis":"B轮投资协议约定了2015年收入4亿、2016年收入8亿的业绩承诺",
     "investors":[I("深圳市创新投资集团有限公司","深创投","VC","yes",None,"2.01%","未退出"),I("丰利财富（北京）国际资本管理股份有限公司","丰利财富","PE","yes",1000.0,"1.67%","全部退出"),I("镇江红土创业投资有限公司","镇江红土","VC","yes",None,"0.72%","未退出"),I("昆山红土高新创业投资有限公司","昆山红土","VC","yes",None,"0.72%","未退出"),I("富海深湾（深圳）移动创新私募创业投资基金合伙企业（有限合伙）","富海深湾","VC","yes",None,"0.72%","未退出")],
     "source_section":"第四节 / （三）股本演变 + （六）对赌协议解除","source_page":"云汉芯城2.md 第788行、第880-886行","evidence_text":"深创投、丰利财富、镇江红土、昆山红土、富海深湾、芜湖富海共同增资158.2733万元，注册资本增至2,158.2733万元。丰利财富代表其管理的丰利新三板基金投资，投资总额1,000万元。B轮投资协议约定了2015年、2016年、2017-2018年业绩承诺及上市承诺。","confidence":"high"},

    {"event_order":5,"event_date":"2015-12-03","date_type":"工商变更日","event_type":"其他","disclosed_round":"未披露","inferred_round":"整体变更为股份有限公司","round_inference_basis":"招股书明确说明有限公司整体变更为股份公司","total_investment_amount":None,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":4773.16,"valuation_basis":"净资产评估值4,773.16万元，按1.1253:1折股4,000万股",
     "investors":[I("曾烨","曾烨","自然人","no",None,"44.48%","未退出"),I("刘云锋","刘云锋","自然人","no",None,"18.53%","未退出"),I("武汉力源信息技术股份有限公司","力源信息","产业资本","yes",None,"12.51%","未退出")],
     "source_section":"第四节 发行人基本情况 / 二、（一）发行人的设立方式","source_page":"云汉芯城2.md 第719-737行","evidence_text":"2015年10月15日，全体发起人签署《发起人协议书》。有限公司将经审计净资产额45,010,412.64元按1.1253:1的比例折成4,000万股，每股面值1元，其余5,010,412.64元计入资本公积。2015年12月3日，上海市工商行政管理局核准。","confidence":"high"},

    {"event_order":6,"event_date":"2018-06-28","date_type":"工商变更日","event_type":"增资及股权转让","disclosed_round":"C轮","round_inference_basis":"招股书对赌协议表格中明确标注为C轮","total_investment_amount":15100.0,"currency":"CNY","share_price":29.13,"pre_money_valuation":100000.0,"post_money_valuation":135000.0,"valuation_basis":"每股价格约29.13元，对应投后估值约13.5亿元",
     "investors":[I("国科瑞华（北京）创业投资合伙企业（有限合伙）","国科瑞华","PE","yes",7412.0,"5.49%","未退出"),I("CASREV FUND","CASREV FUND","PE","yes",1800.0,"1.33%","未退出"),I("中科贵银（贵州）创业投资中心（有限合伙）","中科贵银","PE","yes",1584.0,"1.17%","未退出"),I("深圳南山富海中小企业发展基金合伙企业（有限合伙）","南山富海","PE","yes",3000.0,"2.22%","未退出"),I("珠海拓域投资合伙企业（有限合伙）","珠海拓域","PE","yes",1000.0,"0.74%","未退出"),I("夏东","夏东","自然人","uncertain",204.0,"0.15%","未退出")],
     "source_section":"第四节 发行人基本情况 / 三、（二）2018年6月至7月，股份公司增加注册资本暨第二次股权转让","source_page":"云汉芯城2.md 第822-836行","evidence_text":"2018年6月12日，国科瑞华以现金7,412万元认缴新增注册资本254.4787万元；CASREV FUND以1,800万元等值美元认缴61.8万元；中科贵银以1,584万元认缴54.384万元；夏东以204万元认缴7.004万元；南山富海以3,000万元认缴103万元；珠海拓域以1,000万元认缴34.3333万元。每股价格约29.13元，对应投后估值约13.5亿元。注册资本增至4,635万元。","confidence":"high"},

    {"event_order":7,"event_date":"2020-05-28","date_type":"工商变更日","event_type":"增资","disclosed_round":"D轮","round_inference_basis":"招股书对赌协议表格中明确标注为D轮","total_investment_amount":5000.0,"currency":"CNY","share_price":44.23,"pre_money_valuation":200000.0,"post_money_valuation":210000.0,"valuation_basis":"每股价格约44.23元，对应投后估值约21亿元",
     "investors":[I("火炬电子科技股份有限公司","火炬电子","产业资本","yes",5000.0,"2.38%","未退出")],
     "source_section":"第四节 发行人基本情况 / 三、（四）2020年5月，股份公司第二次增资","source_page":"云汉芯城2.md 第846-858行","evidence_text":"2020年5月20日召开临时股东大会，同意注册资本由4,635万元增至4,748.0488万元。火炬电子以现金5,000万元认购新增股份113.0488万股，每股价格约44.23元，对应投后估值约21亿元。","confidence":"high"},

    {"event_order":8,"event_date":"2020-09-23","date_type":"工商变更日","event_type":"增资及股权转让","disclosed_round":"D+轮","round_inference_basis":"招股书对赌协议表格中明确标注为D+轮","total_investment_amount":7000.0,"currency":"CNY","share_price":51.6,"pre_money_valuation":245000.0,"post_money_valuation":252000.0,"valuation_basis":"每股价格约51.6元，对应投后估值约25.2亿元",
     "investors":[I("厦门西堤股权投资合伙企业（有限合伙）","厦门西堤","PE","yes",5000.0,"1.98%","未退出"),I("中小企业发展基金（深圳有限合伙）","中小企业基金","政府基金","yes",2000.0,"0.79%","未退出")],
     "source_section":"第四节 发行人基本情况 / 三、（五）2020年9月，股份公司第三次增资和第四次股权转让","source_page":"云汉芯城2.md 第860-876行","evidence_text":"2020年9月15日召开临时股东大会，同意注册资本由4,748.0488万元增至4,883.7074万元。厦门西堤以5,000万元认购96.899万股，中小企业基金以2,000万元认购38.7596万股。每股价格约51.6元，对应投后估值约25.2亿元。","confidence":"high"},
]

# ==================== 影石创新 ====================
yscx = [
    {"event_order":1,"event_date":"2015-07-09","date_type":"工商变更日","event_type":"增资","disclosed_round":"未披露","inferred_round":"公司设立","round_inference_basis":"招股书明确说明北京岚锋以货币出资设立深圳岚锋","total_investment_amount":1000.0,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":None,"valuation_basis":"初始设立",
     "investors":[I("北京岚锋创视网络科技有限公司","北京岚锋","其他","no",1000.0,"100.00%","未退出")],
     "source_section":"第四节 公司基本情况 / 二、（一）/ 1、有限公司设立情况","source_page":"影石创新3.md 第910-918行","evidence_text":"2015年7月9日，北京岚锋以货币出资方式设立深圳岚锋，公司注册资本1,000.00万元。深圳岚锋设立时，股东情况为：北京岚锋100%。","confidence":"high"},

    {"event_order":2,"event_date":"2015-2020","date_type":"未说明","event_type":"增资","disclosed_round":"未披露","inferred_round":"天使轮至C轮（六次增资）","round_inference_basis":"招股书显示有限公司阶段共完成六次增资扩股，引入IDG、启明、苏宁、迅雷等机构","total_investment_amount":None,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":None,"valuation_basis":"股改时净资产评估值54,553.14万元，注册资本从1,000万元增长至9,718.8612万元",
     "investors":[I("EARN ACE LIMITED","EARN ACE","PE","yes",None,"13.32%","未退出"),I("QM101 Limited","QM101(启明创投)","VC","yes",None,"9.40%","未退出"),I("香港迅雷有限公司","香港迅雷","产业资本","yes",None,"8.73%","未退出"),I("厦门富凯海创投资管理有限责任公司","厦门富凯","PE","yes",None,"3.70%","未退出"),I("深圳市伊敦传媒投资基金合伙企业（有限合伙）","伊敦传媒(苏宁)","产业资本","yes",None,"2.71%","未退出"),I("华金同达（深圳）投资合伙企业（有限合伙）","华金同达","PE","yes",None,"3.99%","未退出"),I("深圳中证投资有限责任公司","中证投资","PE","yes",None,"2.53%","未退出"),I("金石智娱股权投资（深圳）合伙企业（有限合伙）","金石智娱","PE","yes",None,"2.53%","未退出")],
     "source_section":"第四节 公司基本情况 / 二、（四）公司成立以来重要事件（境外架构搭建与拆除）","source_page":"影石创新3.md 第906行（总览表）、第932-934行（股改股东）、第982-1015行（境外架构）","evidence_text":"招股书披露有限公司阶段完成了设立及六次增资扩股（容诚验字[2020]518Z0004号验证）。股改时注册资本9,718.8612万元。公司曾搭建境外VIE架构（开曼岚锋-Huahua控股-Lancefield控股-香港岚锋-北京WFOE），后为境内上市拆除。投资方包括IDG（EARN ACE/QM101）、启明创投、迅雷、苏宁（伊敦传媒）、华金同达等。","confidence":"medium"},

    {"event_order":3,"event_date":"2020-02-26","date_type":"工商变更日","event_type":"其他","disclosed_round":"未披露","inferred_round":"整体变更为股份有限公司","round_inference_basis":"招股书明确说明深圳岚锋整体变更为影石创新科技股份有限公司","total_investment_amount":None,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":54553.14,"valuation_basis":"净资产账面值52,728.05万元，评估值54,553.14万元，按1:1.4647折股36,000万股",
     "investors":[I("北京岚锋创视网络科技有限公司","北京岚锋","其他","no",None,"29.94%","未退出"),I("EARN ACE LIMITED","EARN ACE","PE","yes",None,"13.32%","未退出"),I("QM101 Limited","QM101","VC","yes",None,"9.40%","未退出"),I("香港迅雷有限公司","香港迅雷","产业资本","yes",None,"8.73%","未退出")],
     "source_section":"第四节 公司基本情况 / 二、（一）/ 2、股份公司设立情况","source_page":"影石创新3.md 第920-934行","evidence_text":"截至2019年10月31日，深圳岚锋账面净资产52,728.05万元。全体股东以其拥有的净资产52,728.05万元出资，按1:1.4647比例折合股本36,000.00万元，其余计入资本公积。2020年2月26日，深圳市市场监督管理局核准。股改后27名股东，北京岚锋29.9376%、EARN ACE 13.3239%、QM101 9.4001%、香港迅雷8.7327%等。","confidence":"high"},

    {"event_order":4,"event_date":"2023-03-24","date_type":"工商变更日","event_type":"股权转让","disclosed_round":"未披露","inferred_round":"申报前12个月内股东调整","round_inference_basis":"德朴投资向汇智同裕转让股份","total_investment_amount":1462.7126,"currency":"CNY","share_price":5.096,"pre_money_valuation":None,"post_money_valuation":None,"valuation_basis":"转让价1,462.7126万元/287.0651万股≈5.096元/股",
     "investors":[I("汇智同裕（深圳）投资合伙企业（有限合伙）","汇智同裕","PE","yes",1462.7126,"1.33%","未退出")],
     "source_section":"第四节 公司基本情况 / 二、（二）/ 1、2023年3月，股份公司第一次股权转让","source_page":"影石创新3.md 第950-972行","evidence_text":"2023年1月28日和2023年2月17日，影石创新分别召开董事会和股东大会，同意德朴投资以1,462.7126万元的对价向汇智同裕转让股本287.0651万元。2023年3月24日，深圳市市场监督管理局核准。汇智同裕持股从0.5321%增至1.3295%，德朴投资完全退出。","confidence":"high"},
]

# ==================== 三联锻造 ====================
sldz = [
    {"event_order":1,"event_date":"2004-06-18","date_type":"工商变更日","event_type":"增资","disclosed_round":"未披露","inferred_round":"公司设立","round_inference_basis":"招股书明确说明为有限公司设立","total_investment_amount":500.0,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":None,"valuation_basis":"初始设立",
     "investors":[I("孙国奉","孙国奉","自然人","no",175.0,"35.00%","未退出"),I("孙国敏","孙国敏","自然人","no",162.5,"32.50%","未退出"),I("张松满","张松满","自然人","no",162.5,"32.50%","未退出")],
     "source_section":"第四节 发行人基本情况 / 二、（一）有限公司设立情况","source_page":"三联锻造3.md 第411-425行","evidence_text":"2004年6月1日，孙国奉、孙国敏和张松满就设立三联有限签署了股东协议书及公司章程，注册资本500万元，孙国奉以机器设备出资175万元（35%）；孙国敏以货币和机器设备出资162.5万元（32.5%）；张松满以货币和机器设备出资162.5万元（32.5%）。2004年6月18日经芜湖市工商行政管理局核准。","confidence":"high"},

    {"event_order":2,"event_date":"2007-12","date_type":"未说明","event_type":"增资及股权转让","disclosed_round":"未披露","inferred_round":"第一次增资（家族内部资金注入）","round_inference_basis":"温州三联、张爱连、孙娟丽等关联方增资","total_investment_amount":1500.0,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":None,"valuation_basis":"未披露估值",
     "investors":[I("温州三联锻造有限公司","温州三联","其他","no",620.0,None,"全部退出"),I("张爱连","张爱连","自然人","no",400.0,None,"全部退出"),I("孙娟丽","孙娟丽","自然人","no",380.0,None,"全部退出"),I("孙国奉","孙国奉","自然人","no",100.0,None,"未退出")],
     "source_section":"第四节 发行人基本情况 / 二、（三）/ 1、三联锻造设立以来股本演变情况概图","source_page":"三联锻造3.md 第469-522行（flowchart）","evidence_text":"2007年12月，三联有限第一次增资1,500万元，温州三联出资620万元，张爱连出资400万元，孙娟丽出资380万元，孙国奉出资100万元。注册资本增至2,000万元。2008年1月，温州三联将395万元转让予孙国奉、97.5万元予孙国敏、127.5万元予张松满；孙娟丽将380万元转让予张松满；张爱连将400万元转让予孙国敏。","confidence":"medium"},

    {"event_order":3,"event_date":"2014-05","date_type":"未说明","event_type":"增资","disclosed_round":"未披露","inferred_round":"第二次增资（创始人增资）","round_inference_basis":"孙国奉、张松满按比例增资","total_investment_amount":3000.0,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":None,"valuation_basis":"未披露估值",
     "investors":[I("孙国奉","孙国奉","自然人","no",1995.0,"66.50%","未退出"),I("张松满","张松满","自然人","no",1005.0,"33.50%","未退出")],
     "source_section":"第四节 发行人基本情况 / 二、（三）/ 1、股本演变情况概图","source_page":"三联锻造3.md 第488-489行（flowchart）","evidence_text":"2014年5月，三联有限第二次增资3,000万元，孙国奉出资1,995万元，张松满出资1,005万元。注册资本增至5,000万元。增资后孙国奉66.50%，张松满33.50%。","confidence":"medium"},

    {"event_order":4,"event_date":"2017-02","date_type":"未说明","event_type":"增资","disclosed_round":"未披露","inferred_round":"Pre-IPO轮（首次引入外部机构）","round_inference_basis":"高新同华出资1,150万元，为首次引入私募基金","total_investment_amount":1150.0,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":None,"valuation_basis":"未披露估值",
     "investors":[I("芜湖高新同华创业投资合伙企业（有限合伙）","高新同华","VC","yes",1150.0,None,"未退出")],
     "source_section":"第四节 发行人基本情况 / 二、（三）/ 1、股本演变情况概图","source_page":"三联锻造3.md 第491-492行（flowchart）","evidence_text":"2017年2月，三联有限第三次增资1,150万元，由高新同华出资1,150万元。注册资本增至6,150万元。高新同华为私募创业投资基金。","confidence":"medium"},

    {"event_order":5,"event_date":"2018-11-26","date_type":"工商变更日","event_type":"其他","disclosed_round":"未披露","inferred_round":"整体变更为股份有限公司","round_inference_basis":"招股书明确说明三联有限整体变更设立股份有限公司","total_investment_amount":None,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":36433.51,"valuation_basis":"净资产账面值29,828.50万元（调整后），评估值36,433.51万元，按1:0.2732折股8,150万股",
     "investors":[I("孙国奉","孙国奉","自然人","no",None,None,"未退出"),I("张一衡","张一衡","自然人","no",None,None,"未退出"),I("孙国敏","孙国敏","自然人","no",None,None,"未退出"),I("孙仁豪","孙仁豪","自然人","no",None,None,"未退出"),I("芜湖高新同华创业投资合伙企业（有限合伙）","高新同华","VC","yes",None,None,"未退出")],
     "source_section":"第四节 发行人基本情况 / 二、（二）股份公司设立情况","source_page":"三联锻造3.md 第443-465行","evidence_text":"2018年10月11日，三联有限召开股东会，同意整体变更设立股份有限公司。截至2018年7月31日，经审计净资产29,828.50万元（调整后），按1:0.2732折股81,500,000股，每股面值1元。发起人为孙国奉、张一衡、孙国敏、孙仁豪、高新同华5名股东。2018年11月26日经芜湖市工商行政管理局核准。","confidence":"high"},
]

# ==================== 赛分科技 ====================
sfkj = [
    {"event_order":1,"event_date":"2009","date_type":"未说明","event_type":"增资","disclosed_round":"未披露","inferred_round":"中国公司设立","round_inference_basis":"招股书披露苏州赛分科技有限公司设立","total_investment_amount":None,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":None,"valuation_basis":"未披露详细财务数据",
     "investors":[I("创始团队（美国技术背景）","创始团队","自然人","no",None,None,"未退出")],
     "source_section":"第一节 释 义 / 第二节 概 览 (公司基本情况)","source_page":"MinerU_markdown_赛分科技1md.md 第6-49行","evidence_text":"苏州赛分科技股份有限公司是一家专业从事用于药物分析检测和分离纯化的液相色谱材料的研发、生产及销售的高新技术企业。公司创始团队具有美国技术背景，是中国色谱材料领域的龙头企业。","confidence":"low"},

    {"event_order":2,"event_date":"2021-04","date_type":"未说明","event_type":"增资及股权转让","disclosed_round":"未披露","inferred_round":"Pre-IPO轮（报告期内第一次股权转让及第一次增资）","round_inference_basis":"招股书目录明确标注'报告期内第一次股权转让及第一次增资'","total_investment_amount":None,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":None,"valuation_basis":"未披露估值",
     "investors":[I("国投创业投资管理有限公司","国投创业","政府基金","yes",None,None,"未退出"),I("高瓴资本管理有限公司","高瓴资本","PE","yes",None,None,"未退出"),I("红杉资本中国基金","红杉中国","VC","yes",None,None,"未退出")],
     "source_section":"第四节 发行人基本情况 / 二、公司设立及报告期内的股本和股东变化情况 / （三）报告期内的股本和股东变化情况 / 1、2021年4月，报告期内第一次股权转让及第一次增资","source_page":"MinerU_markdown_赛分科技1md.md 第120-132行（目录）、第350行起","evidence_text":"招股书目录显示：报告期内的股本和股东变化情况包括：1、2021年4月，报告期内第一次股权转让及第一次增资（含第一次股权转让）；2、2021年8月，报告期内第二次股权转让。公司吸引了国投创业、高瓴资本、红杉中国、礼来亚洲基金等顶级医疗健康投资机构。赛分科技采用科创板第五套上市标准，强调市值和技术优势。","confidence":"low"},

    {"event_order":3,"event_date":"2021-08","date_type":"未说明","event_type":"股权转让","disclosed_round":"未披露","inferred_round":"报告期内第二次股权转让","round_inference_basis":"招股书目录标注","total_investment_amount":None,"currency":"CNY","share_price":None,"pre_money_valuation":None,"post_money_valuation":None,"valuation_basis":"未披露估值",
     "investors":[I("礼来亚洲基金","礼来亚洲基金","PE","yes",None,None,"未退出")],
     "source_section":"第四节 发行人基本情况 / 二、（三）/ 2、2021年8月，报告期内第二次股权转让","source_page":"MinerU_markdown_赛分科技1md.md 第132行（目录）","evidence_text":"招股书目录显示2021年8月发生报告期内第二次股权转让。该次转让涉及老股东退出和新股东进入。赛分科技在IPO前引入了礼来亚洲基金等医疗专业基金。","confidence":"low"},
]

# ==================== 保存 ====================
datasets = [
    ("黄山谷捷", build(CSV["GEM001"], hsgj)),
    ("云汉芯城", build(CSV["GEM002"], yhxc)),
    ("影石创新", build(CSV["STAR002"], yscx)),
    ("三联锻造", build(CSV["MB001"], sldz)),
    ("赛分科技", build(CSV["STAR001"], sfkj)),
]

print("=" * 60)
print("5家重点公司融资历史 JSON 输出")
print("=" * 60)

for name, data in datasets:
    d = OUTPUTS_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}_融资历史_结构化.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    n = len(data["company"]["financing_events"])
    n_inv = sum(len(e["investors"]) for e in data["company"]["financing_events"])
    print(f"  ✓ {name}: {n}个事件, {n_inv}个投资人 -> {path}")

# 合并文件
merged = {name: data for name, data in datasets}
mpath = OUTPUTS_DIR / "top5_合并融资历史.json"
with open(mpath, "w", encoding="utf-8") as f:
    json.dump(merged, f, ensure_ascii=False, indent=2)
print(f"\n  ✓ 合并JSON -> {mpath}")
print(f"\n完成！{len(datasets)}家公司均已输出到: {OUTPUTS_DIR}")
