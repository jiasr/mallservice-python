# ================================
# mallservice-python Dockerfile
# ================================
FROM python:3.9-slim

# 使用阿里云镜像源加速
ARG DEBIAN_FRONTEND=noninteractive

# 替换 apt 源为阿里云镜像（兼容 sources.list 和 debian.sources 两种格式）
RUN if [ -f /etc/apt/sources.list ]; then \
        sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list; \
        sed -i 's/security.debian.org/mirrors.aliyun.com\/debian-security/g' /etc/apt/sources.list; \
    fi \
    && if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources; \
        sed -i 's/security.debian.org/mirrors.aliyun.com\/debian-security/g' /etc/apt/sources.list.d/debian.sources; \
    fi \
    && apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        default-libmysqlclient-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 配置 pip 源为阿里云镜像
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip config set global.trusted-host mirrors.aliyun.com

WORKDIR /app

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
