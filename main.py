import os
import time
import requests
import cloudscraper

# --- 1. 用户配置区 (在这里修改成您自己的信息) ---
CONFIG = {
    # 【必填】要监控的商品编号列表，用英文逗号隔开
    "ITEM_IDS": ['ZHONA296297', 'ZHONA307715', 'ZHONA292019'],

    # 【必填】接收通知的邮箱地址
    "TO_EMAIL": os.environ.get('TO_EMAIL', 'your_email@example.com'),

    # 【必填】Resend API 密钥，我们会通过环境变量传入
    "RESEND_API_KEY": os.environ.get('RESEND_API_KEY', 're_YOUR_API_KEY'),

    # 监控间隔时间（秒），建议120秒（2分钟）或以上
    "CHECK_INTERVAL_SECONDS": 120,

    # (无需修改) 其他配置
    "IN_STOCK_KEYWORD": 'class="btn_buy btn cart1"', # 有货按钮的特征
    "FROM_EMAIL": 'Koyeb Monitor <onboarding@resend.dev>', # Resend 默认发件人
}

# --- 2. 核心功能 (无需修改) ---
# 简单记录状态，重启后会重置，但能防止短时间内重复发邮件
item_status_memory = {}

def send_email(subject, body):
    print(f"🚀 准备发送邮件: {subject}")
    api_key = CONFIG["RESEND_API_KEY"]
    if not api_key or 'YOUR_API_KEY' in api_key:
        print("❌ 错误：Resend API 密钥未配置！")
        return

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": CONFIG["FROM_EMAIL"],
                "to": [CONFIG["TO_EMAIL"]],
                "subject": subject,
                "html": body.replace('\n', '<br>'),
            },
            timeout=10
        )
        if response.status_code == 200:
            print("✅ 邮件发送成功!")
        else:
            print(f"❌ 邮件发送失败! 状态码: {response.status_code}, 内容: {response.text}")
    except Exception as e:
        print(f"❌ 调用Resend API时发生异常: {e}")

def check_stock(scraper, item_id):
    product_url = f"https://www.suruga-ya.jp/product/detail/{item_id}"
    print(f"\n🕵️‍♂️ 正在检查: {item_id} | URL: {product_url}")
    try:
        content = scraper.get(product_url, timeout=30).text
        has_stock = CONFIG["IN_STOCK_KEYWORD"] in content
        
        if has_stock:
            print(f"   ✅ 状态: 有货!")
        else:
            print(f"   ➖ 状态: 无货。")
        
        return has_stock
    except Exception as e:
        print(f"   ❌ 检查商品 {item_id} 时发生错误: {e}")
        return False

# --- 3. 主程序入口 (无需修改) ---
if __name__ == "__main__":
    print("===================================")
    print("   骏河屋监控程序启动！")
    print("===================================")
    
    scraper = cloudscraper.create_scraper() # 创建一个智能抓取器实例

    while True:
        print(f"\n--- 开始新一轮检查 (共 {len(CONFIG['ITEM_IDS'])} 个商品) ---")
        for item_id in CONFIG["ITEM_IDS"]:
            is_in_stock = check_stock(scraper, item_id)
            last_status = item_status_memory.get(item_id, 'outofstock')
            
            if is_in_stock and last_status != 'instock':
                print(f"🎉🎉🎉 发现补货: {item_id}！准备发送通知...")
                mail_subject = f"🎉 骏河屋有货！- {item_id}"
                mail_body = f"""
                <h3>🎉 商品有货提醒！</h3>
                <p><strong>商品编号：</strong> {item_id}</p>
                <p><strong>购买链接：</strong> <a href="https://www.suruga-ya.jp/product/detail/{item_id}">https://www.suruga-ya.jp/product/detail/{item_id}</a></p>
                <p>请尽快前往购买！</p>
                """
                send_email(mail_subject, mail_body)
                item_status_memory[item_id] = 'instock' # 更新内存状态为“已通知”
            elif not is_in_stock and last_status == 'instock':
                print(f"📦 商品已售罄: {item_id}。状态重置。")
                item_status_memory[item_id] = 'outofstock' # 重置状态，以便下次补货时通知
            
            time.sleep(5) # 在检查每个商品之间稍微停顿一下，模仿人类行为

        print(f"\n✅ 本轮检查完成。等待 {CONFIG['CHECK_INTERVAL_SECONDS']} 秒后进行下一轮...")
        time.sleep(CONFIG['CHECK_INTERVAL_SECONDS'])
