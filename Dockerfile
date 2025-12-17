FROM apify/actor-python-playwright:3.11

# Copia requirements
COPY requirements.txt ./

# Installa dipendenze Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia codice
COPY src ./src

# Avvio actor
CMD ["python", "-m", "src.main"]
