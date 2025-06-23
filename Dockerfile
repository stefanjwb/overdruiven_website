# Gebruik een efficiënte en stabiele Python-versie als basis
FROM python:3.10-slim

# Zet de werkmap in de container
WORKDIR /app

# Kopieer EERST de requirements. Dit versnelt het bouwproces bij codewijzigingen
COPY requirements.txt requirements.txt

# Installeer de Python-pakketten
RUN pip install --no-cache-dir -r requirements.txt

# Kopieer de rest van de applicatiecode (app.py, static, templates, etc.)
COPY . .

# Vertel Docker welke poort de applicatie intern gebruikt
EXPOSE 5000

# Start de applicatie met Gunicorn, een productie-waardige server
# --workers 4: Start 4 processen om meerdere bezoekers tegelijk aan te kunnen
# --bind 0.0.0.0:5000: Luister op poort 5000, toegankelijk van buiten de container
# wsgi:app: Vertelt Gunicorn om de 'app' variabele te vinden in het 'wsgi.py' bestand
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "wsgi:app"]