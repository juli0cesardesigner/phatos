# app/__init__.py

import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from decimal import Decimal

# Carrega variáveis do arquivo .env se existir
load_dotenv()

MONTHS_PT_BR = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

def get_month_name_pt_br(month_number):
    try:
        return MONTHS_PT_BR[month_number]
    except IndexError:
        return ""

def format_currency(value):
    # Refatorado para aceitar Decimal, Float ou None com segurança
    if value is None:
        value = 0
    return f'R$ {value:,.2f}'.replace(",", "X").replace(".", ",").replace("X", ".")

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

# CONFIGURAÇÃO DE SEGURANÇA
# Tenta pegar do sistema (.env), se não tiver, usa fallback (APENAS PARA DEV)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'fallback-inseguro-apenas-para-dev-troque-isso-em-prod'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configura Filtros Jinja
app.jinja_env.filters['currency'] = format_currency

# INICIALIZAÇÃO DAS EXTENSÕES
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login = LoginManager(app)
login.login_view = 'auth.login'
login.login_message = "Por favor, faça login para acessar esta página."

# CONFIGURAÇÃO DO FLASK-LIMITER (Rate Limiting)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["2000 per day", "500 per hour"], # Limite geral para rotas não decoradas
    storage_uri="memory://" # Armazena em memória (bom para SQLite/Dev). Use Redis em produção.
)

# MANIPULADOR DE ERRO 429 (BLOQUEIO) INTELIGENTE
@app.errorhandler(429)
def ratelimit_handler(e):
    """
    Captura o erro de limite excedido e calcula o tempo de espera para o countdown do frontend.
    """
    description = str(e.description).lower()
    wait_seconds = 60 # Valor padrão de segurança (1 minuto)
    
    # Tenta deduzir o tempo baseado na string do erro (ex: "10 per 1 minute")
    if "day" in description:
        wait_seconds = 86400 # 1 dia
    elif "hour" in description:
        wait_seconds = 3600 # 1 hora
    elif "minute" in description:
        wait_seconds = 60 # 1 minuto
    elif "second" in description:
        wait_seconds = 10 # 10 segundos

    # Passa a variável wait_seconds para o template calcular o countdown
    return render_template('429.html', error=e, wait_seconds=wait_seconds), 429

# REGISTRO DOS BLUEPRINTS
# Importa os módulos apenas após inicializar as extensões para evitar ciclos
from app.blueprints import auth, sessions, finance # Importa blueprints ativos
# from app.blueprints import config, kanban, goals, crm, reports # Comenta blueprints desativados

app.register_blueprint(auth.bp)
app.register_blueprint(sessions.bp)
# app.register_blueprint(config.bp) # Comenta blueprint desativado
app.register_blueprint(finance.bp)
# app.register_blueprint(kanban.bp) # Comenta blueprint desativado
# app.register_blueprint(goals.bp) # Comenta blueprint desativado
# app.register_blueprint(crm.bp) # Comenta blueprint desativado
# app.register_blueprint(reports.bp) # Comenta blueprint desativado

# IMPORTA MODELOS PARA O CONTEXTO DO SHELL E MIGRAÇÕES
from app import models