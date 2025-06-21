# 🍷 Chateau Overdruiven – Wijnclub Webapp

Welkom bij de officiële repository van de Chateau Overdruiven wijnclub!  
Deze Flask-webapplicatie maakt het mogelijk om:

- 👥 Leden te beheren en gebruikersaccounts aan te maken
- 📅 Activiteiten te publiceren en aanmeldingen bij te houden
- 🧾 Betalingen en inschrijvingen (optioneel) te controleren als admin
- 💌 Werken met uitnodigingscodes en rollen (bijv. organisator)

---

## 🚀 Features

- Inloggen en registreren via uitnodigingscode
- Activiteiten aanmaken, bewerken en verwijderen (voor admins/organisatoren)
- Inschrijvingen beheren (met optionele betaling)
- Openbare activiteiten bekijken voor niet-ingelogde bezoekers
- Strakke UI met responsive layout (CSS met custom stijl)

---

## 🛠️ Installatie

1. Clone de repo:
   ```bash
   git clone https://github.com/<jouwgebruikersnaam>/<repo>.git
   cd repo
   ```

2. Maak een virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Installeer dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Voeg een `.env` bestand toe met je configuratie:
   ```ini
   SECRET_KEY=
   GOOGLE_CALENDAR_ID=

   BANK_ACCOUNT_NUMBER=
   BANK_ACCOUNT_NAME=

   MAIL_PASSWORD=
   MAIL_USERNAME=

   ADMIN_EMAIL=
   ```

5. Start de app:
   ```bash
   phyton3 app.py
   ```

---

## ⚠️ Belangrijk

> Bestanden zoals `.env`, wachtwoorden, en persoonlijke gegevens worden **bewust uitgesloten** van deze repo voor veiligheid.  
> Zie `.gitignore` voor een overzicht van uitgesloten mappen en bestanden.

---

## 📄 Licentie

Deze code is uitsluitend bedoeld voor privégebruik binnen de wijnclub.  
Voor andere toepassingen: neem contact op.

---

## 💌 Contact

Voor vragen, aanpassingen of uitbreidingen:  
Stuur een bericht naar de beheerder van deze repo of neem contact op via de clubsite.
