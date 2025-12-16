# app/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, BooleanField, IntegerField, TextAreaField, EmailField, RadioField
from wtforms.fields import DateField
from wtforms_sqlalchemy.fields import QuerySelectField 
from wtforms.validators import DataRequired, EqualTo, ValidationError, Optional, Length, Email
from app.models import User, SessionType, Client, Configuration
import sqlalchemy as sa
from app import db
from app.fields import CurrencyField

msg_required = 'Este campo é obrigatório.'
def get_session_types(): return db.session.scalars(sa.select(SessionType).order_by(SessionType.name))
def get_clients(): return db.session.scalars(sa.select(Client).order_by(Client.name))

LEAD_SOURCE_CHOICES = [
    ('', '--- Selecione a Origem ---'), ('Indicação', 'Indicação'), ('Instagram', 'Instagram'),
    ('Facebook', 'Facebook'), ('Site', 'Site/Busca'), ('Evento', 'Evento'), ('Outro', 'Outro')
]

class DateRangeFilterForm(FlaskForm):
    start_date = DateField('De:', validators=[Optional()], format='%Y-%m-%d')
    end_date = DateField('Até:', validators=[Optional()], format='%Y-%m-%d')
    submit = SubmitField('Gerar Relatório')

class PricingForm(FlaskForm):
    extra_photo_price = CurrencyField('Preço Padrão da Foto Extra', validators=[DataRequired()])
    printing_price = CurrencyField('Preço Padrão da Impressão', validators=[DataRequired()])
    submit = SubmitField('Salvar Preços')

class LoginForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired(message=msg_required)])
    password = PasswordField('Senha', validators=[DataRequired(message=msg_required)])
    submit = SubmitField('Entrar')

class RegistrationForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired(message=msg_required)])
    password = PasswordField('Senha', validators=[DataRequired(message=msg_required)])
    password2 = PasswordField('Repita a Senha', validators=[DataRequired(message=msg_required), EqualTo('password', message='As senhas devem ser iguais.')])
    submit = SubmitField('Registrar')
    def validate_username(self, username):
        if db.session.scalar(sa.select(User).where(User.username == username.data)): raise ValidationError('Este nome de usuário já existe.')

class SessionForm(FlaskForm):
    is_new_family = BooleanField('Cadastrar novo cliente')
    client = QuerySelectField('Cliente', query_factory=get_clients, get_label='name', allow_blank=True, blank_text='--- Selecione um cliente ---', validators=[Optional()])
    new_family_name = StringField('Nome do Cliente', validators=[Optional()])
    new_family_email = EmailField('Email', validators=[Optional(), Email(message="Email inválido.")])
    new_family_whatsapp = StringField('Whatsapp', validators=[Optional()])
    new_lead_source = SelectField('Como conheceu?', choices=LEAD_SOURCE_CHOICES, validators=[Optional()])
    new_client_tags = StringField('Tags (separadas por vírgula)', validators=[Optional()], description="Ex: Gestante, Newborn, Casamento")
    session_type = QuerySelectField('Tipo de Ensaio', query_factory=get_session_types, get_label='name', allow_blank=True, blank_text='--- Selecione um tipo ---', validators=[DataRequired(message=msg_required)])
    session_date = DateField('Data do Ensaio', format='%Y-%m-%d', validators=[DataRequired(message=msg_required)])
    total_value = CurrencyField('Valor Total do Ensaio', validators=[DataRequired(message=msg_required)])
    total_value_paid = BooleanField('Valor Total Quitado')
    down_payment = CurrencyField('Valor da Entrada', validators=[Optional()])
    down_payment_paid = BooleanField('Entrada Quitada')
    extra_photos_qty = IntegerField('Qtd. Fotos Extras', validators=[Optional()])
    extra_photo_unit_price = CurrencyField('Valor Unit. Foto Extra', validators=[Optional()])
    extra_photos_paid = BooleanField('Fotos Extras Quitado')
    printing_qty = IntegerField('Qtd. Impressões', validators=[Optional()])
    printing_unit_price = CurrencyField('Valor Unit. Impressão', validators=[Optional()])
    printing_paid = BooleanField('Impressão Quitada')
    session_cost = CurrencyField('Custo do Ensaio (opcional)', validators=[Optional()])
    notes = TextAreaField('Observações', validators=[Optional()])
    submit = SubmitField('Salvar')
    submit_and_new = SubmitField('Salvar e Adicionar Outro')

    def validate(self, **kwargs):
        if not super().validate(**kwargs): return False
        if hasattr(self, 'is_new_family') and self.is_new_family is not None:
            if not self.is_new_family.data and self.client.data is None: self.client.errors.append('Selecione um cliente ou marque "cadastrar novo".'); return False
            if self.is_new_family.data:
                if not self.new_family_name.data: self.new_family_name.errors.append('O nome do novo cliente é obrigatório.'); return False
                if db.session.scalar(sa.select(Client).where(Client.name == self.new_family_name.data)): self.new_family_name.errors.append('Este cliente já existe.'); return False
        return True

