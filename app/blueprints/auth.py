# app/blueprints/auth.py
from flask import render_template, flash, redirect, url_for, Blueprint, request
from flask_login import login_user, logout_user, current_user
from app import db, limiter
from app.forms import LoginForm, RegistrationForm
from app.models import User
import sqlalchemy as sa

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('sessions.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash('Usuário ou senha inválidos', 'danger')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=True)
        
        # Redirecionamento seguro usando request
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('sessions.index')
        return redirect(next_page)
        
    return render_template('login.html', form=form)

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('sessions.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Registrado com sucesso!', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html', form=form)