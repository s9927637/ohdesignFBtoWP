import os
import time
import requests
from flask import Flask, request, jsonify
from requests.auth import HTTPBasicAuth
import logging  # 確保有引入 logging 以便於記錄

app = Flask(__name__)

# Facebook & WordPress API 設定
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")  # Facebook Page Access Token
WP_URL = os.getenv("WP_URL")  # WordPress 網址
WP_USERNAME = os.getenv("WP_USERNAME")  # WordPress 使用者名稱
WP_PASSWORD = os.getenv("WP_PASSWORD")  # WordPress 應用程式密碼

# WordPress 上傳圖片
def upload_image_to_wordpress(image_url):
    try:
        response = requests.get(image_url)
        if response.status_code != 200:
            print(f"Failed to fetch image: {image_url}")
            return None

        filename = f"fb_image_{int(time.time())}.jpg"
        media_endpoint = f"{WP_URL}/wp-json/wp/v2/media"

        files = {'file': (filename, response.content, 'image/jpeg')}
        response = requests.post(media_endpoint, auth=HTTPBasicAuth(WP_USERNAME, WP_PASSWORD), files=files)

        if response.status_code == 201:
            return response.json().get("source_url")
        else:
            print("Image upload failed:", response.text)
    except Exception as e:
        print("Error uploading image:", e)
    return None

# WordPress 上傳影片
def upload_video_to_wordpress(video_url):
    try:
        response = requests.get(video_url)
        if response.status_code != 200:
            print(f"Failed to fetch video: {video_url}")
            return None

        filename = f"fb_video_{int(time.time())}.mp4"
        media_endpoint = f"{WP_URL}/wp-json/wp/v2/media"

        files = {'file': (filename, response.content, 'video/mp4')}
        response = requests.post(media_endpoint, auth=HTTPBasicAuth(WP_USERNAME, WP_PASSWORD), files=files)

        if response.status_code == 201:
            return response.json().get("source_url")
        else:
            print("Video upload failed:", response.text)
    except Exception as e:
        print("Error uploading video:", e)
    return None

# 發佈文章
def create_wordpress_post(title, content, media_urls):
    try:
        # 格式化內文
        formatted_content = content.replace('\n', '<br>')

        post_content = f"<p>{formatted_content}</p><br>"

        # 處理媒體
        for media_url in media_urls:
            if media_url.endswith(".jpg") or media_url.endswith(".png"):
                post_content += f'<img src="{media_url}" style="max-width:100%;" /><br>'
            elif media_url.endswith(".mp4"):
                post_content += f'<video controls style="max-width:100%;"><source src="{media_url}" type="video/mp4"></video><br>'

        post_data = {
            "title": title,
            "content": post_content,
            "status": "publish"
        }

        headers = {"Content-Type": "application/json"}
        response = requests.post(f"{WP_URL}/wp-json/wp/v2/posts", json=post_data, auth=HTTPBasicAuth(WP_USERNAME, WP_PASSWORD), headers=headers)

        if response.status_code == 201:
            print(f"Post created: {response.json().get('link')}")
            return response.json()
        else:
            print("Post creation failed:", response.text)
    except Exception as e:
        print("Error creating post:", e)
    return None

# 驗證 Webhook 的 token
VERIFY_TOKEN = "my_secure_token"  # 這個 token 需要與 Facebook 開發者頁面中的設定一致

@app.route("/webhook", methods=["GET", "POST"])
def verify_webhook():
    if request.method == "GET":
        # 記錄請求參數
        app.logger.info(f"Request args: {request.args}")
        
        verify_token = "my_secure_token"
        hub_mode = request.args.get("hub.mode")
        hub_challenge = request.args.get("hub.challenge")
        hub_verify_token = request.args.get("hub.verify_token")

        if hub_mode == "subscribe" and hub_verify_token == verify_token:
            return str(hub_challenge)  # 返回挑戰碼
        else:
            return "Verification failed", 403

    elif request.method == "POST":
        data = request.json
        # 處理 POST 請求
        app.logger.info(f"Received POST data: {data}")
        return "Event received", 200


# Webhook 接收 Facebook 貼文
@app.route("/webhook", methods=["POST"])
def facebook_webhook():
    try:
        data = request.json
        logging.info(f"Received Webhook Data: {data}")  # 日誌記錄接收到的數據

        if not data or "entry" not in data:
            logging.warning("Invalid Webhook data received")  # 如果數據無效，記錄警告
            return jsonify({"status": "error", "message": "Invalid data"}), 400

        for entry in data["entry"]:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                message = value.get("message", "")
                attachments = value.get("attachments", {}).get("data", [])

                if not message:
                    logging.warning("No message found in Webhook data")  # 如果沒有消息，記錄警告
                    continue

                logging.info(f"Processing Facebook post: {message}")  # 打印處理的貼文

                # 圖片 / 影片處理
                media_urls = []
                for media in attachments:
                    if media.get("type") == "photo":
                        media_url = media.get("media", {}).get("image", {}).get("src")
                    else:
                        media_url = media.get("media", {}).get("source")

                    if media_url:
                        logging.info(f"Media found: {media_url}")  # 打印媒體鏈接
                        media_urls.append(media_url)
                
                # 解析標題 & 內文
                title = message.split("\n")[0]  # 第一行為標題
                content = "\n".join(message.split("\n")[2:]) if len(message.split("\n")) > 2 else message  # 從第三行開始為內文

                # 發送至 WordPress
                wp_media_urls = [upload_image_to_wordpress(url) if "jpg" in url or "png" in url else upload_video_to_wordpress(url) for url in media_urls]
                wp_media_urls = list(filter(None, wp_media_urls))  # 移除 `None` 值

                # 創建 WordPress 文章
                create_wordpress_post(title, content, wp_media_urls)

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logging.error(f"Error processing Webhook: {str(e)}", exc_info=True)  # 錯誤日誌
        return jsonify({"status": "error", "message": "Internal server error"}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))  # 默認端口為 5000，如果未設置環境變數
    app.run(host="0.0.0.0", port=port)  # 確保監聽所有地址
