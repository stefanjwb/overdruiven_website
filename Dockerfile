# Gebruik een officiële, lichtgewicht Python image als basis
FROM python:3.9-slim-buster

# Stel de werkdirectory in de container in
WORKDIR /app

# Kopieer eerst het requirements-bestand en installeer de dependencies
# Dit maakt gebruik van Docker's layer caching. Als de requirements niet wijzigen,
# wordt deze stap overgeslagen, wat het bouwen versnelt.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopieer de rest van de applicatiecode naar de werkdirectory
COPY . .

# De poort waarop Gunicorn zal draaien binnen de container
EXPOSE 5000

# Belangrijk: Het .env bestand en de instance folder worden NIET meegekopieerd.
# Deze worden via docker-compose.yml als 'volumes' gekoppeld, zodat ze buiten
# de container blijven bestaan en niet bij elke build worden overschreven.