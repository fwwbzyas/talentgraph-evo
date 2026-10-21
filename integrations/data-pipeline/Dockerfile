# 数据采集与清洗流水线 — Docker 镜像
# 基于 python:3.12-slim，体积小，启动快

FROM python:3.12-slim

LABEL maintainer="路z"
LABEL project="揭榜挂帅 XH-202621 — 数据采集与清洗流水线"
LABEL version="1.0.0"

# 设置工作目录
WORKDIR /app

# 安装系统依赖（仅 psycopg2 编译所需，如不用 PostgreSQL 可删除）
RUN apt-get update -y \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY agents/data-pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 PostgreSQL 驱动（可选）
RUN pip install --no-cache-dir psycopg2-binary

# 复制源码
COPY agents/ agents/
COPY config/ config/

# 创建输出和 Cookie 目录
RUN mkdir -p /app/output /app/cookies

# 入口: 交互式采集（docker compose run 时使用）
# 使用绝对路径而非 -m，因为目录名含连字符不符合 Python 包命名规范
ENTRYPOINT ["python", "/app/agents/data-pipeline/main.py"]

# 默认参数可被 docker compose run 覆盖
CMD ["--help"]
