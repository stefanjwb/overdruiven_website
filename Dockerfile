FROM python:3.10-slim

# Zet werkdirectory
WORKDIR /app

# Kopieer projectbestanden
COPY . .

# Installeer Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Zet environment variabelen voor Flask
ENV FLASK_RUN_HOST=0.0.0.0

# Start de app
CMD ["flask", "run"]
