"""
北京小学择校日报收集器 v3（Server酱推送）
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


def generate_daily_report(all_results):
    today_str = date.today().strftime("%Y年%m月%d日")
    combined = "\n\n".join(all_results)
    return f"""📚 择校情报日报
{today_str}

{'─' * 30}

{combined}

{'─' * 30}
📌 数据来源：Gemini AI + Google Search
🔄 下次更新：明日早8:00
"""


def send_report(content, title):
    if not SENDKEY:
        print("⚠️  Server酱未配置，内容打印如下：")
        print(content)
        return
    try:
        resp = httpx.post(
            f"https://sctapi.ftqq.com/{SENDKEY}.send",
            data={"title": title, "desp": content},
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
    all_results = []

    for i in range(0, len(SCHOOLS), BATCH_SIZE):
        batch = SCHOOLS[i: i + BATCH_SIZE]
        print(f"🔍 正在搜索第{i//BATCH_SIZE+1}批：{', '.join(batch)}")
        try:
            result = search_school_news(client, batch)
            all_results.append(result)
            print(f"   ✓ 完成")
        except Exception as e:
            print(f"   ❌ 搜索失败：{e}")
            all_results.append(f"【搜索失败】{', '.join(batch)}")

    print("\n📝 正在生成日报...")
    report = generate_daily_report(all_results)

    os.makedirs("reports", exist_ok=True)
    filename = f"reports/daily_{date.today().strftime('%Y%m%d')}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"📄 已保存：{filename}")

    today_str = date.today().strftime("%m/%d")
    send_report(report, f"📚 择校日报 {today_str}")

    print(f"\n✅ 全部完成 {datetime.now().strftime('%H:%M:%S')}\n")


if __name__ == "__main__":
    run()
