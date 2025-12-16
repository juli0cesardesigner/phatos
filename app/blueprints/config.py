# app/blueprints/config.py
from flask import render_template, flash, redirect, url_for, Blueprint, request
from flask_login import login_required
import sqlalchemy as sa
from app import db
from app.forms import PricingForm, SessionTypeForm
from app.models import Configuration, SessionType, Session
from decimal import Decimal

bp = Blueprint('config', __name__, url_prefix='/config')

@bp.route('/pricing', methods=['GET', 'POST'])
@login_required
def pricing():
    form = PricingForm()
    if form.validate_on_submit():
        extra_photo = db.session.scalar(sa.select(Configuration).filter_by(key='extra_photo_price')) or Configuration(key='extra_photo_price', value='0')
        printing = db.session.scalar(sa.select(Configuration).filter_by(key='printing_price')) or Configuration(key='printing_price', value='0')
        
        # Salva como string (banco TEXT) vindo do Decimal do Form
        extra_photo.value = str(form.extra_photo_price.data)
        printing.value = str(form.printing_price.data)
        
        db.session.add_all([extra_photo, printing])
        db.session.commit()
        flash('Preços padrão atualizados!', 'success')
        return redirect(url_for('config.pricing'))
    
    elif request.method == 'GET':
        extra_photo_price = db.session.scalar(sa.select(Configuration.value).filter_by(key='extra_photo_price')) or '0.00'
        printing_price = db.session.scalar(sa.select(Configuration.value).filter_by(key='printing_price')) or '0.00'
        
        # Converte string do banco para Decimal no form
        form.extra_photo_price.data = Decimal(extra_photo_price)
        form.printing_price.data = Decimal(printing_price)
        
    return render_template('pricing.html', form=form)

@bp.route('/session_types')
@login_required
def session_types():
    types=db.session.scalars(sa.select(SessionType).order_by(SessionType.name)).all()
    return render_template('session_types.html', session_types=types)

@bp.route('/session_types/add', methods=['GET', 'POST'])
@login_required
def add_session_type():
    form = SessionTypeForm()
    if form.validate_on_submit():
        new_type = SessionType(
            name=form.name.data, 
            abbreviation=form.abbreviation.data.upper(),
            selection_deadline_days=form.selection_deadline_days.data,
            editing_deadline_days=form.editing_deadline_days.data
        )
        db.session.add(new_type)
        db.session.commit()
        flash('Tipo de ensaio adicionado!', 'success')
        return redirect(url_for('config.session_types'))
    return render_template('add_edit_session_type.html', title='Adicionar Tipo de Ensaio', form=form)

@bp.route('/session_types/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_session_type(id):
    stype=db.get_or_404(SessionType,id)
    form=SessionTypeForm(obj=stype, original_abbreviation=stype.abbreviation)
    if form.validate_on_submit():
        stype.name=form.name.data
        stype.abbreviation=form.abbreviation.data.upper()
        stype.selection_deadline_days=form.selection_deadline_days.data
        stype.editing_deadline_days=form.editing_deadline_days.data
        db.session.commit()
        flash('Tipo de ensaio atualizado!', 'success')
        return redirect(url_for('config.session_types'))
    return render_template('add_edit_session_type.html', title='Editar Tipo de Ensaio', form=form)

@bp.route('/session_types/delete/<int:id>')
@login_required
def delete_session_type(id):
    stype=db.get_or_404(SessionType,id)
    if db.session.scalar(sa.select(Session).where(Session.session_type_id==stype.id)): 
        flash('Erro: Este tipo de ensaio está em uso.', 'danger')
        return redirect(url_for('config.session_types'))
    
    db.session.delete(stype)
    db.session.commit()
    flash('Tipo de ensaio excluído.', 'info')
    return redirect(url_for('config.session_types'))