# app/blueprints/sessions.py
from flask import render_template, flash, redirect, url_for, request, Blueprint, abort
from flask_login import login_required
import sqlalchemy as sa
from app import db, get_month_name_pt_br
from app.forms import SessionForm, SessionEditForm, SessionFilterForm
from app.models import Session, Transaction, Client, SessionType, Configuration, KANBAN_STAGES
from app.finance_service import SessionFinanceService # Serviço de Domínio
from sqlalchemy import func, or_
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import joinedload, selectinload
import re
import unicodedata

bp = Blueprint('sessions', __name__)

def sanitize_text(text):
    """Remove acentos e caracteres especiais para uso em códigos/URLs."""
    if not text: return ""
    nfkd_form = unicodedata.normalize('NFKD', text)
    sanitized = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    sanitized = re.sub(r'[^a-zA-Z0-9]', '', sanitized)
    return sanitized.upper()

@bp.route('/')
@bp.route('/index')
@login_required
def index():
    today = date.today()
    month, year = today.month, today.year
    
    base_query = sa.select(func.sum(Transaction.value)).filter(sa.extract('year', Transaction.transaction_date) == year)
    
    entries_month = db.session.scalar(base_query.filter(Transaction.transaction_type == 'entry', sa.extract('month', Transaction.transaction_date) == month)) or Decimal('0.00')
    exits_month = db.session.scalar(base_query.filter(Transaction.transaction_type == 'exit', sa.extract('month', Transaction.transaction_date) == month)) or Decimal('0.00')
    
    monthly_session_count = db.session.scalar(sa.select(func.count(Session.id)).filter(sa.extract('month', Session.session_date) == month, sa.extract('year', Session.session_date) == year)) or 0
    
    entries_year = db.session.scalar(sa.select(func.sum(Transaction.value)).filter(Transaction.transaction_type == 'entry', sa.extract('year', Transaction.transaction_date) == year)) or Decimal('0.00')
    exits_year = db.session.scalar(sa.select(func.sum(Transaction.value)).filter(Transaction.transaction_type == 'exit', sa.extract('year', Transaction.transaction_date) == year)) or Decimal('0.00')
    yearly_session_count = db.session.scalar(sa.select(func.count(Session.id)).filter(sa.extract('year', Session.session_date) == year)) or 0
    
    return render_template('index.html', month_name=get_month_name_pt_br(month), current_year=year,
                           total_entries_month=entries_month, total_exits_month=exits_month, balance_month=entries_month - exits_month, monthly_session_count=monthly_session_count,
                           total_entries_year=entries_year, total_exits_year=exits_year, balance_year=entries_year - exits_year, yearly_session_count=yearly_session_count)

@bp.route('/sessoes')
@login_required
def sessoes():
    filter_form = SessionFilterForm(request.args, meta={'csrf': False})
    query = sa.select(Session).options(joinedload(Session.client), joinedload(Session.type))
    
    query = query.filter(Session.kanban_status == KANBAN_STAGES[-1]) if filter_form.status.data == 'arquivados' else query.filter(Session.kanban_status != KANBAN_STAGES[-1])
        
    if filter_form.search.data:
        search_term = f"%{filter_form.search.data}%"
        query = query.join(Client).filter(or_(Client.name.ilike(search_term), Session.session_code.ilike(search_term)))
    if filter_form.client.data: query = query.filter(Session.client_id == filter_form.client.data.id)
    if filter_form.session_type.data: query = query.filter(Session.session_type_id == filter_form.session_type.data.id)
    if filter_form.start_date.data: query = query.filter(Session.session_date >= filter_form.start_date.data)
    if filter_form.end_date.data: query = query.filter(Session.session_date <= filter_form.end_date.data)
        
    sort_logic = {'date_desc': Session.session_date.desc(), 'date_asc': Session.session_date.asc(), 'value_desc': Session.total_value.desc(), 'value_asc': Session.total_value.asc()}
    query = query.order_by(sort_logic.get(filter_form.sort_by.data, Session.session_date.desc()))
    
    return render_template('sessoes.html', sessions=db.session.scalars(query).all(), filter_form=filter_form)

@bp.route('/sessoes/restore/<int:session_id>', methods=['POST', 'GET'])
@login_required
def restore_session(session_id):
    session = db.get_or_404(Session, session_id)
    session.kanban_status = KANBAN_STAGES[0]
    db.session.commit()
    flash(f'O ensaio "{session.session_code}" foi restaurado.', 'success')
    return redirect(url_for('sessions.sessoes', status='arquivados'))