class SessionEditForm(SessionForm):
    is_new_family = None
    new_family_name = None
    new_family_email = None
    new_family_whatsapp = None
    new_lead_source = None
    new_client_tags = None
    submit_and_new = None
        
class ClientFilterForm(FlaskForm):
    search = StringField('Buscar por Nome', validators=[Optional()])
    lead_source = SelectField('Origem', choices=[('', '[Todas]')] + LEAD_SOURCE_CHOICES[1:], validators=[Optional()])
    tags = StringField('Tags', validators=[Optional()])

class ClientForm(FlaskForm):
    name = StringField('Nome do Cliente', validators=[DataRequired(message=msg_required)])
    email = EmailField('Email', validators=[Optional(), Email(message="Email inválido.")])
    whatsapp = StringField('Whatsapp', validators=[Optional()])
    main_contact_birthday = DateField('Aniversário (Contato Principal)', validators=[Optional()])
    lead_source = SelectField('Como conheceu?', choices=LEAD_SOURCE_CHOICES, validators=[Optional()])
    tags = StringField('Tags (separadas por vírgula)', validators=[Optional()], description="Ex: Gestante, Newborn, VIP")
    address_street = StringField('Endereço', validators=[Optional()])
    address_city = StringField('Cidade', validators=[Optional()])
    address_state = StringField('Estado (UF)', validators=[Optional(), Length(max=2)])
    address_zip_code = StringField('CEP', validators=[Optional()])
    notes = TextAreaField('Observações Gerais', validators=[Optional()])
    submit = SubmitField('Salvar Cliente')

    def __init__(self, original_name=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_name = original_name

    def validate_name(self, name):
        if name.data != self.original_name:
            if db.session.scalar(sa.select(Client).where(Client.name == name.data)):
                raise ValidationError('Este nome de cliente já existe.')

class InteractionLogForm(FlaskForm):
    interaction_date = DateField('Data', validators=[DataRequired(message=msg_required)], format='%Y-%m-%d')
    channel = SelectField('Canal', choices=[
        ('WhatsApp', 'WhatsApp'), ('Ligação', 'Ligação'), ('Email', 'E-mail'),
        ('Reunião Presencial', 'Reunião Presencial'), ('Outro', 'Outro')
    ], validators=[DataRequired(message=msg_required)])
    notes = TextAreaField('Anotações', validators=[DataRequired(message=msg_required)])
    submit = SubmitField('Registrar')

class TransactionForm(FlaskForm):
    description = StringField('Descrição', validators=[DataRequired(message=msg_required)])
    value = CurrencyField('Valor', validators=[DataRequired(message=msg_required)])
    transaction_date = DateField('Data', format='%Y-%m-%d', validators=[DataRequired(message=msg_required)])
    transaction_type = SelectField('Tipo', choices=[('entry', 'Entrada'), ('exit', 'Saída')], validators=[DataRequired()])
    tags = StringField('Etiquetas (separadas por vírgula)')
    submit = SubmitField('Salvar Transação')
    is_recurring = BooleanField('Repetir Lançamento')
    recurrence_type = SelectField('Tipo de Repetição', choices=[('fixed', 'Fixa'), ('installment', 'Parcelada')], validators=[Optional()])
    recurrence_frequency = SelectField('Frequência', choices=[
        ('daily', 'Diário'), ('weekly', 'Semanal'), ('monthly', 'Mensal'),
        ('bimonthly', 'Bimestral'), ('quarterly', 'Trimestral'), ('yearly', 'Anual')
    ], validators=[Optional()])
    recurrence_installments = IntegerField('Quantidade de Parcelas', validators=[Optional()])
    edit_scope = RadioField('Escopo da Edição', choices=[
        ('single', 'Atualizar apenas este lançamento'),
        ('future', 'Atualizar este e os próximos'),
        ('all', 'Atualizar todos os lançamentos da série')
    ], default='single', validators=[Optional()])

class SessionFilterForm(FlaskForm):
    search = StringField('Buscar por Nome/Código', validators=[Optional()])
    client = QuerySelectField('Cliente', query_factory=get_clients, get_label='name', allow_blank=True, blank_text='[Todos]')
    session_type = QuerySelectField('Tipo de Ensaio', query_factory=get_session_types, get_label='name', allow_blank=True, blank_text='[Todos]')
    start_date = DateField('De:', validators=[Optional()])
    end_date = DateField('Até:', validators=[Optional()])
    sort_by = SelectField('Ordenar por', choices=[('date_desc', 'Data (Mais Recente)'),('date_asc', 'Data (Mais Antiga)'),('value_desc', 'Valor (Maior)'),('value_asc', 'Valor (Menor)')], default='date_desc')
    status = SelectField('Status', choices=[('ativos', 'Ativos no Fluxo'), ('arquivados', 'Arquivados')], default='ativos')
    
class SessionTypeForm(FlaskForm):
    name = StringField('Nome do Tipo de Ensaio', validators=[DataRequired(message=msg_required)])
    abbreviation = StringField('Abreviatura (Ex: NB, GEST)', validators=[DataRequired(message=msg_required), Length(min=2, max=10)])
    selection_deadline_days = IntegerField('Prazo para Seleção (dias)', validators=[DataRequired(message=msg_required)])
    editing_deadline_days = IntegerField('Prazo para Edição (dias)', validators=[DataRequired(message=msg_required)])
    submit = SubmitField('Salvar')
    def __init__(self, original_abbreviation=None, *args, **kwargs): super().__init__(*args, **kwargs); self.original_abbreviation = original_abbreviation
    def validate_abbreviation(self, abbreviation):
        if abbreviation.data == self.original_abbreviation: return
        if db.session.scalar(sa.select(SessionType).where(SessionType.abbreviation == abbreviation.data)): raise ValidationError('Esta abreviatura já está em uso.')

class TransactionFilterForm(FlaskForm):
    search = StringField('Buscar por Descrição', validators=[Optional()])
    trans_type = SelectField('Tipo', choices=[('', 'Todos'), ('entry', 'Entrada'), ('exit', 'Saída')], default='')
    client = QuerySelectField('Cliente', query_factory=get_clients, get_label='name', allow_blank=True, blank_text='[Todos]', validators=[Optional()])
    start_date = DateField('Data Inicial', validators=[Optional()])
    end_date = DateField('Data Final', validators=[Optional()])

class GoalAddForm(FlaskForm):
    name = StringField('Nome da Meta/Desejo', validators=[DataRequired(message=msg_required)])
    target_value = CurrencyField('Valor Alvo', validators=[DataRequired(message=msg_required)])
    target_date = DateField('Data Alvo', validators=[Optional()])
    notes = TextAreaField('Observações', validators=[Optional()])
    submit = SubmitField('Salvar Meta')

class GoalEditForm(GoalAddForm):
    status = SelectField('Status', choices=[('Ativa', 'Ativa'), ('Concluída', 'Concluída'), ('Cancelada', 'Cancelada')], validators=[DataRequired()])

class GoalContributionForm(FlaskForm):
    value = CurrencyField('Valor da Contribuição', validators=[DataRequired(message=msg_required)])
    contribution_date = DateField('Data', validators=[DataRequired(message=msg_required)])
    submit = SubmitField('Adicionar')