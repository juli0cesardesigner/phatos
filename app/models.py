# app/models.py
from app import db, login
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import sqlalchemy as sa
from datetime import date
from decimal import Decimal

KANBAN_STAGES = [
    'Agendado', 'Backup PC', 'Backup Online', 'Seleção', 'Prova', 'Edição',
    'Arquivar Cliente', 'Envio Final', 'Impressão', 'Arquivar'
]

@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))

class Configuration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(200), nullable=False)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    password_hash = db.Column(db.String(256))
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), index=True, unique=True, nullable=False)
    email = db.Column(db.String(128), nullable=True, index=True)
    whatsapp = db.Column(db.String(20), nullable=True)
    lead_source = db.Column(db.String(50), nullable=True)
    tags = db.Column(db.String(256), nullable=True)
    address_street = db.Column(db.String(200), nullable=True)
    address_city = db.Column(db.String(100), nullable=True)
    address_state = db.Column(db.String(2), nullable=True)
    address_zip_code = db.Column(db.String(10), nullable=True)
    main_contact_birthday = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    sessions = db.relationship('Session', back_populates='client', lazy='dynamic')
    interactions = db.relationship('InteractionLog', back_populates='client', lazy='dynamic', cascade='all, delete-orphan')

class SessionType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    abbreviation = db.Column(db.String(10), unique=True, nullable=False)
    selection_deadline_days = db.Column(db.Integer, nullable=False, default=4)
    editing_deadline_days = db.Column(db.Integer, nullable=False, default=15)
    sessions = db.relationship('Session', backref='type', lazy='dynamic')

class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_code = db.Column(db.String(128), unique=True, nullable=False, index=True)
    session_date = db.Column(db.Date, nullable=False, index=True)
    selection_completed_date = db.Column(db.Date, nullable=True)
    
    total_value = db.Column(sa.Numeric(10, 2), nullable=False, default=Decimal('0.00'))
    down_payment = db.Column(sa.Numeric(10, 2), nullable=False, default=Decimal('0.00'))
    session_cost = db.Column(sa.Numeric(10, 2), nullable=True, default=Decimal('0.00'))
    
    extra_photos_qty = db.Column(db.Integer, nullable=False, default=0)
    extra_photo_unit_price = db.Column(sa.Numeric(10, 2), nullable=False, default=Decimal('0.00'))
    
    printing_qty = db.Column(db.Integer, nullable=False, default=0)
    printing_unit_price = db.Column(sa.Numeric(10, 2), nullable=False, default=Decimal('0.00'))
    
    notes = db.Column(db.Text, nullable=True)
    kanban_status = db.Column(db.String(50), nullable=False, default=KANBAN_STAGES[0])
    
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    session_type_id = db.Column(db.Integer, db.ForeignKey('session_type.id'), nullable=False)
    
    client = db.relationship('Client', back_populates='sessions')
    transactions = db.relationship('Transaction', backref='session', cascade='all, delete-orphan')

    @property
    def has_down_payment_transaction(self):
        return any(t.category == 'session_down_payment' or (t.description and t.description.startswith('Entrada ensaio')) for t in self.transactions)
    
    @property
    def has_final_payment_transaction(self):
        return any(t.category == 'session_settlement' or (t.description and t.description.startswith('Pag. final ensaio')) for t in self.transactions)
    
    @property
    def has_extra_photos_transaction(self):
        return any(t.category == 'session_extra_photos' or (t.description and t.description.startswith('Fotos extras ensaio')) for t in self.transactions)
    
    @property
    def has_printing_transaction(self):
        return any(t.category == 'session_printing' or (t.description and t.description.startswith('Impressões ensaio')) for t in self.transactions)

    # NOVA LÓGICA DE PRAZO MIGRADA PARA O MODELO
    @property
    def deadline_status(self):
        """Calcula a classe CSS do status do prazo."""
        # Se arquivado, não tem status
        if self.kanban_status == KANBAN_STAGES[-1]: 
            return ''
        
        today = date.today()
        session_type = self.type
        days_passed = 0
        deadline_days = 0
        
        # Lógica 1: Prazo de Seleção (Ainda não selecionou)
        if self.selection_completed_date is None:
            deadline_days = session_type.selection_deadline_days
            days_passed = (today - self.session_date).days
            
            # Se passou prazo negativo (erro de data futura), considera 0
            if days_passed < 0: days_passed = 0
            
            if deadline_days <= 0: return '' # Sem prazo definido

            if days_passed <= deadline_days * 0.5:
                return 'deadline-ok'
            elif days_passed <= deadline_days * 0.75:
                return 'deadline-due'
            elif days_passed < deadline_days:
                return 'deadline-urgent'
            else:
                return 'deadline-overdue'

        # Lógica 2: Prazo de Edição (Já selecionou)
        else:
            deadline_days = session_type.editing_deadline_days
            days_passed = (today - self.selection_completed_date).days
            
            if days_passed < 0: days_passed = 0
            
            if deadline_days <= 0: return ''

            if days_passed <= deadline_days * 0.5:
                return 'deadline-ok'
            elif days_passed <= deadline_days * 0.8:
                return 'deadline-due'
            elif days_passed < deadline_days:
                return 'deadline-urgent'
            else:
                return 'deadline-overdue'

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(256))
    transaction_type = db.Column(db.String(10), nullable=False, index=True)
    value = db.Column(sa.Numeric(10, 2), nullable=False)
    transaction_date = db.Column(db.Date, nullable=False, index=True)
    tags = db.Column(db.String(256))
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'))
    recurrence_id = db.Column(db.String(50), nullable=True, index=True)
    recurrence_installment = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(20), nullable=False, server_default='efetivado', default='efetivado')
    category = db.Column(db.String(50), index=True, nullable=True) 

class InteractionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    interaction_date = db.Column(db.Date, nullable=False, index=True, default=date.today)
    channel = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    client = db.relationship('Client', back_populates='interactions')

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    target_value = db.Column(sa.Numeric(10, 2), nullable=False, default=Decimal('0.00'))
    target_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Ativa')
    notes = db.Column(db.Text, nullable=True)
    contributions = db.relationship('GoalContribution', backref='goal', lazy='dynamic', cascade='all, delete-orphan')

class GoalContribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(sa.Numeric(10, 2), nullable=False, default=Decimal('0.00'))
    contribution_date = db.Column(db.Date, nullable=False)
    goal_id = db.Column(db.Integer, db.ForeignKey('goal.id'), nullable=False)