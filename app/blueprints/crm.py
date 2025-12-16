# app/blueprints/crm.py
from flask import render_template, Blueprint, flash, redirect, url_for, request
from flask_login import login_required
import sqlalchemy as sa
from sqlalchemy import func
from app import db
from app.models import Client, InteractionLog, Session, Transaction
from app.forms import ClientFilterForm, ClientForm, InteractionLogForm
from datetime import date
from decimal import Decimal

bp = Blueprint('crm', __name__, url_prefix='/clientes')

@bp.route('/')
@login_required
def index():
    filter_form = ClientFilterForm(request.args, meta={'csrf': False})
    query = sa.select(Client)
    if filter_form.search.data:
        query = query.filter(Client.name.ilike(f'%{filter_form.search.data}%'))
    if filter_form.lead_source.data:
        query = query.filter(Client.lead_source == filter_form.lead_source.data)
    if filter_form.tags.data:
        query = query.filter(Client.tags.ilike(f'%{filter_form.tags.data}%'))
    clients = db.session.scalars(query.order_by(Client.name)).all()
    return render_template('clients.html', clients=clients, filter_form=filter_form)

@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    form = ClientForm()
    if form.validate_on_submit():
        new_client = Client()
        form.populate_obj(new_client)
        db.session.add(new_client)
        db.session.commit()
        flash('Cliente adicionado com sucesso!', 'success')
        return redirect(url_for('crm.index'))
    return render_template('add_edit_client.html', title='Adicionar Novo Cliente', form=form)

@bp.route('/edit/<int:client_id>', methods=['GET', 'POST'])
@login_required
def edit(client_id):
    client = db.get_or_404(Client, client_id)
    form = ClientForm(obj=client, original_name=client.name)
    if form.validate_on_submit():
        form.populate_obj(client)
        client.address_state = client.address_state.upper() if client.address_state else None
        db.session.commit()
        flash('Informações do cliente atualizadas!', 'success')
        return redirect(url_for('crm.index'))
    return render_template('add_edit_client.html', title='Editar Cliente', form=form)

@bp.route('/<client_name>')
@login_required
def client_details(client_name):
    client = db.session.scalar(sa.select(Client).where(Client.name == client_name))
    if not client:
        flash(f"Cliente '{client_name}' não encontrado.", 'warning')
        return redirect(url_for('crm.index'))
        
    interaction_form = InteractionLogForm()
    interaction_form.interaction_date.data = date.today()
    
    interactions = client.interactions.order_by(InteractionLog.interaction_date.desc()).all()
    
    sessions = db.session.scalars(sa.select(Session).where(Session.client_id == client.id).order_by(Session.session_date.desc())).all()
    
    # Correção: Total pago em Decimal
    total_paid = db.session.scalar(sa.select(func.sum(Transaction.value)).join(Session).where(Session.client_id == client.id, Transaction.transaction_type == 'entry')) or Decimal('0.00')
    
    # Mapa de pagamentos por sessão
    paid_amounts = {s.id: (db.session.scalar(sa.select(func.sum(Transaction.value)).where(Transaction.session_id == s.id, Transaction.transaction_type == 'entry')) or Decimal('0.00')) for s in sessions}
    
    return render_template('client_details.html', 
                           client=client,
                           sessions=sessions, 
                           total_paid=total_paid, 
                           paid_amounts=paid_amounts,
                           interactions=interactions,
                           interaction_form=interaction_form)

@bp.route('/<int:client_id>/add_interaction', methods=['POST'])
@login_required
def add_interaction(client_id):
    client = db.get_or_404(Client, client_id)
    form = InteractionLogForm()
    if form.validate_on_submit():
        new_interaction = InteractionLog(
            client_id=client.id,
            interaction_date=form.interaction_date.data,
            channel=form.channel.data,
            notes=form.notes.data
        )
        db.session.add(new_interaction)
        db.session.commit()
        flash('Interação registrada com sucesso!', 'success')
        return redirect(url_for('crm.client_details', client_name=client.name))
    else:
        flash('Erro ao registrar interação. Verifique os campos.', 'danger')
        interactions = client.interactions.order_by(InteractionLog.interaction_date.desc()).all()
        sessions = db.session.scalars(sa.select(Session).where(Session.client_id == client.id).order_by(Session.session_date.desc())).all()
        total_paid = db.session.scalar(sa.select(func.sum(Transaction.value)).join(Session).where(Session.client_id == client.id, Transaction.transaction_type == 'entry')) or Decimal('0.00')
        paid_amounts = {s.id: (db.session.scalar(sa.select(func.sum(Transaction.value)).where(Transaction.session_id == s.id, Transaction.transaction_type == 'entry')) or Decimal('0.00')) for s in sessions}
        
        return render_template('client_details.html', 
                               client=client,
                               sessions=sessions, 
                               total_paid=total_paid, 
                               paid_amounts=paid_amounts,
                               interactions=interactions,
                               interaction_form=form)

@bp.route('/delete_interaction/<int:interaction_id>', methods=['POST'])
@login_required
def delete_interaction(interaction_id):
    interaction = db.get_or_404(InteractionLog, interaction_id)
    client_name = interaction.client.name
    db.session.delete(interaction)
    db.session.commit()
    flash('Registro de interação excluído.', 'info')
    return redirect(url_for('crm.client_details', client_name=client_name))