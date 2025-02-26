import os
import time
import requests
from flask import Flask, request, jsonify
from requests.auth import HTTPBasicAuth
import aiohttp
import asyncio

app = Flask(__name__)

# Facebook & WordPress API 設定
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")  # Facebook Page Access Token
WP_URL = os.getenv("WP_URL")  # WordPress 網址
WP_USERNAME = os.getenv("WP_USERNAME")  # WordPress 使用者名稱
WP_PASSWORD = os.getenv("WP_PASSWORD")  # WordPress 應用程式密碼

# WordPress 上傳圖片
def upload_to_wordpress(image_url):
    image_data = requests.get(image_url).content
    filename = f"fb_image_{int(time.time())}.jpg"
    media_endpoint = f"{WP_URL}/wp-json/wp/v2/media"

    headers = {
        "Authorization": HTTPBasicAuth(WP_USERNAME, WP_PASSWORD),
        "Content-Disposition": f"attachment; filename={filename}",
        "Content-Type": "image/jpeg",
    }
    
    files = {'file': (filename, image_data, 'image/jpeg')}
    response = requests.post(media_endpoint, headers=headers, files=files)
    if response.status_code == 201:
        return response.json()["source_url"]
    return None

# WordPress 上傳影片
async def upload_video_to_wordpress(session, video_url):
    try:
        async with session.get(video_url) as response:
            video_data = await response.read()
            filename = f"fb_video_{int(time.time())}.mp4"  # 給影片一個唯一的文件名
            media_endpoint = f"{WP_URL}/wp-json/wp/v2/media"

            headers = {
                "Authorization": HTTPBasicAuth(WP_USERNAME, WP_PASSWORD),
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "video/mp4",
            }

            data = {'file': (filename, video_data, 'video/mp4')}
            async with session.post(media_endpoint, headers=headers, files=data) as resp:
                if resp.status == 201:
                    return await resp.json()
                return None
    except Exception as e:
        print(f"Error uploading video: {e}")
        return None

# 異步處理媒體上傳
async def upload_media(media_urls, media_type="image"):
    async with aiohttp.ClientSession() as session:
        tasks = []
        if media_type == "image":
            tasks = [upload_to_wordpress(url) for url in media_urls]
        elif media_type == "video":
            tasks = [upload_video_to_wordpress(session, url) for url in media_urls]
        return await asyncio.gather(*tasks)

# 發佈 WordPress 文章
def create_wordpress_post(title, content, media_urls, video_urls):
    post_content = f"{content}<br><br>"
    
    # 插入圖片
    for media_url in media_urls:
        post_content += f'<img src="{media_url}" /><br>'
    
    # 插入影片
    for video_url in video_urls:
        post_content += f'<iframe width="560" height="315" src="{video_url}" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe><br>'
    
    post_data = {
        "title": title,
        "content": post_content,
        "status": "publish"
    }

    headers = {
        "Authorization": HTTPBasicAuth(WP_USERNAME, WP_PASSWORD),
        "Content-Type": "application/json",
    }

    # 發送請求創建 WordPress 文章
    response = requests.post(f"{WP_URL}/wp-json/wp/v2/posts", json=post_data, headers=headers)
    return response.status_code == 201

# Webhook 接收 Facebook 貼文
@app.route("/webhook", methods=["GET", "POST"])
def facebook_webhook():
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
            for entry in data["entry"]:
                for post in entry.get("changes", []):
                    if "value" in post and "message" in post["value"]:
                        message = post["value"]["message"]
                        media_urls = [media["media"]["image"]["src"] for media in post["value"].get("attachments", []) if "image" in media["media"]]
                        video_urls = [media["media"]["video"]["src"] for media in post["value"].get("attachments", []) if "video" in media["media"]]
                        
                        # 提取標題與內容
                        title = message.split("\n")[0]  # 第一行作為標題
                        content = "\n".join(message.split("\n")[2:])  # 第三行開始作為內文

                        # 上傳圖片與影片
                        uploaded_media_urls = await upload_media(media_urls, media_type="image")
                        uploaded_video_urls = await upload_media(video_urls, media_type="video")

                        # 創建 WordPress 文章
                        create_wordpress_post(title, content, uploaded_media_urls, uploaded_video_urls)

        return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
