# app/blueprints/goals.py
from flask import render_template, Blueprint, flash, redirect, url_for, request
from flask_login import login_required
import sqlalchemy as sa
from sqlalchemy import func
from app import db
from app.models import Goal, GoalContribution
from app.forms import GoalAddForm, GoalEditForm, GoalContributionForm
from datetime import date
from markupsafe import Markup
from decimal import Decimal

bp = Blueprint('goals', __name__, url_prefix='/metas')

@bp.route('/')
@login_required
def index():
    status_filter = request.args.get('status', 'Ativa')

    query = sa.select(Goal)
    if status_filter:
        query = query.filter(Goal.status == status_filter)

    goals = db.session.scalars(query.order_by(Goal.target_date.asc())).all()
    
    sums_query = sa.select(
        GoalContribution.goal_id, 
        func.sum(GoalContribution.value)
    ).group_by(GoalContribution.goal_id)
    
    sums_result = db.session.execute(sums_query).all()
    balance_map = {goal_id: (total_saved or Decimal('0.00')) for goal_id, total_saved in sums_result}
    
    goals_data = []
    for goal in goals:
        saved_value = balance_map.get(goal.id, Decimal('0.00'))
        # Cálculo com Decimal: evitar divisão por zero
        if goal.target_value > 0:
            progress_percent = (saved_value / goal.target_value) * 100
        else:
            progress_percent = Decimal(0)
            
        goals_data.append({
            'goal': goal,
            'saved_value': saved_value,
            'remaining_value': goal.target_value - saved_value,
            'progress_percent': progress_percent,
        })
        
    return render_template('metas.html', goals_data=goals_data, current_status=status_filter)

@bp.route('/<int:goal_id>', methods=['GET', 'POST'])
@login_required
def details(goal_id):
    goal = db.get_or_404(Goal, goal_id)
    form = GoalContributionForm()

    saved_value = db.session.scalar(
        sa.select(func.sum(GoalContribution.value)).where(GoalContribution.goal_id == goal.id)
    ) or Decimal('0.00')

    if form.validate_on_submit():
        if goal.status != 'Ativa':
            flash('Não é possível adicionar contribuições a metas concluídas ou canceladas.', 'warning')
            return redirect(url_for('goals.details', goal_id=goal.id))
        
        if saved_value >= goal.target_value:
            flash('A meta já foi atingida. Não é possível adicionar mais contribuições.', 'warning')
            return redirect(url_for('goals.details', goal_id=goal.id))

        new_contribution = GoalContribution(
            value=form.value.data,
            contribution_date=form.contribution_date.data,
            goal_id=goal.id
        )
        db.session.add(new_contribution)
        db.session.commit()
        flash('Contribuição adicionada!', 'success')

        if (saved_value + new_contribution.value) >= goal.target_value:
            edit_url = url_for('goals.edit_goal', goal_id=goal.id)
            message = Markup(
                f'Parabéns! A meta "{goal.name}" foi atingida. '
                f'<a href="{edit_url}" class="alert-link">Clique aqui para marcá-la como "Concluída".</a>'
            )
            flash(message, 'info')

        return redirect(url_for('goals.details', goal_id=goal.id))

    if goal.target_value > 0:
        progress_percent = (saved_value / goal.target_value) * 100
    else:
        progress_percent = Decimal(0)
        
    remaining_value = goal.target_value - saved_value

    contributions = db.session.scalars(sa.select(GoalContribution).where(GoalContribution.goal_id == goal.id).order_by(GoalContribution.contribution_date.desc())).all()
    
    return render_template('goal_details.html', goal=goal,
                           saved_value=saved_value,
                           remaining_value=remaining_value,
                           progress_percent=progress_percent,
                           contributions=contributions,
                           form=form)


@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_goal():
    form = GoalAddForm()
    if form.validate_on_submit():
        new_goal = Goal(
            name=form.name.data,
            target_value=form.target_value.data,
            target_date=form.target_date.data,
            notes=form.notes.data
        )
        db.session.add(new_goal)
        db.session.commit()
        flash('Nova meta adicionada com sucesso!', 'success')
        return redirect(url_for('goals.index'))
    return render_template('add_edit_goal.html', form=form, title='Adicionar Nova Meta', is_editing=False)

@bp.route('/edit/<int:goal_id>', methods=['GET', 'POST'])
@login_required
def edit_goal(goal_id):
    goal = db.get_or_404(Goal, goal_id)
    form = GoalEditForm(obj=goal)
    if form.validate_on_submit():
        goal.name = form.name.data
        goal.target_value = form.target_value.data
        goal.target_date = form.target_date.data
        goal.notes = form.notes.data
        goal.status = form.status.data
        db.session.commit()
        flash('Meta atualizada com sucesso!', 'success')
        return redirect(url_for('goals.index'))
    return render_template('add_edit_goal.html', form=form, title='Editar Meta', is_editing=True)

@bp.route('/<int:goal_id>/concluir', methods=['POST'])
@login_required
def concluir(goal_id):
    goal = db.get_or_404(Goal, goal_id)
    goal.status = 'Concluída'
    db.session.commit()
    flash(f'A meta "{goal.name}" foi marcada como concluída!', 'success')
    return redirect(url_for('goals.index'))


@bp.route('/delete/<int:goal_id>', methods=['POST', 'GET'])
@login_required
def delete_goal(goal_id):
    goal = db.get_or_404(Goal, goal_id)
    db.session.delete(goal)
    db.session.commit()
    flash('Meta e suas contribuições foram excluídas.', 'info')
    return redirect(url_for('goals.index'))

@bp.route('/<int:goal_id>/delete_contribution/<int:contribution_id>')
@login_required
def delete_contribution(goal_id, contribution_id):
    contribution = db.get_or_404(GoalContribution, contribution_id)
    goal = contribution.goal
    
    if goal.id != goal_id:
        flash('Operação inválida.', 'danger')
        return redirect(url_for('goals.details', goal_id=goal_id))
    
    db.session.delete(contribution)
    db.session.commit()
    flash('Contribuição excluída.', 'info')

    if goal.status == 'Concluída':
        total_saved_after_delete = db.session.scalar(
            sa.select(func.sum(GoalContribution.value)).where(GoalContribution.goal_id == goal.id)
        ) or Decimal('0.00')

        if total_saved_after_delete < goal.target_value:
            goal.status = 'Ativa'
            db.session.commit()
            flash(f'O status da meta "{goal.name}" foi revertido para "Ativa", pois o valor salvo ficou abaixo do alvo.', 'warning')
    
    return redirect(url_for('goals.details', goal_id=goal_id))