FROM python:3.11-slim

# Flet web mode に必要なライブラリ
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgl1 \
    libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8550

# Flet をウェブモードで起動
CMD ["flet", "run", "--web", "--port", "8550", "main.py"]
