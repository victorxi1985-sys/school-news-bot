"""
北京小学择校日报收集器 v4（HTML格式推送）
"""

import os
import httpx
import time
from datetime import date, datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SENDKEY        = os.getenv("SENDKEY")

SCHOOLS = [
    "人朝分实验学校小学部",
    "世青国际学校小学部",
    "启明星双语学校",
    "赫德学校 HD Beijing",
    "鼎石学校 Keystone",
    "北京乐成国际学校 BCIS",
    "北京私立汇佳学校",
    "君诚国际双语学校 SIBS",
    "海嘉国际双语学校 BIBA",
    "顺义区诺德安达学校",
]

BATCH_SIZE = 3


def search_school_news(client, schools, retries=3):
    today_str = date.today().strftime("%Y年%m月%d日")
    schools_str = "、".join(schools)
    prompt = f"""
今天是 {today_str}。请搜索以下北京小学的最新动态，重点关注2026年信息：
{schools_str}

每所学校整理：招生政策变化、开放日时间、学费调整、师资变动、家长评价、升学成绩。
没有新消息的标注"暂无新动态"，重大变化用【重要】标注，每校不超过150字，注明来源和时间。

请严格按以下JSON格式输出，不要有任何其他文字：
{{
  "schools": [
    {{
      "name": "学校名称",
      "news": "动态内容",
      "important": true或false
    }}
  ]
}}
"""
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.3,
                ),
            )
            return response.text
        except Exception as e:
            if "503" in str(e) and attempt < retries - 1:
                wait = (attempt + 1) * 10
                print(f"   ⏳ 服务器繁忙，{wait}秒后重试（第{attempt+1}次）...")
                time.sleep(wait)
            else:
                raise e


def parse_results(raw_results):
    """解析JSON结果，失败则降级为纯文本"""
    import json, re
    schools = []
    for raw in raw_results:
        try:
            clean = re.sub(r"```json|```", "", raw).strip()
            data = json.loads(clean)
            schools.extend(data.get("schools", []))
        except Exception:
            # 解析失败，作为纯文本整段加入
            schools.append({"name": "综合动态", "news": raw, "important": False})
    return schools


def generate_html_report(schools_data):
    today_str = date.today().strftime("%Y年%m月%d日")
    weekdays = {"Monday":"周一","Tuesday":"周二","Wednesday":"周三",
                "Thursday":"周四","Friday":"周五","Saturday":"周六","Sunday":"周日"}
    weekday = weekdays.get(datetime.now().strftime("%A"), "")

    cards_html = ""
    for s in schools_data:
        name = s.get("name", "")
        news = s.get("news", "").replace("\n", "<br>")
        important = s.get("important", False)
        border_color = "#e74c3c" if important else "#3498db"
        tag = '<span style="background:#e74c3c;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;margin-left:8px;">重要</span>' if important else ""
        cards_html += f"""
<div style="background:#fff;border-radius:10px;padding:16px;margin-bottom:12px;border-left:4px solid {border_color};box-shadow:0 1px 4px rgba(0,0,0,0.08);">
  <div style="font-size:17px;font-weight:bold;color:#2c3e50;margin-bottom:8px;">{name}{tag}</div>
  <div style="font-size:15px;color:#555;line-height:1.8;">{news}</div>
</div>
"""

    html = f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;background:#f4f6f9;padding:16px;max-width:600px;margin:0 auto;">

  <div style="background:linear-gradient(135deg,#2E75B6,#1a5c96);border-radius:12px;padding:20px;margin-bottom:16px;color:#fff;text-align:center;">
    <div style="font-size:22px;font-weight:bold;">📚 择校情报日报</div>
    <div style="font-size:13px;margin-top:6px;opacity:0.9;">{today_str} {weekday}</div>
    <div style="font-size:12px;margin-top:4px;opacity:0.7;">共 {len(schools_data)} 所学校</div>
  </div>

  {cards_html}

  <div style="text-align:center;font-size:11px;color:#999;margin-top:16px;padding-top:12px;border-top:1px solid #e0e0e0;">
    📌 数据来源：Gemini AI + Google Search 实时搜索<br>
    🔄 下次更新：明日早8:00
  </div>

