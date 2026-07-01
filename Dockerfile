# ================================
# mallservice-python Dockerfile
# ================================
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        default-libmysqlclient-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 配置日志目录
RUN mkdir -p /var/log/mall

# 指定配置文件的默认路径
ENV MALL_CONF=/app/etc/mall/mall.conf

EXPOSE 8560

# 使用 gunicorn 启动
CMD ["gunicorn", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8560", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info", \
     "wsgi:application"]
