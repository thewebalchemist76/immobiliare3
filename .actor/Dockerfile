FROM apify/actor-python-playwright:3.11

# Installa Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 🔧 INSTALLA BROWSER Playwright (OBBLIGATORIO)
RUN playwright install --with-deps chromium

# Copia codice
COPY src ./src

# Entry point
CMD ["python", "-m", "src.main"]