</div>
"""
    return html


def send_report(html_content, title):
    if not SENDKEY:
        print("⚠️  Server酱未配置")
        return
    try:
        desp = "点击查看今日动态 👉 [每日日报](https://victorxi1985-sys.github.io/school-news-bot/)\n\n点击查看学校全面对比 👉 [学校对比表](https://victorxi1985-sys.github.io/school-news-bot/compare.html)"
        resp = httpx.post(
            f"https://sctapi.ftqq.com/{SENDKEY}.send",
            data={"title": title, "desp": desp},
            timeout=15,
        )
        result = resp.json()
        if result.get("code") == 0:
            print("✅ 微信推送成功")
        else:
            print(f"❌ 推送失败：{result}")
    except Exception as e:
        print(f"❌ 推送异常：{e}")




def generate_compare_html():
    from datetime import date
    today = date.today().strftime("%Y年%m月%d日")
    schools = [
        {"name":"启明星双语学校","addr":"朝阳区北皋/三里屯","curriculum":"IB+国家课程","fee":"10-14万","entry":"✅无国籍限制，面试+MAP测试","atm":"green","atm_text":"极度温馨，品格教育，压力小","faculty":"40%硕博，中外教均衡","pro":"氛围温暖，性价比最高，首届高中15人获154份录取","con":"学术竞争感相对弱","news":"2026年1月/3月已开放日，小学23.1-23.4万/年","openday":"每月1-2次，微信：启明星学校","score":5,"suggest":"强烈推荐！性价比最高的IB学校"},
        {"name":"海嘉国际双语学校BIBA","addr":"顺义区天竺","curriculum":"IB全程+A-Level双轨","fee":"18-29万","entry":"✅非京籍友好，1年级须综合评估","atm":"green","atm_text":"最温馨，民主课堂，师生关系融洽","faculty":"中外教1:1，平均教龄12年，80%硕士","pro":"民主课堂，非京籍经验丰富，2026届获约翰霍普金斯等录取","con":"顺义通勤较远","news":"2026年5月17日开放日，小学约26万/年，师生比1:3","openday":"5月17日/10-11月，微信：BIBA海嘉","score":5,"suggest":"强烈推荐！氛围最好，非京籍友好"},
        {"name":"君诚国际双语学校SIBS","addr":"顺义区","curriculum":"IB全程，美式创新","fee":"15-26万","entry":"✅非京籍友好，英文口语评估","atm":"green","atm_text":"务实低调，家长口碑一致好评","faculty":"师生比1:5，平均教龄超8年，60%硕士以上","pro":"师生比1:5极佳，2026届62人获500+录取，奖学金超1600万美元","con":"顺义位置，市区通勤较远","news":"小学20万/年，5月23日参加北京择校展，已获德语官方考点授权","openday":"每两周周三定期，admissions@sibs.com.cn","score":5,"suggest":"强烈推荐！顺义最被低估的学校"},
        {"name":"北京乐成国际学校BCIS","addr":"朝阳区CBD","curriculum":"IB全程PYP/MYP/DP","fee":"22-34.9万","entry":"✅无国籍限制，申请费3000元","atm":"yellow","atm_text":"中规中矩，换校长后管理趋紧","faculty":"IB认证师资，老牌经验丰富","pro":"CBD通勤最方便，IB全程，老牌口碑","con":"换校长后家校沟通争议","news":"2026-27招生开放，小学29.8万/年，4月24日发布录取结果","openday":"11月全校开放日，bcis.cn","score":4,"suggest":"朝阳CBD最便利的IB选项"},
        {"name":"北京私立汇佳学校","addr":"昌平区（位置偏远）","curriculum":"IB全程，北京最早IB学校","fee":"11-25万","entry":"✅无国籍限制，春季可插班","atm":"yellow","atm_text":"老牌低调，近年学术导向增强","faculty":"30年IB经验，新校长杨承（耶鲁背景）","pro":"IB经验最丰富，2025届获普林斯顿/耶鲁/康奈尔/牛津","con":"昌平位置偏远","news":"新校长杨承上任，春季插班名额开放","openday":"2026年2月/4月/5月，hjs.com.cn","score":4,"suggest":"IB经验最深厚，适合不在意通勤的家庭"},
        {"name":"赫德学校HD Beijing","addr":"朝阳区金盏","curriculum":"⚠️小学非IB认证，自研双语，高中IBDP","fee":"20-30万","entry":"✅无国籍限制，家长面试+能动性考察","atm":"green","atm_text":"创新开放，全球化视野","faculty":"国际化背景，双语跨学科","pro":"项目式学习，大语文+逻辑强，不刷题","con":"小学非IB PYP认证，学校相对年轻","news":"2026年5月15日开放日，小学24.8万，高中27.8-29.8万","openday":"全年多次，微信：北京赫德","score":4,"suggest":"理念契合AI时代，但小学非IB认证"},
        {"name":"世青国际学校小学部","addr":"朝阳区亮马桥/望京","curriculum":"⚠️小学IPC（非IB PYP），初中IBMYP，高中IBDP","fee":"16-26万","entry":"✅无国籍限制，笔试+面试，须1.5年评估报告","atm":"green","atm_text":"学术自由，培养思考者，25国学生在校","faculty":"国际认证，经验丰富","pro":"学风自由，超1500名毕业生入牛津/布朗/康奈尔","con":"小学IPC非IB PYP，硬件略简朴，需孩子自律","news":"2026秋招开启，小学25.5-26万/年","openday":"预约探校，mission@bwya.cn","score":4,"suggest":"适合注重思辨且孩子自律的家庭"},
        {"name":"顺义区诺德安达学校","addr":"顺义区","curriculum":"小学自研双语，高中IBDP","fee":"12.8-24.5万","entry":"✅无国籍限制，G1融合班12.8万","atm":"yellow","atm_text":"全球化氛围，连锁品牌标准化","faculty":"全球诺德安达体系，统一培训","pro":"G1融合班性价比高，2026届全员获TOP100录取","con":"小学非纯IB，连锁标准化","news":"G1融合班12.8万，周一至周五可1v1访校","openday":"周一至周五1v1访校","score":4,"suggest":"G1融合班是低成本试水选项"},
        {"name":"鼎石学校Keystone","addr":"朝阳区/顺义何各庄","curriculum":"IB全程，600+课外活动","fee":"25-38.75万","entry":"✅无国籍限制，申请费2000元不退","atm":"red","atm_text":"⚠️攀比严重，超高净值家庭聚集","faculty":"顶尖师资，但外教流失，2025年管理层大换血","pro":"升学资源顶尖，2025届35%进全球TOP10","con":"攀比严重，外教流失，小学数学弱，管理层动荡","news":"2026学费25-38.75万，新增AI/击剑课程","openday":"9月/11月，申请费2000元","score":3,"suggest":"⚠️不推荐：攀比严重，管理层动荡"},
        {"name":"人朝分实验学校小学部","addr":"朝阳区太阳宫","curriculum":"民办九年一贯，国内课程（非IB）","fee":"5-10万","entry":"⚠️朝阳区摇号，5月报名","atm":"yellow","atm_text":"学风严谨，偏应试","faculty":"人大附中体系，师资共享","pro":"直升初中有保障，中考成绩朝阳第一，性价比最高","con":"非IB，国际化程度低","news":"2025新政：五升六可直升初中","openday":"不定期说明会，010-84296311","score":3,"suggest":"适合走国内高考路线，与国际化目标不符"},
    ]

    def stars(n): return "★"*n + "☆"*(5-n)
    def atm_bg(a): return {"green":"#e8f5e9","yellow":"#fff8e1","red":"#ffebee"}[a]
    def atm_border(a): return {"green":"#4caf50","yellow":"#ff9800","red":"#f44336"}[a]
    def score_color(n):
        if n>=5: return "#1b5e20"
        if n>=4: return "#1565c0"
        return "#e65100"

    cards = ""
    for i,s in enumerate(schools):
        rank = i+1
        badge = ""
        if rank<=3: badge = f'<span style="background:#1b5e20;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;margin-left:6px;">TOP{rank} 强烈推荐</span>'
        elif rank<=6: badge = '<span style="background:#1565c0;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;margin-left:6px;">推荐</span>'
        cards += f"""
