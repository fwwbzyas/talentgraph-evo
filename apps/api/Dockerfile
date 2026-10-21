FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY requirements.txt /app/requirements.txt
RUN printf '%s\n' \
        'Types: deb' \
        'URIs: https://mirrors.aliyun.com/debian' \
        'Suites: trixie trixie-updates' \
        'Components: main' \
        'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
        '' \
        'Types: deb' \
        'URIs: https://mirrors.aliyun.com/debian-security' \
        'Suites: trixie-security' \
        'Components: main' \
        'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
        > /etc/apt/sources.list.d/debian.sources \
    && printf '%s\n' \
        'Acquire::Retries "5";' \
        'Acquire::http::Timeout "30";' \
        'Acquire::https::Timeout "30";' \
        > /etc/apt/apt.conf.d/80-retries \
    && apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-cjk fonts-arphic-uming \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --timeout 120 --retries 8 --index-url https://mirrors.aliyun.com/pypi/simple \
        https://mirrors.aliyun.com/pytorch-wheels/cpu/torch-2.5.1%2Bcpu-cp312-cp312-linux_x86_64.whl \
        https://mirrors.aliyun.com/pytorch-wheels/cpu/torchaudio-2.5.1%2Bcpu-cp312-cp312-linux_x86_64.whl \
    && pip install --no-cache-dir --timeout 120 --retries 8 --index-url https://mirrors.aliyun.com/pypi/simple -r /app/requirements.txt
ENV PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=120000
RUN python -m playwright install-deps chromium
RUN python -m playwright install chromium
COPY agents /app/agents
COPY apps /app/apps
COPY contracts /app/contracts
COPY core /app/core

ENV PYTHONPATH=/app
ENV TALENTGRAPH_ZHAOPIN_BROWSER_CHANNEL=""
ENV TALENTGRAPH_ZHAOPIN_HEADLESS=1
EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