@bp.route('/add_session', methods=['GET', 'POST'])
@login_required
def add_session():
    form = SessionForm()
    if not db.session.query(SessionType).count():
        flash('Cadastre um "Tipo de Ensaio" nas configurações primeiro.', 'warning')
        return redirect(url_for('config.session_types'))
        
    if form.validate_on_submit():
        # 1. Criação/Seleção do Cliente
        target_client = form.client.data
        if form.is_new_family.data:
            target_client = Client(
                name=form.new_family_name.data.strip(), 
                email=form.new_family_email.data, whatsapp=form.new_family_whatsapp.data,
                lead_source=form.new_lead_source.data, tags=form.new_client_tags.data
            )
            db.session.add(target_client)
            # Flush gera o ID do cliente para usarmos no código da sessão, sem comitar a transação inteira
            db.session.flush()
            
        # 2. Criação Inicial da Sessão
        session = Session(
            client_id=target_client.id, 
            session_type_id=form.session_type.data.id, 
            session_date=form.session_date.data, 
            notes=form.notes.data,
            extra_photos_qty=(form.extra_photos_qty.data or 0), 
            printing_qty=(form.printing_qty.data or 0),
            total_value=form.total_value.data, 
            down_payment=form.down_payment.data, 
            session_cost=form.session_cost.data,
            extra_photo_unit_price=form.extra_photo_unit_price.data, 
            printing_unit_price=form.printing_unit_price.data, 
            session_code="TEMP"
        )
        db.session.add(session)
        # Flush gera o ID da sessão, necessário para criar as Transações vinculadas a ela
        db.session.flush()
        
        # 3. Geração do Código
        cleaned_name = sanitize_text(target_client.name)
        first_name = cleaned_name.split()[0] if cleaned_name.split() else f"CLI{target_client.id}"
        session.session_code = f"{session.session_date.strftime('%y%m%d')}_{first_name}_{session.type.abbreviation}_{session.id}"
        
        # 4. Sincronização Financeira via Serviço (Unificado!)
        # Aqui substituímos 30 linhas de código manual repetido pela chamada segura
        SessionFinanceService.update_session_financials(session, form)
            
        db.session.commit()
        
        flash('Ensaio registrado com sucesso!', 'success')
        return redirect(url_for('sessions.sessoes')) if not form.submit_and_new.data else redirect(url_for('sessions.add_session'))
    
    elif request.method == 'GET':
        # Pre-load de valores padrão do banco
        extra_photo_price = db.session.scalar(sa.select(Configuration.value).filter_by(key='extra_photo_price')) or '0'
        printing_price = db.session.scalar(sa.select(Configuration.value).filter_by(key='printing_price')) or '0'
        form.extra_photo_unit_price.data = Decimal(extra_photo_price)
        form.printing_unit_price.data = Decimal(printing_price)
        
    return render_template('add_session.html', form=form)

@bp.route('/edit_session/<int:session_id>', methods=['GET', 'POST'])
@login_required
def edit_session(session_id):
    stmt = sa.select(Session).options(selectinload(Session.transactions)).filter_by(id=session_id)
    session = db.session.scalars(stmt).first()
    
    if not session: abort(404)
    
    form = SessionEditForm(obj=session)
    
    if form.validate_on_submit():
        # Popula campos simples
        form.populate_obj(session) 
        
        # Popula campos financeiros explicitamente para garantir tipos Decimal
        session.total_value = form.total_value.data
        session.down_payment = form.down_payment.data
        session.session_cost = form.session_cost.data
        session.extra_photo_unit_price = form.extra_photo_unit_price.data
        session.printing_unit_price = form.printing_unit_price.data
        
        # Delega lógica financeira para o serviço
        SessionFinanceService.update_session_financials(session, form)
        
        db.session.commit()
        flash('Ensaio atualizado!', 'success')
        return redirect(url_for('sessions.sessoes'))
        
    elif request.method == 'GET':
        # Preparação da View
        form.session_type.data = session.type
        form.down_payment_paid.data = session.has_down_payment_transaction
        
        remaining = session.total_value - session.down_payment
        form.total_value_paid.data = True if remaining <= 0 else session.has_final_payment_transaction
        
        extras = (Decimal(session.extra_photos_qty) * session.extra_photo_unit_price)
        form.extra_photos_paid.data = True if extras <= 0 else session.has_extra_photos_transaction
        
        printing = (Decimal(session.printing_qty) * session.printing_unit_price)
        form.printing_paid.data = True if printing <= 0 else session.has_printing_transaction
        
    return render_template('edit_session.html', form=form)

@bp.route('/delete_session/<int:session_id>', methods=['POST', 'GET'])
@login_required
def delete_session(session_id):
    session = db.get_or_404(Session, session_id)
    db.session.delete(session)
    db.session.commit()
    flash('Ensaio e todas as transações associadas foram excluídos.', 'info')
    return redirect(url_for('sessions.sessoes'))