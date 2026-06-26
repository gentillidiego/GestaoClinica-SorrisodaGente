from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from database import execute, query
from datetime import datetime, timedelta
from constants import CLINICAL_EXECUTOR_ROLES, Role, canonical_role
from services.execution_unit_service import get_default_execution_unit, get_execution_unit_choices, normalize_execution_unit
from services.security_service import audit_log, permission_required
from services.web_security_service import flash_internal_error

agenda_bp = Blueprint('agenda', __name__, url_prefix='/agenda')
FULL_AGENDA_SCOPE_ROLES = {Role.ADMIN, Role.COORDENACAO, Role.RECEPCAO}


def _get_week_range(ref_date):
    """Retorna (segunda-feira, domingo) da semana de ref_date."""
    start = ref_date - timedelta(days=ref_date.weekday())
    end = start + timedelta(days=6)
    return start, end


def _can_manage():
    """Verifica se o usuário pode criar/editar/cancelar consultas."""
    return current_user.can('agenda:write')


def _current_role():
    return canonical_role(getattr(current_user, 'role', None))


def _has_full_agenda_scope():
    return _current_role() in FULL_AGENDA_SCOPE_ROLES


def _has_own_agenda_scope():
    return _current_role() == Role.CLINICOS


def _agenda_scope():
    return 'full' if _has_full_agenda_scope() else 'own'


def _consulta_scope_clause(column='c.dentista_id'):
    if _has_full_agenda_scope():
        return '', []
    if _has_own_agenda_scope():
        return f' AND {column} = %s', [current_user.id]
    return ' AND 1 = 0', []


def _list_clinical_users():
    roles = tuple(sorted(CLINICAL_EXECUTOR_ROLES | {Role.ADMIN}))
    placeholders = ', '.join(['%s'] * len(roles))
    return query(
        f"SELECT id, username, full_name FROM users WHERE role IN ({placeholders}) ORDER BY full_name ASC",
        roles,
    )


def _list_visible_dentistas():
    if _has_full_agenda_scope():
        return _list_clinical_users()
    if _has_own_agenda_scope():
        return query(
            "SELECT id, username, full_name FROM users WHERE id = %s ORDER BY full_name ASC",
            (current_user.id,),
        )
    return []


def _is_agenda_professional(user_id):
    if not user_id:
        return False
    roles = tuple(sorted(CLINICAL_EXECUTOR_ROLES | {Role.ADMIN}))
    placeholders = ', '.join(['%s'] * len(roles))
    result = query(
        f"SELECT id FROM users WHERE id = %s AND role IN ({placeholders})",
        tuple([user_id, *roles]),
        one=True,
    )
    return bool(result)


def _resolve_dentista_id(requested_dentista_id):
    if _has_own_agenda_scope():
        return current_user.id
    return requested_dentista_id


def _can_use_dentista_id(dentista_id):
    if _has_own_agenda_scope():
        return dentista_id == current_user.id
    if _has_full_agenda_scope():
        return _is_agenda_professional(dentista_id)
    return False


def _get_scoped_consulta(consulta_id, include_patient=False):
    joins = ''
    fields = 'c.*'
    if include_patient:
        fields += ', p.nome as patient_nome, u.username as dentista_username'
        joins = """
        JOIN patients p ON c.patient_id = p.id
        JOIN users u ON c.dentista_id = u.id
        """
    scope_clause, scope_params = _consulta_scope_clause('c.dentista_id')
    return query(
        f"""
        SELECT {fields}
        FROM consultas c
        {joins}
        WHERE c.id = %s
        {scope_clause}
        """,
        tuple([consulta_id, *scope_params]),
        one=True,
    )


