import os
import time
import requests
from flask import Flask, request, jsonify
from requests.auth import HTTPBasicAuth

app = Flask(__name__)

# Facebook & WordPress API 設定
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")  # Facebook Page Access Token
WP_URL = os.getenv("WP_URL")  # WordPress 網址
WP_USERNAME = os.getenv("WP_USERNAME")  # WordPress 使用者名稱
WP_PASSWORD = os.getenv("WP_PASSWORD")  # WordPress 應用程式密碼

# WordPress 上傳圖片
def upload_image_to_wordpress(image_url):
    try:
        image_data = requests.get(image_url).content
        filename = f"fb_image_{int(time.time())}.jpg"
        media_endpoint = f"{WP_URL}/wp-json/wp/v2/media"

        files = {'file': (filename, image_data, 'image/jpeg')}
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
        video_data = requests.get(video_url).content
        filename = f"fb_video_{int(time.time())}.mp4"
        media_endpoint = f"{WP_URL}/wp-json/wp/v2/media"

        files = {'file': (filename, video_data, 'video/mp4')}
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
        post_content = f"{content}<br><br>"
        for media_url in media_urls:
            post_content += f'<img src="{media_url}" /><br>' if media_url else ""

        post_data = {
            "title": title,
            "content": post_content,
            "status": "publish"
        }

        headers = {"Content-Type": "application/json"}
        response = requests.post(f"{WP_URL}/wp-json/wp/v2/posts", json=post_data, auth=HTTPBasicAuth(WP_USERNAME, WP_PASSWORD), headers=headers)

        if response.status_code == 201:
            return response.json()
        else:
            print("Post creation failed:", response.text)
    except Exception as e:
        print("Error creating post:", e)
    return None

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
                        attachments = post["value"].get("attachments", {}).get("data", [])

                        media_urls = []
                        for media in attachments:
                            media_type = media.get("type", "")
                            media_url = media.get("media", {}).get("image", {}).get("src") if media_type == "photo" else \
                                        media.get("media", {}).get("video", {}).get("src") if media_type == "video" else None
                            if media_url:
                                media_urls.append(media_url)

                        title = message.split("\n")[0]  # 第一行作為標題
                        content = "\n".join(message.split("\n")[2:])  # 第三行開始作為內文

                        # 處理圖片和影片上傳
                        wp_media_urls = []
                        for url in media_urls:
                            if url.endswith(".jpg") or url.endswith(".jpeg"):
                                uploaded_url = upload_image_to_wordpress(url)
                            elif url.endswith(".mp4"):
                                uploaded_url = upload_video_to_wordpress(url)
                            else:
                                uploaded_url = None

                            if uploaded_url:
                                wp_media_urls.append(uploaded_url)

                        # 上傳完成後創建文章
                        create_wordpress_post(title, content, wp_media_urls)

        return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
