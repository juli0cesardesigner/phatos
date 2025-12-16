# app/blueprints/reports.py
from flask import render_template, Blueprint, request, redirect, url_for
from flask_login import login_required
import sqlalchemy as sa
from sqlalchemy import func, case
from app import db, get_month_name_pt_br
from app.models import Transaction, Client, Session, SessionType
from app.forms import DateRangeFilterForm
from datetime import date, datetime
from decimal import Decimal

bp = Blueprint('reports', __name__, url_prefix='/relatorios')

def get_dates_from_request():
    """Helper para obter e validar datas da URL, com fallback para o ano corrente."""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    today = date.today()
    
    start_date, end_date = None, None
    
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        start_date, end_date = None, None

    if not start_date or not end_date:
        start_date = date(today.year, 1, 1)
        end_date = today
        
    return start_date, end_date

@bp.route('/')
@login_required
def index():
    return redirect(url_for('reports.financial_performance'))

@bp.route('/financeiro')
@login_required
def financial_performance():
    form = DateRangeFilterForm(request.args, meta={'csrf': False})
    start_date, end_date = get_dates_from_request()
    
    form.start_date.data = start_date
    form.end_date.data = end_date

    base_query = sa.select(Transaction).filter(Transaction.transaction_date.between(start_date, end_date))
    
    total_revenue = db.session.scalar(base_query.with_only_columns(func.sum(Transaction.value)).filter(Transaction.transaction_type == 'entry')) or Decimal('0.00')
    total_costs = db.session.scalar(base_query.with_only_columns(func.sum(Transaction.value)).filter(Transaction.transaction_type == 'exit')) or Decimal('0.00')
    
    net_profit = total_revenue - total_costs
    
    monthly_query = sa.select(
        sa.extract('year', Transaction.transaction_date).label('year'),
        sa.extract('month', Transaction.transaction_date).label('month'),
        func.sum(case((Transaction.transaction_type == 'entry', Transaction.value), else_=Decimal(0))).label('total_entries'),
        func.sum(case((Transaction.transaction_type == 'exit', Transaction.value), else_=Decimal(0))).label('total_exits')
    ).filter(Transaction.transaction_date.between(start_date, end_date)).group_by('year', 'month').order_by('year', 'month')
    
    monthly_data = db.session.execute(monthly_query).all()
    
    # Sanitização para garantir que o template receba Decimal ou 0 (e não None)
    processed_monthly = []
    for m in monthly_data:
        processed_monthly.append({
            'month': m.month,
            'year': m.year,
            'total_entries': m.total_entries or Decimal('0.00'),
            'total_exits': m.total_exits or Decimal('0.00')
        })

    return render_template(
        'reports.html', form=form, total_revenue=total_revenue, total_costs=total_costs,
        net_profit=net_profit, monthly_data=processed_monthly, get_month_name_pt_br=get_month_name_pt_br)

@bp.route('/leads')
@login_required
def lead_source_analysis():
    form = DateRangeFilterForm(request.args, meta={'csrf': False})
    start_date, end_date = get_dates_from_request()
    
    form.start_date.data = start_date
    form.end_date.data = end_date

    revenue_subquery = sa.select(
        Session.client_id,
        func.sum(Transaction.value).label('total_revenue')
    ).join(Transaction).where(
        Transaction.transaction_type == 'entry',
        Transaction.transaction_date.between(start_date, end_date)
    ).group_by(Session.client_id).subquery()
    
    lead_source_query = sa.select(
        Client.lead_source,
        func.count(Client.id).label('client_count'),
        func.sum(revenue_subquery.c.total_revenue).label('total_revenue')
    ).outerjoin(
        revenue_subquery, Client.id == revenue_subquery.c.client_id
    ).filter(
        Client.lead_source.isnot(None),
        Client.lead_source != ''
    ).group_by(
        Client.lead_source
    ).order_by(
        sa.desc('total_revenue')
    )
    
    results = db.session.execute(lead_source_query).all()
    
    # Sanitiza para o template (None -> 0.00)
    cleaned_results = []
    for row in results:
        cleaned_results.append({
            'lead_source': row.lead_source,
            'client_count': row.client_count,
            'total_revenue': row.total_revenue or Decimal('0.00')
        })
        
    return render_template('report_lead_source.html', form=form, results=cleaned_results)

@bp.route('/lucratividade')
@login_required
def profitability_analysis():
    form = DateRangeFilterForm(request.args, meta={'csrf': False})
    start_date, end_date = get_dates_from_request()

    form.start_date.data = start_date
    form.end_date.data = end_date
    
    revenue_subquery = sa.select(
        Transaction.session_id,
        func.sum(Transaction.value).label('revenue')
    ).where(
        Transaction.transaction_type == 'entry',
        Transaction.transaction_date.between(start_date, end_date)
    ).group_by(Transaction.session_id).subquery()

    profit_query = sa.select(
        SessionType.name.label('session_type_name'),
        func.count(Session.id).label('session_count'),
        func.sum(revenue_subquery.c.revenue).label('total_revenue'),
        func.sum(Session.session_cost).label('total_cost')
    ).join(
        SessionType, Session.session_type_id == SessionType.id
    ).outerjoin(
        revenue_subquery, Session.id == revenue_subquery.c.session_id
    ).where(
        Session.session_date.between(start_date, end_date)
    ).group_by(
        SessionType.name
    )
    
    results_raw = db.session.execute(profit_query).all()
    
    results_with_profit = []
    for row in results_raw:
        rev = row.total_revenue or Decimal('0.00')
        cost = row.total_cost or Decimal('0.00')
        profit = rev - cost
        
        results_with_profit.append({
            'session_type_name': row.session_type_name,
            'session_count': row.session_count,
            'total_revenue': rev,
            'total_cost': cost,
            'profit': profit
        })
        
    results = sorted(results_with_profit, key=lambda x: x['profit'], reverse=True)

    return render_template('report_profitability.html', form=form, results=results)