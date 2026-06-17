from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from database import execute, query

triage_bp = Blueprint('triage', __name__, url_prefix='/triagem')


def _can_manage_triage():
    return current_user.can('triage:write')


def _normalize_code(value):
    return (value or '').strip().upper()


@triage_bp.before_request
@login_required
def require_triage_access():
    if not _can_manage_triage():
        flash('Acesso negado para gerenciar a triagem.', 'danger')
        return redirect(url_for('main.dashboard'))


@triage_bp.route('/')
def list_actions():
    actions = query('''
        SELECT a.*, m.nome as municipio_nome, m.codigo as municipio_codigo,
               COUNT(s.id) as total_senhas,
               COUNT(s.id) FILTER (WHERE s.status = 'Disponível') as senhas_disponiveis,
               COUNT(s.id) FILTER (WHERE s.status = 'Entregue') as senhas_entregues,
               COUNT(s.id) FILTER (WHERE s.status = 'Vinculada') as senhas_vinculadas,
               COUNT(s.id) FILTER (WHERE s.status = 'Cancelada') as senhas_canceladas
        FROM triagem_acoes a
        JOIN municipios m ON a.municipio_id = m.id
        LEFT JOIN triagem_senhas s ON s.triagem_acao_id = a.id
        GROUP BY a.id, m.nome, m.codigo
        ORDER BY a.data_acao DESC, a.id DESC
    ''')
    return render_template(
        'triage/index.html',
        actions=actions,
    )


@triage_bp.route('/acoes/nova', methods=['GET', 'POST'])
def create_action():
    municipios = query("SELECT id, nome, codigo FROM municipios WHERE ativo = 1 ORDER BY nome")

    if request.method == 'POST':
        municipio_id = request.form.get('municipio_id', type=int)
        data_acao = request.form.get('data_acao')
        local = request.form.get('local')
        observacoes = request.form.get('observacoes')

        if not municipio_id or not data_acao:
            flash('Município e data da ação são obrigatórios.', 'danger')
            return render_template(
                'triage/action_form.html',
                municipios=municipios,
            )

        try:
            datetime.strptime(data_acao, '%Y-%m-%d')
            action_id = execute('''
                INSERT INTO triagem_acoes (municipio_id, data_acao, local, observacoes, created_by)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            ''', (municipio_id, data_acao, local, observacoes, current_user.id))
            flash('Ação de triagem criada com sucesso.', 'success')
            return redirect(url_for('triage.view_action', action_id=action_id))
        except ValueError:
            flash('Data da ação inválida.', 'danger')
        except Exception as e:
            flash(f'Erro ao criar ação de triagem: {str(e)}', 'danger')

    return render_template(
        'triage/action_form.html',
        municipios=municipios,
    )


