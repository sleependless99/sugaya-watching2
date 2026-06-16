import os
import json
import time
from curl_cffi import requests

# --- 配置区 ---
CONFIG = {
    "ITEM_IDS": ['ZHONA296297', 'ZHONA307715', 'ZHONA292019'],  # 改成你的商品编号
    "TO_EMAIL": os.environ.get('TO_EMAIL', '2799313501@qq.com'),
    "RESEND_API_KEY": os.environ.get('RESEND_API_KEY', 're_Y6jiGVfy_CrrjD6kZKoeDX4e81jAXoWow'),
    "FROM_EMAIL": 'Suruga-ya Monitor <onboarding@resend.dev>',
}

# 模拟 Chrome 浏览器的 TLS 指纹
SESSION = requests.Session(impersonate="chrome120")

def send_email(subject, body):
    api_key = CONFIG["RESEND_API_KEY"]
    if not api_key or 'YOUR_API_KEY' in api_key:
        print("❌ Resend API Key 未配置！")
        return False
    try:
        resp = requests.post(
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

def check_stock_via_api(item_id):
    """直接调用 offer_stock API，而非爬取整个页面"""
    api_url = "https://www.suruga-ya.jp/product/detail/offer_stock"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://www.suruga-ya.jp/product/detail/{item_id}",
        "Origin": "https://www.suruga-ya.jp",
    }
    payload = f"shinaban={item_id}&eda=&latitude=&longitude="
    
    try:
        resp = SESSION.post(api_url, headers=headers, data=payload, timeout=20)
        
        if resp.status_code == 403:
            print(f"   ⚠️ 被 Cloudflare 拦截 (403)")
            return None  # None 表示不确定
        
        if resp.status_code != 200:
            print(f"   ⚠️ API 返回异常状态码: {resp.status_code}")
            return None
        
        data = resp.json()
        print(f"   📦 API 返回: {json.dumps(data, ensure_ascii=False)}")
        
        # 判断有货的逻辑：data 不为空对象/空数组
        if data and data != {} and data != []:
            return True
        else:
            return False
            
    except Exception as e:
        print(f"   ❌ API 请求异常: {e}")
        return None

def check_stock_fallback(item_id):
    """备用方案：爬取完整页面，检查按钮"""
    url = f"https://www.suruga-ya.jp/product/detail/{item_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        resp = SESSION.get(url, headers=headers, timeout=20)
        if resp.status_code == 403:
            print(f"   ⚠️ 页面被拦截 (403)")
            return None
        has_stock = 'class="btn_buy btn cart1"' in resp.text
        return has_stock
    except Exception as e:
        print(f"   ❌ 页面请求异常: {e}")
        return None

# --- 主程序 ---
if __name__ == "__main__":
    print("=" * 40)
    print("  骏河屋监控 (curl_cffi + API)")
    print("=" * 40)
    
    for item_id in CONFIG["ITEM_IDS"]:
        print(f"\n🕵️ 检查: {item_id}")
        
        # 优先使用 API（更轻量）
        result = check_stock_via_api(item_id)
        
        # 如果 API 被拦截，回退到页面方案
        if result is None:
            print("   ↪️ 回退到页面检测...")
            result = check_stock_fallback(item_id)
        
        if result is True:
            print(f"   🎉 有货！发送通知...")
            send_email(
                f"🎉 骏河屋有货 - {item_id}",
                f"""
                <h3>商品有货！</h3>
                <p><strong>编号：</strong>{item_id}</p>
                <p><a href="https://www.suruga-ya.jp/product/detail/{item_id}">点击购买</a></p>
                <p><small>（每2分钟提醒一次，直到售罄）</small></p>
                """
            )
        elif result is False:
            print(f"   ➖ 无货")
        else:
            print(f"   ❓ 无法确定（可能被拦截）")
        
        time.sleep(3)
    
    print("\n✅ 本轮完成")
