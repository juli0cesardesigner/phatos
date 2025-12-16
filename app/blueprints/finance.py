# app/blueprints/finance.py
from flask import render_template, flash, redirect, url_for, Blueprint, request
from flask_login import login_required
import sqlalchemy as sa
from sqlalchemy import func
from app import db, get_month_name_pt_br
from app.forms import TransactionForm, TransactionFilterForm
from app.models import Transaction, Session, Client
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import time

bp = Blueprint('finance', __name__, url_prefix='/financeiro')

@bp.route('/')
@login_required
def index():
    filter_form = TransactionFilterForm(request.args, meta={'csrf': False})
    
    query = sa.select(Transaction)
    
    query_params = request.args.to_dict()
    
    use_month_nav = not (filter_form.start_date.data or filter_form.end_date.data)
    current_date = None

    if use_month_nav:
        try:
            year = int(request.args.get('year', date.today().year))
            month = int(request.args.get('month', date.today().month))
            current_date = date(year, month, 1)
        except (ValueError, TypeError):
            current_date = date.today()
        
        query = query.filter(
            sa.extract('month', Transaction.transaction_date) == current_date.month,
            sa.extract('year', Transaction.transaction_date) == current_date.year
        )

    if filter_form.search.data:
        query = query.filter(Transaction.description.ilike(f'%{filter_form.search.data}%'))
    if filter_form.trans_type.data:
        query = query.filter(Transaction.transaction_type == filter_form.trans_type.data)
    if filter_form.start_date.data:
        query = query.filter(Transaction.transaction_date >= filter_form.start_date.data)
    if filter_form.end_date.data:
        query = query.filter(Transaction.transaction_date <= filter_form.end_date.data)
    if filter_form.client.data:
        query = query.join(Transaction.session).filter(Session.client_id == filter_form.client.data.id)

    summary_query = query.with_only_columns(func.sum(Transaction.value))
    
    # USANDO DECIMAL PARA EVITAR ERRO DE OPERANDO (Decimal vs Float)
    total_entries = db.session.scalar(
        summary_query.filter(Transaction.transaction_type == 'entry', Transaction.status == 'efetivado')
    ) or Decimal('0.00')
    
    total_exits = db.session.scalar(
        summary_query.filter(Transaction.transaction_type == 'exit', Transaction.status == 'efetivado')
    ) or Decimal('0.00')
    
    balance = total_entries - total_exits
    
    transactions = db.session.scalars(query.order_by(Transaction.transaction_date.desc())).all()

    month_name, current_year, prev_month, next_month = (None, None, None, None)
    if current_date:
        month_name = get_month_name_pt_br(current_date.month)
        current_year = current_date.year
        prev_month = current_date - relativedelta(months=1)
        next_month = current_date + relativedelta(months=1)

    return render_template('financeiro.html', 
                           transactions=transactions,
                           month_name=month_name,
                           year=current_year,
                           prev_month=prev_month,
                           next_month=next_month,
                           filter_form=filter_form,
                           use_month_nav=use_month_nav,
                           total_entries=total_entries,
                           total_exits=total_exits,
                           balance=balance,
                           query_params=query_params)