@triage_bp.route('/acoes/<int:action_id>')
def view_action(action_id):
    action = query('''
        SELECT a.*, m.nome as municipio_nome, m.codigo as municipio_codigo
        FROM triagem_acoes a
        JOIN municipios m ON a.municipio_id = m.id
        WHERE a.id = %s
    ''', (action_id,), one=True)

    if not action:
        flash('Ação de triagem não encontrada.', 'danger')
        return redirect(url_for('triage.list_actions'))

    patient_q = (request.args.get('paciente') or '').strip()
    if patient_q:
        patient_search = f"%{patient_q}%"
        patient_options = query('''
            SELECT id, nome, cpf, cns, data_nascimento
            FROM patients
            WHERE nome ILIKE %s OR cpf ILIKE %s OR cns ILIKE %s
            ORDER BY nome ASC
            LIMIT 80
        ''', (patient_search, patient_search, patient_search))
    else:
        patient_options = query('''
            SELECT id, nome, cpf, cns, data_nascimento
            FROM patients
            ORDER BY id DESC
            LIMIT 120
        ''')

    especialidades = query("SELECT id, nome, codigo FROM especialidades WHERE ativo = 1 ORDER BY nome")
    summary = query('''
        SELECT e.id, e.nome, e.codigo,
               COUNT(s.id) as total,
               COUNT(s.id) FILTER (WHERE s.status = 'Disponível') as disponiveis,
               COUNT(s.id) FILTER (WHERE s.status = 'Entregue') as entregues,
               COUNT(s.id) FILTER (WHERE s.status = 'Vinculada') as vinculadas,
               COUNT(s.id) FILTER (WHERE s.status = 'Cancelada') as canceladas
        FROM especialidades e
        LEFT JOIN triagem_senhas s
          ON s.especialidade_id = e.id AND s.triagem_acao_id = %s
        WHERE e.ativo = 1
        GROUP BY e.id, e.nome, e.codigo
        ORDER BY e.nome
    ''', (action_id,))
    tickets = query('''
        SELECT s.*, e.nome as especialidade_nome, e.codigo as especialidade_codigo,
               p.nome as patient_nome,
               COALESCE(eu.name, planned.execution_unit) as execution_unit_label,
               planned.data_consulta as scheduled_at,
               planned.status as appointment_status
        FROM triagem_senhas s
        JOIN especialidades e ON s.especialidade_id = e.id
        LEFT JOIN patients p ON s.patient_id = p.id
        LEFT JOIN LATERAL (
            SELECT c.execution_unit, c.data_consulta, c.status
            FROM consultas c
            WHERE c.patient_id = s.patient_id
              AND c.status NOT IN ('Cancelado', 'Faltou')
            ORDER BY
              CASE WHEN c.data_consulta >= NOW() THEN 0 ELSE 1 END,
              CASE WHEN c.data_consulta >= NOW() THEN c.data_consulta END ASC,
              c.data_consulta DESC
            LIMIT 1
        ) planned ON TRUE
        LEFT JOIN execution_units eu ON eu.code = planned.execution_unit
        WHERE s.triagem_acao_id = %s
        ORDER BY e.nome, s.numero
    ''', (action_id,))

    return render_template(
        'triage/action_detail.html',
        action=action,
        especialidades=especialidades,
        patient_options=patient_options,
        patient_q=patient_q,
        summary=summary,
        tickets=tickets,
        generated_ticket=_normalize_code(request.args.get('senha_gerada')),
        generated_patient=query(
            "SELECT id, nome FROM patients WHERE id = %s",
            (request.args.get('paciente_id', type=int),),
            one=True,
        ) if request.args.get('paciente_id', type=int) else None,
    )


@triage_bp.route('/acoes/<int:action_id>/gerar', methods=['POST'])
def generate_tickets(action_id):
    action = query('''
        SELECT a.*, m.codigo as municipio_codigo
        FROM triagem_acoes a
        JOIN municipios m ON a.municipio_id = m.id
        WHERE a.id = %s
    ''', (action_id,), one=True)
    if not action:
        flash('Ação de triagem não encontrada.', 'danger')
        return redirect(url_for('triage.list_actions'))

    especialidade_id = request.form.get('especialidade_id', type=int)
    patient_id = request.form.get('patient_id', type=int)
    if not patient_id:
        flash('Selecione o paciente já cadastrado para vincular a senha.', 'danger')
        return redirect(url_for('triage.view_action', action_id=action_id))

    patient = query("SELECT id, nome FROM patients WHERE id = %s", (patient_id,), one=True)
    if not patient:
        flash('Paciente não encontrado. Cadastre o paciente antes de gerar a senha.', 'danger')
        return redirect(url_for('triage.view_action', action_id=action_id))

    if not especialidade_id:
        flash('Informe a especialidade para gerar a senha.', 'danger')
        return redirect(url_for('triage.view_action', action_id=action_id))

    especialidade = query("SELECT id, codigo FROM especialidades WHERE id = %s AND ativo = 1", (especialidade_id,), one=True)
    if not especialidade:
        flash('Especialidade inválida.', 'danger')
        return redirect(url_for('triage.view_action', action_id=action_id))

    last = query('''
        SELECT COALESCE(MAX(numero), 0) as ultimo
        FROM triagem_senhas
        WHERE municipio_id = %s AND especialidade_id = %s
    ''', (action['municipio_id'], especialidade_id), one=True)
    numero = (last['ultimo'] or 0) + 1
    codigo = f"{action['municipio_codigo']}-{especialidade['codigo']}-{numero:03d}"

    try:
        execute('''
            INSERT INTO triagem_senhas (
                triagem_acao_id, municipio_id, especialidade_id, numero, codigo,
                status, patient_id, vinculada_em
            ) VALUES (%s, %s, %s, %s, %s, 'Vinculada', %s, CURRENT_TIMESTAMP)
        ''', (action_id, action['municipio_id'], especialidade_id, numero, codigo, patient_id))
        flash(f'Senha {codigo} gerada e vinculada a {patient["nome"]}.', 'success')
        return redirect(url_for(
            'triage.view_action',
            action_id=action_id,
            senha_gerada=codigo,
            paciente_id=patient_id,
        ))
    except Exception as e:
        flash(f'Erro ao gerar senhas: {str(e)}', 'danger')

    return redirect(url_for('triage.view_action', action_id=action_id))


