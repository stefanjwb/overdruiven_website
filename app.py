from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import datetime
import os
from flask_mail import Mail, Message
from dotenv import load_dotenv
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import click

# Google API imports
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()

app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///activities.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['BANK_ACCOUNT_NUMBER'] = os.getenv('BANK_ACCOUNT_NUMBER')
app.config['BANK_ACCOUNT_NAME'] = os.getenv('BANK_ACCOUNT_NAME')

app.config['ADMIN_EMAIL'] = os.getenv('ADMIN_EMAIL')

app.config['SERVER_NAME'] = os.getenv('SERVER_NAME')

app.config['MAIL_SERVER'] = 'smtp.gmail.com' 
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = ('Chateau Overdruiven', os.getenv('MAIL_USERNAME'))

db = SQLAlchemy(app)
mail = Mail(app)
migrate = Migrate(app, db)

# ... (de rest van je app.py code)

# --- Google Calendar API Configuration ---
SERVICE_ACCOUNT_FILE = 'credentials/service_account.json' 
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = os.getenv('GOOGLE_CALENDAR_ID')

def get_calendar_service():
    """Retrieves the Google Calendar service client."""
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"Error: Service account file not found at '{SERVICE_ACCOUNT_FILE}'")
        raise FileNotFoundError(f"Service account file is missing. Expected at: {SERVICE_ACCOUNT_FILE}")
        
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    return service

# --- Database Models ---
class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(50), nullable=True)
    end_time = db.Column(db.String(50), nullable=True)
    max_participants = db.Column(db.Integer, nullable=True)
    location = db.Column(db.String(200), nullable=True)
    google_event_id = db.Column(db.String(255), nullable=True, unique=True)
    is_public = db.Column(db.Boolean, nullable=False, server_default='0')
    cost = db.Column(db.Float, nullable=True) 
    signups = db.relationship('Signup', backref='activity', lazy=True, cascade="all, delete-orphan")

    @property
    def signups_count(self):
        """Telt het totaal aantal aanmeldingen voor deze activiteit."""
        return len(self.signups)

    def __repr__(self):
        return f'<Activity {self.name}>'

class Signup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activity.id'), nullable=False)
    participant_name = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f'<Signup {self.participant_name} for Activity {self.activity_id}>'

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, server_default='user') # bv. 'user', 'organizer', 'admin'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} - {self.email}>'

class InvitationCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    used_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    role = db.Column(db.String(20), nullable=False, server_default='user')

    def __repr__(self):
        return f'<InvitationCode {self.code} (Used: {self.is_used})>'



class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('activity.id'), nullable=False)
    status = db.Column(db.String(30), nullable=False, default='unpaid')
    db.UniqueConstraint('user_id', 'activity_id', name='uq_user_activity_payment')

    def __repr__(self):
        return f'<Payment {self.id} - Status: {self.status}>'

# --- Helper Functions and Decorators ---


@app.context_processor
def inject_is_admin():
    return dict(is_admin=is_admin)

def is_admin():
    if not session.get('logged_in'):
        return False
    # Een gebruiker is admin als de username 'admin' is OF als de rol 'admin' is.
    return session.get('username') == 'admin' or session.get('role') == 'admin'

# In app.py (bij de andere helper functions)

# Helper om te checken of iemand admin OF organizer is
def is_organizer():
    if not session.get('logged_in'):
        return False
    # Admins mogen alles wat een organizer mag
    return is_admin() or session.get('role') == 'organizer'

def organizer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_organizer():
            flash('Je hebt geen rechten om activiteiten aan te maken.', 'danger')
            return redirect(url_for('activiteiten'))
        return f(*args, **kwargs)
    return decorated_function

