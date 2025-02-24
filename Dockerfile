# 使用 Python 3.10
FROM python:3.10

# 設定工作目錄
WORKDIR /app

# 複製程式碼
COPY . /app

# 安裝依賴
RUN pip install --no-cache-dir flask requests

# 啟動 Flask 服務
CMD ["python", "app.py"]