<div style="background:#fff;border-radius:12px;padding:18px;margin-bottom:14px;box-shadow:0 2px 8px rgba(0,0,0,0.08);border-top:4px solid {atm_border(s['atm'])};">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;flex-wrap:wrap;gap:6px;">
    <div><span style="font-size:16px;font-weight:bold;color:#1a237e;">#{rank} {s['name']}</span>{badge}</div>
    <div style="font-size:18px;color:{score_color(s['score'])};">{stars(s['score'])}</div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
    <div style="background:#f5f5f5;border-radius:8px;padding:8px;"><div style="font-size:10px;color:#666;">📍地址</div><div style="font-size:12px;">{s['addr']}</div></div>
    <div style="background:#f5f5f5;border-radius:8px;padding:8px;"><div style="font-size:10px;color:#666;">💰学费</div><div style="font-size:12px;font-weight:bold;color:#c62828;">{s['fee']}/年</div></div>
    <div style="background:#f5f5f5;border-radius:8px;padding:8px;"><div style="font-size:10px;color:#666;">📚课程</div><div style="font-size:12px;">{s['curriculum']}</div></div>
    <div style="background:{atm_bg(s['atm'])};border-radius:8px;padding:8px;border-left:3px solid {atm_border(s['atm'])};"><div style="font-size:10px;color:#666;">🌟风气</div><div style="font-size:12px;">{s['atm_text']}</div></div>
  </div>
  <div style="background:#e8f0fe;border-radius:8px;padding:8px;margin-bottom:8px;"><div style="font-size:10px;color:#1565c0;">📋入学要求</div><div style="font-size:12px;">{s['entry']}</div></div>
  <div style="background:#e0f2f1;border-radius:8px;padding:8px;margin-bottom:8px;"><div style="font-size:10px;color:#00695c;">👩‍🏫师资</div><div style="font-size:12px;">{s['faculty']}</div></div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
    <div style="background:#e8f5e9;border-radius:8px;padding:8px;"><div style="font-size:10px;color:#2e7d32;">✅优点</div><div style="font-size:12px;color:#1b5e20;">{s['pro']}</div></div>
    <div style="background:#fff3e0;border-radius:8px;padding:8px;"><div style="font-size:10px;color:#e65100;">⚠️缺点</div><div style="font-size:12px;color:#bf360c;">{s['con']}</div></div>
  </div>
  <div style="background:#fff8e1;border-radius:8px;padding:8px;margin-bottom:8px;border-left:3px solid #ffa000;"><div style="font-size:10px;color:#e65100;">🔥2026最新动态</div><div style="font-size:12px;">{s['news']}</div></div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
    <div style="background:#f3e5f5;border-radius:8px;padding:8px;"><div style="font-size:10px;color:#6a1b9a;">📅开放日</div><div style="font-size:12px;">{s['openday']}</div></div>
    <div style="background:#e8eaf6;border-radius:8px;padding:8px;border-left:3px solid #3949ab;"><div style="font-size:10px;color:#283593;">💡综合建议</div><div style="font-size:12px;font-weight:500;color:#1a237e;">{s['suggest']}</div></div>
  </div>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>北京国际小学全面对比2026</title>