# Voeg de nieuwe helper toe aan de context voor gebruik in templates
@app.context_processor
def inject_permissions():
    return dict(is_admin=is_admin, is_organizer=is_organizer)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            flash('Meld je aan om toegang te krijgen tot deze pagina.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            flash('Je hebt geen rechten om deze pagina te bekijken.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes (Website URLs) ---
@app.route('/')
def public_home():
    today = datetime.date.today()
    public_activities = Activity.query.filter(Activity.is_public == True, Activity.date >= today).order_by(Activity.date).all()
    return render_template('public_home.html', activities=public_activities)

@app.route('/agenda')
@login_required
def agenda():
    return render_template('agenda.html')


@app.route('/activiteiten')
@login_required
def activiteiten():
    today = datetime.date.today()
    activities = Activity.query.filter(Activity.date >= today).order_by(Activity.date).all()
    return render_template('index.html', activities=activities)


@app.route('/add_activity', methods=['GET', 'POST'])
@login_required
@organizer_required
def add_activity():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        date_str = request.form['date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        location = request.form['location']
        max_participants_str = request.form.get('max_participants')
        is_public = request.form.get('is_public') == 'true'
        cost_str = request.form.get('cost')
        cost = float(cost_str) if cost_str else None
        
        max_participants = int(max_participants_str) if max_participants_str else None
        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        
        new_activity = Activity(
            name=name, 
            description=description, 
            date=date_obj, 
            start_time=start_time, 
            end_time=end_time, 
            location=location,
            max_participants=max_participants,
            is_public=is_public,
            cost=cost
        )
        try:
            service = get_calendar_service()
            start_datetime_str = f"{date_str}T{start_time}:00" if start_time else f"{date_str}"
            end_datetime_str = f"{date_str}T{end_time}:00" if end_time else f"{date_str}"
            event_body = {
                'summary': name, 'location': location, 'description': description,
                'start': {'timeZone': 'Europe/Amsterdam'}, 'end': {'timeZone': 'Europe/Amsterdam'},
            }
            if start_time and end_time:
                event_body['start']['dateTime'] = start_datetime_str
                event_body['end']['dateTime'] = end_datetime_str
            else:
                event_body['start']['date'] = date_str
                event_body['end']['date'] = date_str
            created_event = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
            new_activity.google_event_id = created_event['id']
            flash(f"Activiteit '{name}' ook toegevoegd aan Google Agenda!", 'info')
        except FileNotFoundError:
            flash(f"Fout: Service account bestand niet gevonden. Google Agenda niet bijgewerkt.", 'warning')
            print(f"Google Calendar Error: Service account file not found at {SERVICE_ACCOUNT_FILE}")
        except Exception as e:
            flash(f"Fout bij toevoegen aan Google Agenda: {e}", 'warning')
            print(f"Google Calendar Error: {e}")
        db.session.add(new_activity)
        # ... code om de activiteit te verwijderen ...
        db.session.commit()
        flash('Activiteit succesvol toegevoegd!', 'success') # Changed message
        return redirect(url_for('activiteiten'))
    return render_template('add_activity.html')

@app.route('/activity/<int:activity_id>')
def view_activity(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    signups = Signup.query.filter_by(activity_id=activity.id).all()
    
    user = None # Begin met user als None voor gasten
    user_payment = None
    if 'logged_in' in session:
        user = User.query.filter_by(username=session['username']).first()
        if user: # Alleen als de gebruiker daadwerkelijk gevonden is
            user_payment = Payment.query.filter_by(user_id=user.id, activity_id=activity.id).first()

    # Haal alle betalingen voor deze activiteit op voor de admin-weergave
    payments_list = Payment.query.filter_by(activity_id=activity.id).all()
    payments_by_user = {p.user_id: p for p in payments_list}
    
    # Voeg de user objecten toe aan de signups (nodig voor admin-weergave)
    for signup in signups:
        signup.user = User.query.filter_by(username=signup.participant_name).first()

    # Geef alle benodigde data, INCLUSIEF 'user', mee aan de template
    return render_template(
        'view_activity.html', 
        activity=activity, 
        signups=signups, 
        user_payment=user_payment, 
        payments_by_user=payments_by_user,
        user=user  # <-- DEZE VARIABELE ONTBRAK
    )


# In app.py
@app.route('/confirm_payment/<int:activity_id>', methods=['POST'])
@login_required
def confirm_payment(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    user = User.query.filter_by(username=session['username']).first()

    # Meld de gebruiker aan als dat nog niet is gebeurd.
    existing_signup = Signup.query.filter_by(activity_id=activity.id, participant_name=user.username).first()
    if not existing_signup:
        if activity.max_participants is not None and activity.signups_count >= activity.max_participants:
            flash(f'Helaas, de activiteit "{activity.name}" is zojuist vol geraakt.', 'warning')
            return redirect(url_for('view_activity', activity_id=activity.id))
            
        new_signup = Signup(activity_id=activity.id, participant_name=user.username)
        db.session.add(new_signup)
        flash(f'Je bent succesvol aangemeld voor {activity.name}!', 'success')

    # Alleen betalingslogica uitvoeren als er kosten zijn
    if activity.cost and activity.cost > 0:
        payment = Payment.query.filter_by(user_id=user.id, activity_id=activity.id).first()
        if not payment:
            payment = Payment(user_id=user.id, activity_id=activity_id)
            db.session.add(payment)
        
        payment.status = 'pending_verification'
        flash('Bedankt! Je betaling wordt zo snel mogelijk geverifieerd.', 'info')

    db.session.commit()
    return redirect(url_for('view_activity', activity_id=activity.id))

@app.route('/delete_activity/<int:activity_id>', methods=['POST'])
@admin_required
def delete_activity(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    if activity.google_event_id:
        try:
            service = get_calendar_service()
            service.events().delete(calendarId=CALENDAR_ID, eventId=activity.google_event_id).execute()
            flash(f"Activiteit '{activity.name}' ook verwijderd uit Google Agenda!", 'info')
        except Exception as e:
            flash(f"Fout bij verwijderen uit Google Agenda: {e}", 'warning')
    db.session.delete(activity)
    db.session.commit()
    flash('Activiteit succesvol verwijderd!', 'success')
    return redirect(url_for('activiteiten'))

@app.route('/edit_activity/<int:activity_id>', methods=['GET', 'POST'])
@login_required
@organizer_required
def edit_activity(activity_id):
    activity = Activity.query.get_or_404(activity_id)

    if request.method == 'POST':
        # Haal gegevens uit het formulier
        activity.name = request.form['name']
        activity.description = request.form['description']
        date_str = request.form['date']
        activity.date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        activity.start_time = request.form['start_time']
        activity.end_time = request.form['end_time']
        activity.location = request.form['location']
        max_participants_str = request.form.get('max_participants')
        activity.max_participants = int(max_participants_str) if max_participants_str else None
        activity.is_public = request.form.get('is_public') == 'true'
        cost_str = request.form.get('cost')
        activity.cost = float(cost_str) if cost_str else None

        # Update Google Calendar Event
        if activity.google_event_id:
            try:
                service = get_calendar_service()
                event = service.events().get(calendarId=CALENDAR_ID, eventId=activity.google_event_id).execute()

                event['summary'] = activity.name
                event['description'] = activity.description
                event['location'] = activity.location
                
                if activity.start_time and activity.end_time:
                    event['start']['dateTime'] = f"{date_str}T{activity.start_time}:00"
                    event['end']['dateTime'] = f"{date_str}T{activity.end_time}:00"
                else:
                    event['start']['date'] = date_str
                    event['end']['date'] = date_str

                service.events().update(calendarId=CALENDAR_ID, eventId=activity.google_event_id, body=event).execute()
                flash('Google Agenda-evenement succesvol bijgewerkt!', 'info')
            except Exception as e:
                flash(f"Fout bij bijwerken van Google Agenda: {e}", 'warning')
        
        db.session.commit()
        flash('Activiteit succesvol bijgewerkt!', 'success')
        return redirect(url_for('view_activity', activity_id=activity.id))

    # GET request: toon het formulier met de huidige data
    return render_template('edit_activity.html', activity=activity)

@app.route('/delete_signup/<int:signup_id>', methods=['POST'])
@admin_required
def delete_signup(signup_id):
    signup = Signup.query.get_or_404(signup_id)
    activity_id = signup.activity_id
    participant_name = signup.participant_name
    db.session.delete(signup)
    db.session.commit()
    flash(f'Aanmelding van {participant_name} verwijderd!', 'success')
    return redirect(url_for('view_activity', activity_id=activity_id))

@app.route('/admin/activities')
@admin_required
def admin_activities():
    """Toont een overzicht van alle activiteiten, inclusief die in het verleden."""
    # Voeg 'today' toe voor gebruik in de template
    today = datetime.date.today() 
    activities = Activity.query.order_by(Activity.date.desc()).all()
    # Geef 'today' mee aan de render_template functie
    return render_template('admin_activities.html', activities=activities, today=today)

# --- app.py ---

# NOTE: The approve_signup route from the original code seems to be for an 'is_approved' flag on Signup,
#       but your Payment model handles the approval status. I will assume the request refers to payment approval.
#       If you also need a separate "signup approval" email for free activities (without payment),
#       please clarify and I can add that.
@app.route('/approve_payment/<int:payment_id>', methods=['POST'])
@admin_required
def approve_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    user_to_notify = User.query.get_or_404(payment.user_id)
    activity = Activity.query.get_or_404(payment.activity_id)

    if payment.status == 'paid':
        flash('Betaling is al goedgekeurd.', 'info')
        return redirect(url_for('view_activity', activity_id=payment.activity_id))

    payment.status = 'paid'
    db.session.commit()

    try:
        if user_to_notify.email:
            subject = f"Je betaling voor '{activity.name}' is goedgekeurd!"
            body = f"""
Beste {user_to_notify.username},

Geweldig nieuws! Je betaling voor de activiteit '{activity.name}' is ontvangen en goedgekeurd.
Je aanmelding is nu definitief.

Activiteit: {activity.name}
Datum: {activity.date.strftime('%d-%m-%Y')}
"""
            if activity.start_time:
                body += f"Tijd: {activity.start_time}\n"
            if activity.location:
                body += f"Locatie: {activity.location}\n"

            body += """
We kijken ernaar uit je te zien!

Met vriendelijke groet,
Het team van Chateau Overdruiven
"""
            msg = Message(subject, recipients=[user_to_notify.email], body=body)
            mail.send(msg)
            flash(f'Betaling goedgekeurd en bevestigingsmail verstuurd naar {user_to_notify.username}.', 'success')
        else:
            flash(f'Betaling goedgekeurd, maar geen e-mail verstuurd: gebruiker {user_to_notify.username} heeft geen e-mailadres.', 'warning')

    except Exception as e:
        print(f"Fout bij versturen goedkeuringsmail: {e}")
        flash('Betaling goedgekeurd, maar er ging iets mis bij het versturen van de e-mail.', 'danger')

    return redirect(url_for('view_activity', activity_id=payment.activity_id))

@app.route('/reject_payment/<int:payment_id>', methods=['POST'])
@admin_required
def reject_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    user_to_notify = User.query.get_or_404(payment.user_id)
    activity = Activity.query.get_or_404(payment.activity_id)

    if payment.status == 'unpaid':
        flash('Betaling is al afgewezen of nog niet betaald.', 'info')
        return redirect(url_for('view_activity', activity_id=payment.activity_id))

    payment.status = 'unpaid' 
    db.session.commit()
    
    try:
        if user_to_notify.email:
            subject = f"Status van je betaling voor '{activity.name}'"
            body = f"""
Beste {user_to_notify.username},

We moeten je helaas informeren dat je betaling voor de activiteit '{activity.name}' niet kon worden geverifieerd of is afgewezen.
Dit kan verschillende redenen hebben (bijv. onjuiste omschrijving, bedrag klopt niet, of de betaling is nog niet verwerkt).

Controleer alsjeblieft je betalingsgegevens en probeer het opnieuw via de activiteitspagina:
{url_for('view_activity', activity_id=activity.id, _external=True)}

Activiteit: {activity.name}
Datum: {activity.date.strftime('%d-%m-%Y')}
Kosten: €{"%.2f"|format(activity.cost)}

Onze excuses voor het ongemak.

Met vriendelijke groet,
Het team van Chateau Overdruiven
"""
            msg = Message(subject, recipients=[user_to_notify.email], body=body)
            mail.send(msg)
            flash(f'Betaling afgewezen en e-mail verstuurd naar {user_to_notify.username}.', 'success')
        else:
            flash(f'Betaling afgewezen, maar geen e-mail verstuurd: gebruiker {user_to_notify.username} heeft geen e-mailadres.', 'warning')
    except Exception as e:
        print(f"Fout bij versturen afwijsmail: {e}")
        flash('Betaling afgewezen, maar er ging iets mis bij het versturen van de e-mail.', 'danger')

    return redirect(url_for('view_activity', activity_id=payment.activity_id))


# --- Login, Logout, Register, Admin Routes... ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'logged_in' in session and session['logged_in']:
        return redirect(url_for('activiteiten'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['logged_in'] = True
            session['username'] = username
            session['role'] = user.role
            flash('Succesvol ingelogd!', 'success')
            return redirect(url_for('activiteiten'))
        else:
            flash('Ongeldige gebruikersnaam of wachtwoord', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('role', None)
    flash('Succesvol uitgelogd!', 'success')
    return redirect(url_for('public_home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'logged_in' in session and session['logged_in']:
        flash('Je bent al ingelogd. Log uit om een nieuw account te registreren.', 'info')
        return redirect(url_for('activiteiten'))
        
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        invite_code_str = request.form['invite_code'].strip()
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Deze gebruikersnaam is al bezet. Kies een andere.', 'danger')
            return render_template('register.html', username=username, email=email)
            
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('Dit e-mailadres is al in gebruik. Kies een andere.', 'danger')
            return render_template('register.html', username=username, email=email)
            
        invite_code = InvitationCode.query.filter_by(code=invite_code_str).first()
        if not invite_code or invite_code.is_used:
            flash('Ongeldige of reeds gebruikte uitnodigingscode.', 'danger')
            return render_template('register.html', username=username, email=email)
            
        # GEWIJZIGD: Ken de rol toe die in de uitnodigingscode staat
        new_user = User(username=username, email=email, role=invite_code.role) 
        new_user.set_password(password)
        db.session.add(new_user)
        # We moeten de user eerst een ID geven, dus we flushen de sessie
        db.session.flush()
        
        invite_code.is_used = True
        invite_code.used_by_user_id = new_user.id
        db.session.commit()
        
        flash('Registratie succesvol! Je kunt nu inloggen.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user_to_delete = User.query.get_or_404(user_id)
    if user_to_delete.username == session.get('username'):
        flash('Je kunt je eigen admin-account niet verwijderen.', 'danger')
        return redirect(url_for('admin_users'))
    db.session.delete(user_to_delete)
    db.session.commit()
    flash(f'Gebruiker "{user_to_delete.username}" succesvol verwijderd.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_id):
    user_to_edit = User.query.get_or_404(user_id)

    if request.method == 'POST':
        # Haal data uit het formulier
        new_email = request.form.get('email')
        new_password = request.form.get('password')

        # Controleer of de nieuwe email uniek is (als deze is gewijzigd)
        if new_email != user_to_edit.email:
            existing_user = User.query.filter_by(email=new_email).first()
            if existing_user:
                flash('Dit e-mailadres is al in gebruik door een andere gebruiker.', 'danger')
                return render_template('edit_user.html', user=user_to_edit)
            user_to_edit.email = new_email

        # Controleer of er een nieuw wachtwoord is ingevuld
        if new_password:
            user_to_edit.set_password(new_password)
            flash('Wachtwoord succesvol gewijzigd.', 'info')

        db.session.commit()
        flash('Gebruikersgegevens succesvol bijgewerkt.', 'success')
        return redirect(url_for('admin_users'))

    # GET request: toon het formulier met de huidige data
    return render_template('edit_user.html', user=user_to_edit)

@app.route('/admin/generate_code', methods=['GET', 'POST'])
@admin_required
def generate_code_web():
    if request.method == 'POST':
        role = request.form.get('role', 'user') 
        code = secrets.token_urlsafe(16)
        new_invite_code = InvitationCode(code=code, role=role) 
        db.session.add(new_invite_code)
        db.session.commit()
        flash(f"Nieuwe uitnodigingscode gegenereerd voor rol '{role}': '{code}'", 'success')
        return redirect(url_for('admin_invite_codes'))
    return render_template('generate_code.html')

@app.route('/admin/invite_codes')
@admin_required
def admin_invite_codes():
    codes = InvitationCode.query.order_by(InvitationCode.created_at.desc()).all()
    return render_template('admin_invite_codes.html', codes=codes)

@app.route('/admin/delete_invite_code/<int:code_id>', methods=['POST'])
@admin_required
def delete_invite_code(code_id):
    code_to_delete = InvitationCode.query.get_or_404(code_id)
    db.session.delete(code_to_delete)
    db.session.commit()
    flash(f"Uitnodigingscode succesvol verwijderd.", 'success')
    return redirect(url_for('admin_invite_codes'))

# The original `approve_signup` route which seems to have been removed or commented out.
# I will use the `approve_payment` and `reject_payment` routes for email notifications.
# @app.route('/approve_signup/<int:signup_id>', methods=['POST'])
# @admin_required
# def approve_signup(signup_id):
#     signup = Signup.query.get_or_404(signup_id)
#     activity = signup.activity
#     
#     if activity.max_participants is not None:
#         if activity.approved_signups_count >= activity.max_participants:
#             flash(f'Kan aanmelding niet goedkeuren, activiteit "{activity.name}" is al vol.', 'warning')
#             return redirect(url_for('view_activity', activity_id=activity.id))
#
#     signup.is_approved = True
#     db.session.commit()
#     
#     try:
#         # Zoek de gebruiker die bij deze aanmelding hoort
#         user_to_notify = User.query.filter_by(username=signup.participant_name).first()
#         
#         if user_to_notify and user_to_notify.email:
#             subject = f"Je aanmelding voor '{activity.name}' is goedgekeurd!"
#             
#             # Stel de body van de e-mail samen
#             body = f"""
# Beste {user_to_notify.username},
#
# Goed nieuws! Je aanmelding voor de volgende activiteit is betaald en goedgekeurd:
#
# Activiteit: {activity.name}
# Datum: {activity.date.strftime('%d-%m-%Y')}
# """
#             # Voeg optionele details toe als ze bestaan
#             if activity.start_time:
#                 body += f"Tijd: {activity.start_time}\n"
#             if activity.location:
#                 body += f"Locatie: {activity.location}\n"
#
#             body += """
# We zien je daar!
#
# Met vriendelijke groet,
# Bestuur van Chateau Overdruiven
# """
#             # Maak en verstuur de e-mail
#             msg = Message(subject, recipients=[user_to_notify.email], body=body)
#             mail.send(msg)
#             
#             flash(f'Aanmelding van {signup.participant_name} goedgekeurd en een bevestigingsmail is verstuurd!', 'success')
#         else:
#             flash(f'Aanmelding van {signup.participant_name} goedgekeurd, maar er kon geen e-mail worden verstuurd (gebruiker niet gevonden).', 'warning')
#
#     except Exception as e:
#         # Vang mogelijke fouten tijdens het mailen af
#         print(f"Fout bij het versturen van de e-mail: {e}")
#         flash(f'Aanmelding van {signup.participant_name} goedgekeurd, maar de bevestigingsmail kon niet worden verstuurd.', 'danger')
#         
#     return redirect(url_for('view_activity', activity_id=signup.activity_id))

# In app.py
@app.route('/contact', methods=['POST'])
def contact():
    # Haal de data uit het formulier
    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')

    # Stel de e-mail samen
    subject = f"Nieuwe aanvraag lidmaatschap van {name}"
    sender = app.config['MAIL_DEFAULT_SENDER']
    recipients = [app.config['ADMIN_EMAIL']]
    
    body = f"""
Je hebt een nieuwe aanvraag voor lidmaatschap ontvangen.

Naam: {name}
E-mailadres: {email}

Bericht:
{message}
"""
    try:
        msg = Message(subject, sender=sender, recipients=recipients, body=body)
        mail.send(msg)
        flash('Bedankt voor je aanvraag! We nemen zo snel mogelijk contact met je op.', 'success')
    except Exception as e:
        flash('Er ging iets mis bij het versturen van je aanvraag. Probeer het later opnieuw.', 'danger')
        print(f"Fout bij versturen van contactmail: {e}") # Voor debugging

    return redirect(url_for('public_home'))

# --- CLI Commands ---
# --- DEZE FUNCTIE IS NU BIJGEWERKT ---
@app.cli.command("create-user")
@click.argument("username")
@click.argument("email")
@click.argument("password")
def create_user_command(username, email, password):
    """Creëert een nieuwe gebruiker met username, email en password."""
    if User.query.filter_by(username=username).first():
        print(f"Fout: Gebruiker '{username}' bestaat al.")
        return
        
    if User.query.filter_by(email=email).first():
        print(f"Fout: E-mailadres '{email}' is al in gebruik.")
        return

    new_user = User(username=username, email=email)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    print(f"Gebruiker '{username}' met e-mail '{email}' succesvol aangemaakt.")


@app.cli.command("generate-invite-code")
def generate_invite_code_command():
    """Genereert en voegt een nieuwe uitnodigingscode toe aan de database."""
    code = secrets.token_urlsafe(16)
    new_invite_code = InvitationCode(code=code)
    db.session.add(new_invite_code)
    db.session.commit()
    print(f"Nieuwe uitnodigingscode gegenereerd: '{code}'")

@app.cli.command("list-invite-codes")
def list_invite_codes_command():
    """Toont alle uitnodigingscodes en hun status."""
    codes = InvitationCode.query.all()
    if not codes:
        print("Geen uitnodigingscodes gevonden.")
        return
    print("\n--- Uitnodigingscodes ---")
    for c in codes:
        status = "Gebruikt" if c.is_used else "Ongebruikt"
        used_by = f"door gebruiker ID: {c.used_by_user_id}" if c.used_by_user_id else ""
        print(f"Code: {c.code} | Status: {status} {used_by} | Aangemaakt: {c.created_at.strftime('%Y-%m-%d %H:%M')}")
    print("---------------------------\n")


if __name__ == '__main__':
    with app.app_context():
        app.run(debug=True)