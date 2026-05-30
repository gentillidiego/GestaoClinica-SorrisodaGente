from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from database import execute, query
from datetime import datetime, timedelta
from services.security_service import audit_log

agenda_bp = Blueprint('agenda', __name__, url_prefix='/agenda')


def _get_week_range(ref_date):
    """Retorna (segunda-feira, domingo) da semana de ref_date."""
    start = ref_date - timedelta(days=ref_date.weekday())
    end = start + timedelta(days=6)
    return start, end


def _can_manage():
    """Verifica se o usuário pode criar/editar/cancelar consultas."""
    return current_user.can('agenda:write')


@agenda_bp.route('/')
@login_required
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
    dentista_id = request.args.get('dentista_id', type=int)
    status_filter = request.args.get('status', '')

    # Monta a query de consultas da semana
    sql = """
        SELECT c.id, c.data_consulta, c.duracao_minutos, c.status, c.observacoes,
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

    if status_filter:
        sql += " AND c.status = %s"
        params.append(status_filter)

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
    dentistas = query(
        "SELECT id, username, full_name FROM users WHERE role IN ('dentista', 'admin') ORDER BY full_name ASC"
    )

    # Pacientes para o modal de nova consulta
    patients = query("SELECT id, nome FROM patients ORDER BY nome ASC")

    prev_week = (week_start - timedelta(days=7)).isoformat()
    next_week = (week_start + timedelta(days=7)).isoformat()

    return render_template(
        'agenda/index.html',
        week_days=week_days,
        consultas_por_dia=consultas_por_dia,
        consultas_hoje=consultas_hoje,
        dentistas=dentistas,
        patients=patients,
        today=today,
        week_start=week_start,
        week_end=week_end,
        prev_week=prev_week,
        next_week=next_week,
        dentista_id_filter=dentista_id,
        status_filter=status_filter,
    )


@agenda_bp.route('/nova', methods=['POST'])
@login_required
def nova_consulta():
    if not _can_manage():
        flash('Sem permissão para criar consultas.', 'danger')
        return redirect(url_for('agenda.agenda_index'))

    patient_id = request.form.get('patient_id', type=int)
    dentista_id = request.form.get('dentista_id', type=int)
    data_hora = request.form.get('data_consulta')
    duracao = request.form.get('duracao_minutos', 30, type=int)
    observacoes = request.form.get('observacoes', '')

    if not all([patient_id, dentista_id, data_hora]):
        flash('Paciente, dentista e data/hora são obrigatórios.', 'danger')
        return redirect(url_for('agenda.agenda_index'))

    try:
        dt = datetime.strptime(data_hora, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('Formato de data/hora inválido.', 'danger')
        return redirect(url_for('agenda.agenda_index'))

    try:
        consulta_id = execute(
            """
            INSERT INTO consultas (patient_id, dentista_id, data_consulta, duracao_minutos, observacoes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (patient_id, dentista_id, dt, duracao, observacoes, current_user.id),
        )
        audit_log(
            action='appointment_created',
            module='agenda',
            entity_type='consulta',
            entity_id=consulta_id,
            patient_id=patient_id,
            details={'dentista_id': dentista_id, 'data_consulta': dt.isoformat(), 'duracao_minutos': duracao}
        )
        flash('Consulta agendada com sucesso! ✅', 'success')
    except Exception as e:
        flash(f'Erro ao agendar consulta: {str(e)}', 'danger')

    # Redireciona para a semana da consulta criada
    week_start = dt.date() - timedelta(days=dt.weekday())
    return redirect(url_for('agenda.agenda_index', semana=week_start.isoformat()))


@agenda_bp.route('/<int:consulta_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_consulta(consulta_id):
    consulta = query(
        """
        SELECT c.*, p.nome as patient_nome, u.username as dentista_username
        FROM consultas c
        JOIN patients p ON c.patient_id = p.id
        JOIN users u ON c.dentista_id = u.id
        WHERE c.id = %s
        """,
        (consulta_id,), one=True
    )
    if not consulta:
        flash('Consulta não encontrada.', 'danger')
        return redirect(url_for('agenda.agenda_index'))

    if not _can_manage():
        flash('Sem permissão para editar consultas.', 'danger')
        return redirect(url_for('agenda.agenda_index'))

    if request.method == 'POST':
        patient_id = request.form.get('patient_id', type=int)
        dentista_id = request.form.get('dentista_id', type=int)
        data_hora = request.form.get('data_consulta')
        duracao = request.form.get('duracao_minutos', 30, type=int)
        status = request.form.get('status', 'Pendente')
        observacoes = request.form.get('observacoes', '')
        status_validos = ('Pendente', 'Confirmado', 'Realizado', 'Cancelado', 'Faltou')
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
                    duracao_minutos=%s, status=%s, observacoes=%s
                WHERE id=%s
                """,
                (patient_id, dentista_id, dt, duracao, status, observacoes, consulta_id),
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
                }
            )
            flash('Consulta atualizada com sucesso! ✅', 'success')
        except Exception as e:
            flash(f'Erro ao atualizar consulta: {str(e)}', 'danger')

        week_start = dt.date() - timedelta(days=dt.weekday())
        return redirect(url_for('agenda.agenda_index', semana=week_start.isoformat()))

    dentistas = query(
        "SELECT id, username, full_name FROM users WHERE role IN ('dentista', 'admin') ORDER BY full_name ASC"
    )
    patients = query("SELECT id, nome FROM patients ORDER BY nome ASC")
    return render_template('agenda/editar.html', consulta=consulta, dentistas=dentistas, patients=patients)


@agenda_bp.route('/<int:consulta_id>/cancelar', methods=['POST'])
@login_required
def cancelar_consulta(consulta_id):
    if not _can_manage():
        flash('Sem permissão para cancelar consultas.', 'danger')
        return redirect(url_for('agenda.agenda_index'))

    consulta = query("SELECT patient_id, data_consulta, status FROM consultas WHERE id = %s", (consulta_id,), one=True)
    if not consulta:
        flash('Consulta não encontrada.', 'danger')
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
        flash(f'Erro ao cancelar: {str(e)}', 'danger')

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
        consulta = query("SELECT patient_id, status FROM consultas WHERE id = %s", (consulta_id,), one=True)
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
        flash(f'Erro ao atualizar status: {str(e)}', 'danger')

    return redirect(request.referrer or url_for('agenda.agenda_index'))