<style>*{{box-sizing:border-box;margin:0;padding:0;}}body{{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;background:#f0f4f8;}}</style>
</head>
<body>
<div style="background:linear-gradient(135deg,#1a237e,#283593);color:#fff;padding:20px 16px;text-align:center;">
  <div style="font-size:20px;font-weight:bold;">🏫 北京国际小学全面对比</div>
  <div style="font-size:12px;opacity:0.8;margin-top:4px;">2026年版 · 共10所学校 · 更新：{today}</div>
</div>
<div style="background:#fff;padding:10px 16px;display:flex;gap:10px;box-shadow:0 1px 4px rgba(0,0,0,0.1);">
  <a href="index.html" style="font-size:13px;color:#1565c0;text-decoration:none;padding:5px 12px;border-radius:16px;border:1px solid #1565c0;">📰每日动态</a>
  <a href="compare.html" style="font-size:13px;color:#fff;text-decoration:none;padding:5px 12px;border-radius:16px;background:#1565c0;">📊学校对比</a>
</div>
<div style="max-width:680px;margin:0 auto;padding:14px;">
  <div style="background:#fff;border-radius:10px;padding:12px;margin-bottom:14px;">
    <div style="font-size:13px;font-weight:bold;color:#1a237e;margin-bottom:8px;">筛选：非京籍·IB体系·探究式·校园风气好</div>
    <div style="display:flex;flex-wrap:wrap;gap:6px;">
      <span style="background:#e8f5e9;color:#1b5e20;padding:3px 8px;border-radius:10px;font-size:11px;">★★★★★ 强烈推荐</span>
      <span style="background:#e3f2fd;color:#1565c0;padding:3px 8px;border-radius:10px;font-size:11px;">★★★★☆ 推荐</span>
      <span style="background:#fff8e1;color:#e65100;padding:3px 8px;border-radius:10px;font-size:11px;">★★★☆☆ 谨慎考虑</span>
    </div>
  </div>
  {cards}
  <div style="text-align:center;font-size:11px;color:#999;padding:16px 0;">📌 Gemini AI + Google Search · {today}</div>
</div>
</body>
</html>"""

def run():
    print(f"\n{'='*50}")
    print(f"🚀 开始收集择校情报 {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*50}\n")

    client = genai.Client(api_key=GEMINI_API_KEY)
    all_raw = []

    for i in range(0, len(SCHOOLS), BATCH_SIZE):
        batch = SCHOOLS[i: i + BATCH_SIZE]
        print(f"🔍 正在搜索第{i//BATCH_SIZE+1}批：{', '.join(batch)}")
        try:
            result = search_school_news(client, batch)
            all_raw.append(result)
            print(f"   ✓ 完成")
        except Exception as e:
            print(f"   ❌ 搜索失败：{e}")
            all_raw.append(f'{{"schools":[{{"name":"搜索失败","news":"{", ".join(batch)} 本批次搜索失败","important":false}}]}}')

    print("\n📝 正在生成日报...")
    schools_data = parse_results(all_raw)
    html = generate_html_report(schools_data)

    # 保存 HTML 本地留档
    os.makedirs("reports", exist_ok=True)
    filename = f"reports/daily_{date.today().strftime('%Y%m%d')}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"📄 已保存：{filename}")

    today_str = date.today().strftime("%m/%d")
    send_report(html, f"📚 择校日报 {today_str} | {len(schools_data)}所学校")

    print(f"\n✅ 全部完成 {datetime.now().strftime('%H:%M:%S')}\n")


if __name__ == "__main__":
    run()
# 此行仅用于触发更新
