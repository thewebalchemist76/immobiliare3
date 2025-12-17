FROM apify/actor-python-playwright:3.11

# Installa Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 🔧 Fix librerie Debian per Playwright Chromium
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        fonts-liberation \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libatspi2.0-0 \
        libcairo-gobject2 \
        libcairo2 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libexpat1 \
        libgbm1 \
        libglib2.0-0 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libstdc++6 \
        libx11-6 \
        libx11-xcb1 \
        libxcb1 \
        libxcomposite1 \
        libxcursor1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxi6 \
        libxrandr2 \
        libxrender1 \
        libxss1 \
        libxtst6 \
        lsb-release \
        wget \
        xdg-utils \
        fonts-unifont \
    && rm -rf /var/lib/apt/lists/*

# 🔧 Installa Chromium Playwright
RUN playwright install chromium

# Copia codice
COPY src ./src

# Entry point
CMD ["python", "-m", "src.main"]
