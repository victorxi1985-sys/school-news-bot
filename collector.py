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
  <div style="font-size:15px;font-weight:bold;color:#2c3e50;margin-bottom:8px;">{name}{tag}</div>
  <div style="font-size:13px;color:#555;line-height:1.7;">{news}</div>
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
        desp = "点击查看今日完整择校日报 👉 [择校日报](https://victorxi1985-sys.github.io/school-news-bot/)"
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
