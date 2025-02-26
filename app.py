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
        post_content = f"<p>{content.replace('\n', '<br>')}</p><br>"

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
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    message = value.get("message", "")
                    attachments = value.get("attachments", {}).get("data", [])

                    media_urls = []
                    for media in attachments:
                        media_type = media.get("type", "")
                        media_url = None

                        if media_type == "photo":
                            media_url = media.get("media", {}).get("image", {}).get("src")
                        elif media_type == "video":
                            media_url = media.get("media", {}).get("source")  # Facebook 影片來源 key 為 `source`

                        if media_url:
                            media_urls.append(media_url)

                    if message:
                        title = message.split("\n")[0]  # 第一行作為標題
                        content_lines = message.split("\n")[2:]  # 第三行開始作為內文
                        content = "\n".join(content_lines) if content_lines else message

                        # 處理圖片和影片上傳
                        wp_media_urls = []
                        for url in media_urls:
                            if "jpg" in url or "jpeg" in url or "png" in url:
                                uploaded_url = upload_image_to_wordpress(url)
                            elif "mp4" in url:
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