@bp.route('/add', methods=['GET','POST'])
@login_required
def add_transaction():
    form = TransactionForm()
    if form.validate_on_submit():
        start_date = form.transaction_date.data
        status = 'efetivado' if start_date <= date.today() else 'previsto'

        if not form.is_recurring.data:
            new_trans = Transaction(
                description=form.description.data,
                transaction_type=form.transaction_type.data,
                value=form.value.data, # Já é Decimal vindo do Form
                transaction_date=start_date,
                tags=form.tags.data,
                status=status,
                category='manual' # Marca como manual explicitamente
            )
            db.session.add(new_trans)
            flash('Transação salva!', 'success')
        else:
            recurrence_id = f"rec-{int(time.time())}"
            base_description = form.description.data
            
            frequency_map = {
                'daily': relativedelta(days=1), 'weekly': relativedelta(weeks=1),
                'monthly': relativedelta(months=1), 'bimonthly': relativedelta(months=2),
                'quarterly': relativedelta(months=3), 'yearly': relativedelta(years=1)
            }
            delta = frequency_map.get(form.recurrence_frequency.data)

            if form.recurrence_type.data == 'installment':
                installments_count = form.recurrence_installments.data or 1
                
                # Calcula valor da parcela (divisão segura Decimal)
                # Atenção: Simples divisão. Centavos remanescentes na última parcela não tratados para simplicidade MVP,
                # mas Decimal garante que não vira 33.33333333333334
                total_val = form.value.data
                installment_val = total_val  # No form atual, assume-se que o usuário digita o valor da parcela ou total?
                # Assumindo que no form o usuário digita o VALOR DA PARCELA se selecionar "Repetir Lançamento" ou ajusta manual.
                # Mudei a lógica aqui: O valor do form É o valor que será salvo em cada recorrência
                
                for i in range(installments_count):
                    installment_date = start_date + (delta * i)
                    installment_status = 'efetivado' if installment_date <= date.today() else 'previsto'
                    installment_label = f"({i+1}/{installments_count})"
                    new_trans = Transaction(
                        description=f"{base_description} {installment_label}",
                        transaction_type=form.transaction_type.data, 
                        value=form.value.data,
                        transaction_date=installment_date, 
                        tags=form.tags.data,
                        recurrence_id=recurrence_id, 
                        recurrence_installment=installment_label,
                        status=installment_status,
                        category='manual'
                    )
                    db.session.add(new_trans)
                flash(f'{installments_count} transações parceladas foram adicionadas!', 'success')
            
            elif form.recurrence_type.data == 'fixed':
                for i in range(24):
                    installment_date = start_date + (delta * i)
                    installment_status = 'efetivado' if installment_date <= date.today() else 'previsto'
                    new_trans = Transaction(
                        description=base_description, 
                        transaction_type=form.transaction_type.data,
                        value=form.value.data, 
                        transaction_date=installment_date,
                        tags=form.tags.data, 
                        recurrence_id=recurrence_id,
                        recurrence_installment="Fixa", 
                        status=installment_status,
                        category='manual'
                    )
                    db.session.add(new_trans)
                flash('Transação fixa criada para os próximos 2 anos!', 'success')

        db.session.commit()
        return redirect(url_for('finance.index'))
        
    return render_template('add_transaction.html', form=form)

@bp.route('/toggle_status/<int:transaction_id>', methods=['POST'])
@login_required
def toggle_status(transaction_id):
    trans = db.get_or_404(Transaction, transaction_id)
    trans.status = 'efetivado' if trans.status == 'previsto' else 'previsto'
    db.session.commit()
    return redirect(url_for('finance.index', **request.args))

@bp.route('/edit/<int:transaction_id>', methods=['GET','POST'])
@login_required
def edit_transaction(transaction_id):
    trans = db.get_or_404(Transaction, transaction_id)
    form = TransactionForm(obj=trans)
    
    if form.validate_on_submit():
        trans.description = form.description.data
        trans.value = form.value.data
        trans.transaction_date = form.transaction_date.data
        trans.tags = form.tags.data
        
        # Apenas permite mudar o tipo se não for vinculado a uma sessão (segurança de dados)
        if not trans.session_id:
            trans.transaction_type = form.transaction_type.data
            if not trans.category:
                 trans.category = 'manual'
        
        # Lógica de recorrência (edição em lote simples)
        # No MVP atual, se editar "Todos", vamos atualizar valores e tags dos outros
        # Essa é uma lógica complexa, simplificada aqui:
        if form.is_recurring.data and form.edit_scope.data in ['future', 'all'] and trans.recurrence_id:
            scope_query = sa.select(Transaction).filter(Transaction.recurrence_id == trans.recurrence_id)
            if form.edit_scope.data == 'future':
                scope_query = scope_query.filter(Transaction.transaction_date >= trans.transaction_date)
            
            related_transactions = db.session.scalars(scope_query).all()
            for rel_t in related_transactions:
                if rel_t.id == trans.id: continue
                rel_t.description = form.description.data + (f" {rel_t.recurrence_installment}" if rel_t.recurrence_installment else "")
                rel_t.value = form.value.data
                rel_t.tags = form.tags.data
        
        db.session.commit()
        flash('Transação atualizada!', 'success')
        return redirect(url_for('finance.index', **request.args))
        
    return render_template('edit_transaction.html', form=form, transaction=trans, query_params=request.args)

@bp.route('/delete/<int:transaction_id>', methods=['POST','GET'])
@login_required
def delete_transaction(transaction_id):
    trans = db.get_or_404(Transaction, transaction_id)
    
    recurrence_id = trans.recurrence_id
    delete_all = False
    # Se houver parâmetro query 'delete_series' (implementar botão no futuro), deletaria tudo
    # Por enquanto, deleção unitária padrão.
    
    db.session.delete(trans)
    db.session.commit()
    flash('Transação excluída.', 'info')
    return redirect(url_for('finance.index', **request.args))