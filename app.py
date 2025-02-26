import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Facebook & WordPress API 設定
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")  # Facebook Page Access Token
WP_URL = os.getenv("WP_URL")  # WordPress 網址
WP_USERNAME = os.getenv("WP_USERNAME")  # WordPress 使用者名稱
WP_PASSWORD = os.getenv("WP_PASSWORD")  # WordPress 應用程式密碼

# WordPress 上傳圖片
def upload_to_wordpress(image_url):
    image_data = requests.get(image_url).content
    filename = f"fb_image_{int(os.times()[4])}.jpg"
    media_endpoint = f"{WP_URL}/wp-json/wp/v2/media"

    headers = {
        "Authorization": f"Basic {requests.auth._basic_auth_str(WP_USERNAME, WP_PASSWORD)}",
        "Content-Disposition": f"attachment; filename={filename}",
        "Content-Type": "image/jpeg",
    }
    
    response = requests.post(media_endpoint, headers=headers, files={"file": image_data})
    if response.status_code == 201:
        return response.json()["source_url"]
    return None

# 發佈文章
def create_wordpress_post(title, content, media_urls):
    post_content = f"{content}<br><br>"
    for media_url in media_urls:
        post_content += f'<img src="{media_url}" /><br>'
    
    post_data = {
        "title": title,
        "content": post_content,
        "status": "publish"
    }

    headers = {
        "Authorization": f"Basic {requests.auth._basic_auth_str(WP_USERNAME, WP_PASSWORD)}",
        "Content-Type": "application/json",
    }
    
    response = requests.post(f"{WP_URL}/wp-json/wp/v2/posts", json=post_data, headers=headers)
    return response.status_code == 201

# Webhook 接收 Facebook 貼文
@app.route("/webhook", methods=["POST"])
def facebook_webhook():
    data = request.json

    # 確認事件是來自粉絲專頁貼文
    if "entry" in data:
        for entry in data["entry"]:
            for post in entry.get("changes", []):
                if "value" in post and "message" in post["value"]:
                    message = post["value"]["message"]
                    media_urls = [media["media"]["image"]["src"] for media in post["value"].get("attachments", []) if "image" in media["media"]]

                    title = message.split("\n")[0]  # 第一行作為標題
                    content = "\n".join(message.split("\n")[2:])  # 第三行開始作為內文

                    wp_media_urls = [upload_to_wordpress(url) for url in media_urls if upload_to_wordpress(url)]
                    create_wordpress_post(title, content, wp_media_urls)

    return jsonify({"status": "ok"}), 200

# Facebook Webhook 驗證
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    VERIFY_TOKEN = "my_secure_token"
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "Invalid verification token", 403

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