@triage_bp.route('/senhas')
def list_tickets():
    q = _normalize_code(request.args.get('q'))
    status = request.args.get('status') or ''
    especialidade_id = request.args.get('especialidade_id', type=int)
    municipio_id = request.args.get('municipio_id', type=int)

    sql = '''
        SELECT s.*, e.nome as especialidade_nome, m.nome as municipio_nome,
               a.data_acao, p.nome as patient_nome,
               COALESCE(eu.name, planned.execution_unit) as execution_unit_label,
               planned.data_consulta as scheduled_at,
               planned.status as appointment_status
        FROM triagem_senhas s
        JOIN especialidades e ON s.especialidade_id = e.id
        JOIN municipios m ON s.municipio_id = m.id
        JOIN triagem_acoes a ON s.triagem_acao_id = a.id
        LEFT JOIN patients p ON s.patient_id = p.id
        LEFT JOIN LATERAL (
            SELECT c.execution_unit, c.data_consulta, c.status
            FROM consultas c
            WHERE c.patient_id = s.patient_id
              AND c.status NOT IN ('Cancelado', 'Faltou')
            ORDER BY
              CASE WHEN c.data_consulta >= NOW() THEN 0 ELSE 1 END,
              CASE WHEN c.data_consulta >= NOW() THEN c.data_consulta END ASC,
              c.data_consulta DESC
            LIMIT 1
        ) planned ON TRUE
        LEFT JOIN execution_units eu ON eu.code = planned.execution_unit
        WHERE 1=1
    '''
    params = []
    if q:
        sql += " AND s.codigo ILIKE %s"
        params.append(f"%{q}%")
    if status:
        sql += " AND s.status = %s"
        params.append(status)
    if especialidade_id:
        sql += " AND s.especialidade_id = %s"
        params.append(especialidade_id)
    if municipio_id:
        sql += " AND s.municipio_id = %s"
        params.append(municipio_id)
    sql += " ORDER BY s.criado_em DESC, s.id DESC LIMIT 500"

    tickets = query(sql, tuple(params))
    especialidades = query("SELECT id, nome FROM especialidades WHERE ativo = 1 ORDER BY nome")
    municipios = query("SELECT id, nome FROM municipios WHERE ativo = 1 ORDER BY nome")
    return render_template(
        'triage/tickets.html',
        tickets=tickets,
        especialidades=especialidades,
        municipios=municipios,
        q=q,
        status=status,
        especialidade_id=especialidade_id,
        municipio_id=municipio_id,
    )


@triage_bp.route('/senhas/<int:ticket_id>/status', methods=['POST'])
def update_ticket_status(ticket_id):
    new_status = request.form.get('status')
    valid_statuses = ('Disponível', 'Entregue', 'Cancelada')
    if new_status not in valid_statuses:
        flash('Status inválido para a senha.', 'danger')
        return redirect(request.referrer or url_for('triage.list_tickets'))

    ticket = query("SELECT patient_id FROM triagem_senhas WHERE id = %s", (ticket_id,), one=True)
    if not ticket:
        flash('Senha não encontrada.', 'danger')
        return redirect(request.referrer or url_for('triage.list_tickets'))
    if ticket['patient_id']:
        flash('Senha já vinculada a paciente não pode ter status alterado manualmente.', 'danger')
        return redirect(request.referrer or url_for('triage.list_tickets'))

    if new_status == 'Entregue':
        execute("UPDATE triagem_senhas SET status = %s, entregue_em = CURRENT_TIMESTAMP WHERE id = %s", (new_status, ticket_id))
    else:
        execute("UPDATE triagem_senhas SET status = %s WHERE id = %s", (new_status, ticket_id))
    flash('Status da senha atualizado.', 'success')
    return redirect(request.referrer or url_for('triage.list_tickets'))
