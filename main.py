import os
import sys
import json
import time
import tempfile
from curl_cffi import requests as curl_requests
from playwright.sync_api import sync_playwright

# ==========================================
# 用户配置区（请修改这里）
# ==========================================
CONFIG = {
    # 要监控的商品编号（请换成您自己的）
    "ITEM_IDS": ['ZHONA296297', 'ZHONA307715', 'ZHONA292019'],

    # 以下内容通过 GitHub Secrets 自动填入，不用改
    "TO_EMAIL": os.environ.get('TO_EMAIL', '2799313501@qq.com'),
    "RESEND_API_KEY": os.environ.get('RESEND_API_KEY', 're_Y6jiGVfy_CrrjD6kZKoeDX4e81jAXoWow'),
    "FROM_EMAIL": 'Suruga-ya Monitor <onboarding@resend.dev>',
}

# ==========================================
# 1. 自动获取 cf_clearance cookie
# ==========================================
def get_cf_clearance():
    """
    启动无头 Chrome 浏览器，访问骏河屋，自动通过 Cloudflare 验证，
    然后返回包含 cf_clearance 在内的所有 cookie。
    """
    print("🚀 正在启动浏览器，自动获取 Cloudflare 通行证...")
    cookies = None
    with sync_playwright() as p:
        # 启动 Chrome（headless 模式，GitHub Actions 里没有显示器）
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        try:
            # 随便访问一个商品页面（只是为了触发 Cloudflare 验证）
            test_url = "https://www.suruga-ya.jp/product/detail/ZHONA296297"
            print(f"   🔗 访问 {test_url} ...")
            page.goto(test_url, wait_until="domcontentloaded", timeout=30000)
            
            # 等待 Cloudflare 验证完成（如果有的话）
            # 这里给足时间，让 Cloudflare 的脚本跑完
            print("   ⏳ 等待 Cloudflare 验证...")
            time.sleep(10)  # 10 秒通常足够
            
            # 提取所有 cookie
            cookies = context.cookies()
            print(f"   ✅ 成功获取到 {len(cookies)} 个 cookie")
            for c in cookies:
                if 'cf_' in c['name']:
                    print(f"      -> {c['name']}: {c['value'][:30]}...")
        except Exception as e:
            print(f"   ❌ 浏览器操作失败: {e}")
        finally:
            browser.close()
    
    return cookies

def apply_cookies_to_session(session, cookies):
    """将 Playwright 获取的 cookie 应用到 curl_cffi 的 session 中"""
    if not cookies:
        return
    for c in cookies:
        session.cookies.set(c['name'], c['value'], domain=c.get('domain', ''))
    print("   🍪 Cookie 已注入到请求会话")

# ==========================================
# 2. 发送邮件通知
# ==========================================
def send_email(subject, body):
    api_key = CONFIG["RESEND_API_KEY"]
    if not api_key or 'YOUR_API_KEY' in api_key:
        print("❌ Resend API Key 未配置！")
        return False
    try:
        resp = curl_requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "from": CONFIG["FROM_EMAIL"],
                "to": [CONFIG["TO_EMAIL"]],
                "subject": subject,
                "html": body.replace('\n', '<br>'),
            },
            timeout=15
        )
        if resp.status_code == 200:
            print("✅ 邮件发送成功!")
            return True
        else:
            print(f"❌ 邮件失败: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False

# ==========================================
# 3. 检查库存（使用已注入 cookie 的 session）
# ==========================================
def check_stock_via_api(session, item_id):
    """调用 offer_stock 接口，判断是否有货"""
    api_url = "https://www.suruga-ya.jp/product/detail/offer_stock"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://www.suruga-ya.jp/product/detail/{item_id}",
        "Origin": "https://www.suruga-ya.jp",
    }
    payload = f"shinaban={item_id}&eda=&latitude=&longitude="

    try:
        resp = session.post(api_url, headers=headers, data=payload, timeout=20)
        
        if resp.status_code == 403:
            print(f"   ⚠️ 请求被拒 (403) — cookie 可能过期了")
            return None
        
        if resp.status_code != 200:
            print(f"   ⚠️ API 返回 {resp.status_code}")
            return None

        data = resp.json()
        print(f"   📦 API 返回: {json.dumps(data, ensure_ascii=False)}")
        
        # 有货的逻辑：返回的 JSON 不是空对象/空数组
        if data and data != {} and data != []:
            return True
        else:
            return False

    except Exception as e:
        print(f"   ❌ API 请求异常: {e}")
        return None

# ==========================================
# 4. 主流程
# ==========================================
if __name__ == "__main__":
    print("=" * 50)
    print("  骏河屋监控 (全自动 Cloudflare 绕过版)")
    print("=" * 50)

    # --- 第一步：自动获取 cf_clearance ---
    cookies = get_cf_clearance()
    if not cookies:
        print("❌ 未能获取 Cloudflare cookie，程序终止。")
        sys.exit(1)

    # --- 第二步：创建请求会话，注入 cookie ---
    session = curl_requests.Session(impersonate="chrome120")
    apply_cookies_to_session(session, cookies)

    # --- 第三步：逐一检查商品库存 ---
    for item_id in CONFIG["ITEM_IDS"]:
        print(f"\n🕵️ 检查商品: {item_id}")
        result = check_stock_via_api(session, item_id)

        if result is True:
            print(f"   🎉 有货！立即发送通知...")
            send_email(
                f"🎉 骏河屋有货 - {item_id}",
                f"""
                <h3>🎉 商品补货提醒！</h3>
                <p><strong>商品编号：</strong>{item_id}</p>
                <p><a href="https://www.suruga-ya.jp/product/detail/{item_id}">👉 点此立即前往购买</a></p>
                <p><small>（本邮件由自动监控程序发送，每约2分钟检查一次）</small></p>
                """
            )
        elif result is False:
            print(f"   ➖ 暂未补货")
        else:
            print(f"   ❓ 检测失败（可能是 cookie 被拒）")
        
        time.sleep(2)

    print("\n✅ 本轮检测完成")
