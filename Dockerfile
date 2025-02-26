# 使用 Python 3.10 作為基礎映像
FROM python:3.10

# 設定工作目錄
WORKDIR /app

# 複製本地的 requirements.txt 文件到容器中
COPY requirements.txt /app/

# 安裝依賴（這樣可以利用 Docker 的層緩存，減少不必要的重建）
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式代碼到容器中
COPY . /app/

# 啟動 Flask 服務
CMD ["python", "app.py"]

# 開放應用程序運行的端口
EXPOSE 5000
