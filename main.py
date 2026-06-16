import os
import sys
import json
import time
from curl_cffi import requests as curl_requests

# ==========================================
# 用户配置（请修改 ITEM_IDS）
# ==========================================
CONFIG = {
    "ITEM_IDS": ['ZHONA296297', 'ZHONA307715', 'ZHONA292019'],  # ← 改成你的商品编号
    "TO_EMAIL": os.environ.get('TO_EMAIL', '2799313501@qq.com'),
    "RESEND_API_KEY": os.environ.get('RESEND_API_KEY', 're_Y6jiGVfy_CrrjD6kZKoeDX4e81jAXoWow'),
    "FROM_EMAIL": 'Suruga-ya Monitor <onboarding@resend.dev>',
    # 手动提供的 cf_clearance（通过 GitHub Secrets 传入）
    "CF_CLEARANCE": os.environ.get('CF_CLEARANCE', ''),
}

# ==========================================
# 方法 1：curl_cffi 直接调用 API（最快）
# ==========================================
def try_curl_cffi_direct(item_id):
    print("   📡 [方法1] curl_cffi 直连...")
    session = curl_requests.Session(impersonate="chrome120")
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
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✅ 直连成功！返回: {json.dumps(data, ensure_ascii=False)}")
            return (data and data != {} and data != [])
        elif resp.status_code == 403:
            print("   ❌ 直连 403")
            return None
        else:
            print(f"   ❌ 状态码 {resp.status_code}")
            return None
    except Exception as e:
        print(f"   ❌ 异常: {e}")
        return None

# ==========================================
# 方法 2：使用手动 Cookie（完整或单独）
# ==========================================
def try_with_manual_cookie(item_id):
    raw_cookie = CONFIG.get("CF_CLEARANCE", "")
    if not raw_cookie or len(raw_cookie) < 20:
        print("   ⚠️ [方法2] 未配置 CF_CLEARANCE")
        return None

    print("   🍪 [方法2] 使用手动 cookie...")
    session = curl_requests.Session(impersonate="chrome120")

    # 解析 cookie 字符串（可能是一整串 key=value; key=value ...）
    if '=' in raw_cookie and (';' in raw_cookie or 'cf_clearance' in raw_cookie):
        # 当作完整 cookie 字符串处理
        pairs = raw_cookie.split(';')
        for pair in pairs:
            pair = pair.strip()
            if '=' in pair:
                key, value = pair.split('=', 1)
                session.cookies.set(key.strip(), value.strip(), domain="www.suruga-ya.jp")
                print(f"   🍪 加载 cookie: {key.strip()} = {value.strip()[:30]}...")
    else:
        # 单个 cf_clearance 值
        session.cookies.set("cf_clearance", raw_cookie, domain="www.suruga-ya.jp")
        print(f"   🍪 加载单个 cf_clearance")

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
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✅ cookie 有效！返回: {json.dumps(data, ensure_ascii=False)}")
            return (data and data != {} and data != [])
        elif resp.status_code == 403:
            print("   ❌ cookie 过期（403）")
            return None
        else:
            print(f"   ❌ 状态码 {resp.status_code}")
            return None
    except Exception as e:
        print(f"   ❌ 异常: {e}")
        return None

# ==========================================
# 方法 3：Playwright + stealth 自动获取 Cookie
# ==========================================
def try_playwright_stealth(item_id):
    print("   🌐 [方法3] Playwright+stealth 自动过 Cloudflare...")
    try:
        from playwright.sync_api import sync_playwright
        from playwright_stealth import stealth_sync
    except ImportError:
        print("   ❌ playwright-stealth 未安装")
        return None

    cookies = None
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-blink-features=AutomationControlled',
                  '--disable-dev-shm-usage', '--disable-gpu']
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        page = context.new_page()
        stealth_sync(page)  # 关键：隐藏自动化特征
        try:
            url = f"https://www.suruga-ya.jp/product/detail/{item_id}"
            print(f"   🔗 访问 {url} ...")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            print(f"   📄 页面标题：{page.title()}")
            # 等待 Cloudflare 挑战完成（最长25秒）
            try:
                page.wait_for_function(
                    """() => !document.title.includes('稍等') &&
                              !document.title.includes('Just a moment')""",
                    timeout=25000
                )
                print(f"   ✅ 页面标题变为：{page.title()}")
            except Exception:
                print(f"   ⚠️ 等待超时，当前标题: {page.title()}")
            time.sleep(3)
            cookies = context.cookies()
            print(f"   🍪 获取到 {len(cookies)} 个 cookie")
            for c in cookies:
                if 'cf_' in c['name']:
                    print(f"      -> {c['name']}: {c['value'][:40]}...")
        except Exception as e:
            print(f"   ❌ 浏览器异常: {e}")
        finally:
            browser.close()
    return cookies

def check_with_playwright_cookies(item_id, cookies):
    if not cookies: return None
    session = curl_requests.Session(impersonate="chrome120")
    for c in cookies:
        session.cookies.set(c['name'], c['value'], domain=c.get('domain', 'www.suruga-ya.jp'))
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
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✅ API 返回: {json.dumps(data, ensure_ascii=False)}")
            return (data and data != {} and data != [])
        else:
            print(f"   ❌ 状态码 {resp.status_code}")
            return None
    except Exception as e:
        print(f"   ❌ 异常: {e}")
        return None

# ==========================================
# 发送邮件
# ==========================================
def send_email(subject, body):
    api_key = CONFIG["RESEND_API_KEY"]
    if not api_key or 'YOUR_API_KEY' in api_key:
        print("❌ Resend API Key 未配置")
        return False
    try:
        resp = curl_requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"from": CONFIG["FROM_EMAIL"], "to": [CONFIG["TO_EMAIL"]],
                  "subject": subject, "html": body.replace('\n', '<br>')},
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
# 主流程：按优先级依次尝试
# ==========================================
def check_item(item_id):
    print(f"\n{'='*50}\n🕵️ 检查: {item_id}\n{'='*50}")
    # 方法1
    result = try_curl_cffi_direct(item_id)
    if result is not None: return result
    # 方法2
    result = try_with_manual_cookie(item_id)
    if result is not None: return result
    # 方法3
    print("   ↪️ 前两种方法失败，启动浏览器...")
    cookies = try_playwright_stealth(item_id)
    if cookies and any('cf_clearance' in c['name'] for c in cookies):
        result = check_with_playwright_cookies(item_id, cookies)
        if result is not None: return result
    print(f"   ❌ 所有方法均失败！")
    return None

if __name__ == "__main__":
    print("=" * 50)
    print("  骏河屋监控 v3（三层递进式）")
    print("=" * 50)
    for item_id in CONFIG["ITEM_IDS"]:
        result = check_item(item_id)
        if result is True:
            print(f"   🎉🎉🎉 有货！")
            send_email(
                f"🎉 骏河屋有货 - {item_id}",
                f"""<h3>🎉 商品补货！</h3><p><strong>编号：</strong>{item_id}</p>
                <p><a href="https://www.suruga-ya.jp/product/detail/{item_id}">👉 点此立即购买</a></p>
                <p><small>（每约2分钟自动检测一次）</small></p>"""
            )
        elif result is False:
            print(f"   ➖ 暂无货")
        else:
            print(f"   ❓ 检测失败")
        time.sleep(2)
    print("\n✅ 本轮完成")
