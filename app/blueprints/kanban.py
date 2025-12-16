# app/blueprints/kanban.py
from flask import render_template, Blueprint, jsonify, request
from flask_login import login_required
import sqlalchemy as sa
from app import db
from app.models import Session, KANBAN_STAGES
from sqlalchemy.orm import joinedload
from datetime import datetime, date

bp = Blueprint('kanban', __name__, url_prefix='/kanban')

EDITING_STAGE = 'Edição' 
ARCHIVE_STAGE = KANBAN_STAGES[-1]

@bp.route('/')
@login_required
def index():
    sessions = db.session.scalars(
        sa.select(Session)
        .options(joinedload(Session.client), joinedload(Session.type)) 
        .filter(Session.kanban_status != ARCHIVE_STAGE)
        .order_by(Session.session_date.asc())
    ).all()

    # O dicionário armazena DIRETAMENTE os objetos Session
    kanban_data = {stage: [] for stage in KANBAN_STAGES}
    
    for session in sessions:
        # Usa a nova propriedade 'deadline_status' do Model para decidir a cor
        if session.kanban_status in kanban_data:
            kanban_data[session.kanban_status].append(session)
        else:
            # Fallback para segurança
            kanban_data[KANBAN_STAGES[0]].append(session)

    return render_template('kanban.html', kanban_data=kanban_data, stages=KANBAN_STAGES, KANBAN_STAGES=KANBAN_STAGES)

@bp.route('/update_status', methods=['POST'])
@login_required
def update_status():
    data = request.get_json()
    session_id = data.get('session_id')
    new_status = data.get('new_status')

    if not session_id or not new_status or new_status not in KANBAN_STAGES:
        return jsonify({'success': False, 'message': 'Dados inválidos.'}), 400

    session = db.session.get(Session, session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Ensaio não encontrado.'}), 404

    old_status = session.kanban_status
    
    if old_status == new_status:
        return jsonify({'success': True, 'message': 'Status inalterado.', 'action_required': None, 'archived': False})

    # Lógica de verificação para abrir modal de data
    if (new_status == EDITING_STAGE and old_status != EDITING_STAGE and session.selection_completed_date is None):
        return jsonify({'success': True, 'action_required': 'confirm_selection_date', 'message': 'Confirmação de data necessária.'})

    # Reset data de seleção se voltar antes da edição (regra de negócio opcional, mantida do original)
    try:
        old_status_index = KANBAN_STAGES.index(old_status)
        new_status_index = KANBAN_STAGES.index(new_status)
        editing_stage_index = KANBAN_STAGES.index(EDITING_STAGE)
        
        if old_status_index >= editing_stage_index and new_status_index < editing_stage_index:
            session.selection_completed_date = None
    except ValueError:
        pass

    session.kanban_status = new_status
    db.session.commit()

    archived = new_status == ARCHIVE_STAGE
    message = (f'Ensaio {session.session_code} arquivado.' if archived 
               else f'Status do ensaio {session.session_code} atualizado para {new_status}.')
    
    return jsonify({
        'success': True, 
        'message': message, 
        'archived': archived,
        'action_required': None
    })

@bp.route('/confirm_selection_date', methods=['POST'])
@login_required
def confirm_selection_date():
    data = request.get_json()
    session_id = data.get('session_id')
    selection_date_str = data.get('selection_date')

    if not session_id or not selection_date_str:
        return jsonify({'success': False, 'message': 'Dados incompletos.'}), 400

    session = db.session.get(Session, session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Ensaio não encontrado.'}), 404

    try:
        session.selection_completed_date = datetime.strptime(selection_date_str, '%Y-%m-%d').date()
        session.kanban_status = EDITING_STAGE
        db.session.commit()
        return jsonify({'success': True, 'message': 'Data de seleção confirmada e status atualizado.'})
    except ValueError:
        return jsonify({'success': False, 'message': 'Formato de data inválido.'}), 400