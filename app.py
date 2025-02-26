import os
import time
import aiohttp
import asyncio
from flask import Flask, request, jsonify
from aiohttp import ClientSession
from requests.auth import HTTPBasicAuth

app = Flask(__name__)

# Facebook & WordPress API 設定
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")  # Facebook Page Access Token
WP_URL = os.getenv("WP_URL")  # WordPress 網址
WP_USERNAME = os.getenv("WP_USERNAME")  # WordPress 使用者名稱
WP_PASSWORD = os.getenv("WP_PASSWORD")  # WordPress 應用程式密碼

# WordPress 上傳圖片，使用 aiohttp 進行異步處理
async def upload_to_wordpress(image_url: str, session: ClientSession):
    async with session.get(image_url) as response:
        image_data = await response.read()
        filename = f"fb_image_{int(time.time())}.jpg"
        media_endpoint = f"{WP_URL}/wp-json/wp/v2/media"
        
        headers = {
            "Authorization": HTTPBasicAuth(WP_USERNAME, WP_PASSWORD),
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "image/jpeg",
        }

        data = aiohttp.FormData()
        data.add_field('file', image_data, filename=filename, content_type='image/jpeg')

        async with session.post(media_endpoint, headers=headers, data=data) as post_response:
            if post_response.status == 201:
                return await post_response.json()
            return None

# 發佈文章，使用 aiohttp 進行異步處理
async def create_wordpress_post(title: str, content: str, media_urls: list, session: ClientSession):
    post_content = f"{content}<br><br>"
    for media_url in media_urls:
        post_content += f'<img src="{media_url}" /><br>'
    
    post_data = {
        "title": title,
        "content": post_content,
        "status": "publish"
    }

    headers = {
        "Authorization": HTTPBasicAuth(WP_USERNAME, WP_PASSWORD),
        "Content-Type": "application/json",
    }

    async with session.post(f"{WP_URL}/wp-json/wp/v2/posts", json=post_data, headers=headers) as response:
        return response.status == 201

# Webhook 接收 Facebook 貼文
@app.route("/webhook", methods=["GET", "POST"])
async def facebook_webhook():
    if request.method == "GET":
        # Facebook webhook 驗證
        VERIFY_TOKEN = "my_secure_token"
        if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Invalid verification token", 403

    if request.method == "POST":
        # 接收 Facebook 貼文並處理
        data = request.json
        if "entry" in data:
            async with aiohttp.ClientSession() as session:
                for entry in data["entry"]:
                    for post in entry.get("changes", []):
                        if "value" in post and "message" in post["value"]:
                            message = post["value"]["message"]
                            media_urls = [media["media"]["image"]["src"] for media in post["value"].get("attachments", []) if "image" in media["media"]] + \
                                         [media["media"]["video"]["src"] for media in post["value"].get("attachments", []) if "video" in media["media"]]
                            
                            title = message.split("\n")[0]  # 第一行作為標題
                            content = "\n".join(message.split("\n")[2:])  # 第三行開始作為內文

                            wp_media_urls = []
                            for url in media_urls:
                                wp_media_url = await upload_to_wordpress(url, session)
                                if wp_media_url:
                                    wp_media_urls.append(wp_media_url["source_url"])
                            
                            await create_wordpress_post(title, content, wp_media_urls, session)

        return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