@agenda_bp.route('/')
@login_required
@permission_required('agenda:view')
def agenda_index():
    # Semana de referência via query param (ISO date da segunda)
    week_str = request.args.get('semana')
    try:
        week_start = datetime.strptime(week_str, '%Y-%m-%d').date() if week_str else None
        if week_start is None:
            raise ValueError
    except ValueError:
        today = datetime.today().date()
        week_start = today - timedelta(days=today.weekday())

    week_end = week_start + timedelta(days=6)

    # Filtros
    requested_dentista_id = request.args.get('dentista_id', type=int)
    dentista_id = requested_dentista_id if _has_full_agenda_scope() else None
    status_filter = request.args.get('status', '')
    execution_unit_filter = normalize_execution_unit(request.args.get('execution_unit'))

    # Monta a query de consultas da semana
    sql = """
        SELECT c.id, c.data_consulta, c.duracao_minutos, c.status, c.observacoes, c.execution_unit,
               p.id as patient_id, p.nome as patient_nome,
               u.id as dentista_id, u.username as dentista_username, u.full_name as dentista_fullname
        FROM consultas c
        JOIN patients p ON c.patient_id = p.id
        JOIN users u ON c.dentista_id = u.id
        WHERE DATE(c.data_consulta) BETWEEN %s AND %s
    """
    params = [week_start.isoformat(), week_end.isoformat()]

    if dentista_id:
        sql += " AND c.dentista_id = %s"
        params.append(dentista_id)
    else:
        scope_clause, scope_params = _consulta_scope_clause('c.dentista_id')
        sql += scope_clause
        params.extend(scope_params)

    if status_filter:
        sql += " AND c.status = %s"
        params.append(status_filter)
    if execution_unit_filter:
        sql += " AND c.execution_unit = %s"
        params.append(execution_unit_filter)

    sql += " ORDER BY c.data_consulta ASC"
    consultas = query(sql, params)

    # Organiza consultas por dia da semana (0=Seg, 6=Dom)
    week_days = [week_start + timedelta(days=i) for i in range(7)]
    consultas_por_dia = {d: [] for d in week_days}
    for c in consultas:
        d = c['data_consulta'].date()
        if d in consultas_por_dia:
            consultas_por_dia[d].append(c)

    # Consultas de hoje para a lista diária
    today = datetime.today().date()
    consultas_hoje = [c for c in consultas if c['data_consulta'].date() == today]

    # Dentistas disponíveis para o filtro
    dentistas = _list_visible_dentistas()
    execution_units = get_execution_unit_choices()

    # Pacientes para o modal de nova consulta
    patients = query("SELECT id, nome FROM patients ORDER BY nome ASC") if _can_manage() else []

    prev_week = (week_start - timedelta(days=7)).isoformat()
    next_week = (week_start + timedelta(days=7)).isoformat()

    return render_template(
        'agenda/index.html',
        week_days=week_days,
        consultas_por_dia=consultas_por_dia,
        consultas_hoje=consultas_hoje,
        dentistas=dentistas,
        patients=patients,
        execution_units=execution_units,
        execution_unit_labels=dict(execution_units),
        today=today,
        week_start=week_start,
        week_end=week_end,
        prev_week=prev_week,
        next_week=next_week,
        dentista_id_filter=dentista_id,
        status_filter=status_filter,
        execution_unit_filter=execution_unit_filter,
        agenda_scope=_agenda_scope(),
    )


@agenda_bp.route('/nova', methods=['POST'])
@login_required
def nova_consulta():
    if not _can_manage():
        flash('Sem permissão para criar consultas.', 'danger')
        return redirect(url_for('agenda.agenda_index'))

    patient_id = request.form.get('patient_id', type=int)
    dentista_id = _resolve_dentista_id(request.form.get('dentista_id', type=int))
    data_hora = request.form.get('data_consulta')
    duracao = request.form.get('duracao_minutos', 30, type=int)
    execution_unit = normalize_execution_unit(request.form.get('execution_unit')) or get_default_execution_unit()
    observacoes = request.form.get('observacoes', '')

    if not all([patient_id, dentista_id, data_hora]):
        flash('Paciente, dentista e data/hora são obrigatórios.', 'danger')
        return redirect(url_for('agenda.agenda_index'))

    if not _can_use_dentista_id(dentista_id):
        flash('Profissional inválido para o seu perfil de acesso.', 'danger')
        return redirect(url_for('agenda.agenda_index'))

    try:
        dt = datetime.strptime(data_hora, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('Formato de data/hora inválido.', 'danger')
        return redirect(url_for('agenda.agenda_index'))

    try:
        consulta_id = execute(
            """
            INSERT INTO consultas (patient_id, dentista_id, data_consulta, duracao_minutos, execution_unit, observacoes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (patient_id, dentista_id, dt, duracao, execution_unit, observacoes, current_user.id),
        )
        audit_log(
            action='appointment_created',
            module='agenda',
            entity_type='consulta',
            entity_id=consulta_id,
            patient_id=patient_id,
            details={
                'dentista_id': dentista_id,
                'data_consulta': dt.isoformat(),
                'duracao_minutos': duracao,
                'execution_unit': execution_unit,
            }
        )
        flash('Consulta agendada com sucesso! ✅', 'success')
    except Exception as e:
        flash_internal_error('Falha ao agendar consulta')

    # Redireciona para a semana da consulta criada
    week_start = dt.date() - timedelta(days=dt.weekday())
    return redirect(url_for('agenda.agenda_index', semana=week_start.isoformat()))


@agenda_bp.route('/<int:consulta_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_consulta(consulta_id):
    if not _can_manage():
        flash('Sem permissão para editar consultas.', 'danger')
        return redirect(url_for('agenda.agenda_index'))

    consulta = _get_scoped_consulta(consulta_id, include_patient=True)
    if not consulta:
        flash('Consulta não encontrada ou fora do seu escopo de acesso.', 'danger')
        return redirect(url_for('agenda.agenda_index'))

    if request.method == 'POST':
        patient_id = request.form.get('patient_id', type=int)
        dentista_id = _resolve_dentista_id(request.form.get('dentista_id', type=int))
        data_hora = request.form.get('data_consulta')
        duracao = request.form.get('duracao_minutos', 30, type=int)
        status = request.form.get('status', 'Pendente')
        execution_unit = normalize_execution_unit(request.form.get('execution_unit')) or get_default_execution_unit()
        observacoes = request.form.get('observacoes', '')
        status_validos = ('Pendente', 'Confirmado', 'Realizado', 'Cancelado', 'Faltou')
        if not all([patient_id, dentista_id, data_hora]):
            flash('Paciente, dentista e data/hora são obrigatórios.', 'danger')
            return redirect(url_for('agenda.editar_consulta', consulta_id=consulta_id))
        if not _can_use_dentista_id(dentista_id):
            flash('Profissional inválido para o seu perfil de acesso.', 'danger')
            return redirect(url_for('agenda.editar_consulta', consulta_id=consulta_id))
        if status not in status_validos:
            flash('Status inválido.', 'danger')
            return redirect(url_for('agenda.editar_consulta', consulta_id=consulta_id))

        try:
            dt = datetime.strptime(data_hora, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Formato de data/hora inválido.', 'danger')
            return redirect(url_for('agenda.editar_consulta', consulta_id=consulta_id))

        try:
            execute(
                """
                UPDATE consultas
                SET patient_id=%s, dentista_id=%s, data_consulta=%s,
                    duracao_minutos=%s, status=%s, execution_unit=%s, observacoes=%s
                WHERE id=%s
                """,
                (patient_id, dentista_id, dt, duracao, status, execution_unit, observacoes, consulta_id),
            )
            audit_log(
                action='appointment_updated',
                module='agenda',
                entity_type='consulta',
                entity_id=consulta_id,
                patient_id=patient_id,
                details={
                    'previous_status': consulta['status'],
                    'new_status': status,
                    'previous_date': consulta['data_consulta'],
                    'new_date': dt.isoformat(),
                    'execution_unit': execution_unit,
                }
            )
            flash('Consulta atualizada com sucesso! ✅', 'success')
        except Exception as e:
            flash_internal_error('Falha ao atualizar consulta')

        week_start = dt.date() - timedelta(days=dt.weekday())
        return redirect(url_for('agenda.agenda_index', semana=week_start.isoformat()))

    dentistas = _list_visible_dentistas()
    patients = query("SELECT id, nome FROM patients ORDER BY nome ASC")
    return render_template(
        'agenda/editar.html',
        consulta=consulta,
        dentistas=dentistas,
        patients=patients,
        execution_units=get_execution_unit_choices(),
        agenda_scope=_agenda_scope(),
    )


@agenda_bp.route('/<int:consulta_id>/cancelar', methods=['POST'])
@login_required
def cancelar_consulta(consulta_id):
    if not _can_manage():
        flash('Sem permissão para cancelar consultas.', 'danger')
        return redirect(url_for('agenda.agenda_index'))

    consulta = _get_scoped_consulta(consulta_id)
    if not consulta:
        flash('Consulta não encontrada ou fora do seu escopo de acesso.', 'danger')
        return redirect(url_for('agenda.agenda_index'))

    try:
        execute("UPDATE consultas SET status = 'Cancelado' WHERE id = %s", (consulta_id,))
        audit_log(
            action='appointment_canceled',
            module='agenda',
            entity_type='consulta',
            entity_id=consulta_id,
            patient_id=consulta['patient_id'],
            details={'previous_status': consulta['status'], 'new_status': 'Cancelado'}
        )
        flash('Consulta cancelada.', 'success')
    except Exception as e:
        flash_internal_error('Falha ao cancelar consulta')

    dt = consulta['data_consulta']
    week_start = dt.date() - timedelta(days=dt.weekday())
    return redirect(url_for('agenda.agenda_index', semana=week_start.isoformat()))


@agenda_bp.route('/<int:consulta_id>/status', methods=['POST'])
@login_required
def atualizar_status(consulta_id):
    if not _can_manage():
        return jsonify({'error': 'Sem permissão'}), 403

    novo_status = request.form.get('status')
    status_validos = ('Pendente', 'Confirmado', 'Realizado', 'Cancelado', 'Faltou')
    if novo_status not in status_validos:
        return jsonify({'error': 'Status inválido'}), 400

    try:
        consulta = _get_scoped_consulta(consulta_id)
        if not consulta:
            flash('Consulta não encontrada.', 'danger')
            return redirect(request.referrer or url_for('agenda.agenda_index'))

        execute("UPDATE consultas SET status = %s WHERE id = %s", (novo_status, consulta_id))
        audit_log(
            action='appointment_status_changed',
            module='agenda',
            entity_type='consulta',
            entity_id=consulta_id,
            patient_id=consulta['patient_id'],
            details={
                'previous_status': consulta['status'],
                'new_status': novo_status,
            }
        )
        flash(f'Status atualizado para "{novo_status}".', 'success')
    except Exception as e:
        flash_internal_error('Falha ao atualizar status da consulta')

    return redirect(request.referrer or url_for('agenda.agenda_index'))
