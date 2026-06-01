import json

from flask import Blueprint, Response, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from database import query, execute, execute_returning
from functools import wraps
from constants import (
    Role,
    get_role_choices,
    role_requires_dental_license,
    role_requires_professional_data,
)
from services.security_service import audit_log, list_audit_logs, permission_required
from services.esus_export_service import (
    get_esus_batch_detail,
    get_esus_dashboard,
    register_esus_export_batch,
    update_esus_settings,
    update_treatment_sigtap,
    validate_esus_export_batch,
)
from services.sigtap_service import build_sigtap_options, get_sigtap_summary

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != Role.ADMIN:
            flash('Acesso negado. Apenas administradores podem acessar esta página.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def admin_or_atendente_required(f):
    """Permite visualização da lista de usuários para admin e atendente."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can('users:view'):
            flash('Acesso negado.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def _clean_form_value(name):
    return (request.form.get(name) or '').strip()


def _validate_required_professional_fields(role):
    required_fields = []
    if role_requires_professional_data(role):
        required_fields.extend([
            ('cns', 'CNS do profissional'),
            ('cbo', 'CBO'),
            ('cnes', 'CNES'),
            ('ine', 'INE/equipe'),
        ])
    if role_requires_dental_license(role):
        required_fields.extend([
            ('cro', 'CRO'),
            ('cro_uf', 'CRO-UF'),
        ])

    missing = [label for field, label in required_fields if not _clean_form_value(field)]
    if missing:
        return f"Preencha os dados obrigatórios do profissional: {', '.join(missing)}."
    return None

@admin_bp.route('/users')
@login_required
@admin_or_atendente_required
def list_users():
    users = query("""
        SELECT id, username, role, full_name, active, last_login_at, last_login_ip,
               cns, cbo, cnes, ine, cro, cro_uf
        FROM users
        ORDER BY role, username
    """)
    return render_template('admin/users.html', users=users)

@admin_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    if request.method == 'POST':
        full_name = _clean_form_value('full_name')
        username = _clean_form_value('username')
        password = request.form.get('password')
        role = request.form.get('role')
        active = request.form.get('active') == '1'
        # matricula não é mais usada — campo removido
        cro = _clean_form_value('cro')
        cro_uf = _clean_form_value('cro_uf')
        cns = _clean_form_value('cns')
        cbo = _clean_form_value('cbo')
        cnes = _clean_form_value('cnes')
        ine = _clean_form_value('ine')

        valid_roles = {role_value for role_value, _ in get_role_choices()}
        if role not in valid_roles:
            flash('Perfil de acesso inválido.', 'danger')
            return render_template('admin/add_user.html', role_choices=get_role_choices())

        validation_error = _validate_required_professional_fields(role)
        if validation_error:
            flash(validation_error, 'danger')
            return render_template('admin/add_user.html', role_choices=get_role_choices())

        hashed_password = generate_password_hash(password)

        try:
            user_id = execute_returning(
                """
                INSERT INTO users (
                    username, password, role, full_name, cro, cro_uf,
                    cns, cbo, cnes, ine, active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (username, hashed_password, role, full_name, cro, cro_uf, cns, cbo, cnes, ine, active)
            )
            audit_log(
                action='user_created',
                module='admin',
                entity_type='user',
                entity_id=user_id,
                details={
                    'username': username,
                    'role': role,
                    'active': active,
                    'professional_data_required': role_requires_professional_data(role),
                }
            )
            flash(f'Usuário {full_name or username} criado com sucesso!', 'success')
            return redirect(url_for('admin.list_users'))
        except Exception as e:
            flash(f'Erro ao criar usuário: {str(e)}', 'danger')

    return render_template('admin/add_user.html', role_choices=get_role_choices())

@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('Você não pode excluir a si mesmo.', 'danger')
    else:
        user = query("SELECT id, username, role FROM users WHERE id = %s", (user_id,), one=True)
        execute("DELETE FROM users WHERE id = %s", (user_id,))
        audit_log(
            action='user_deleted',
            module='admin',
            entity_type='user',
            entity_id=user_id,
            details={'username': user['username'], 'role': user['role']} if user else None
        )
        flash('Usuário excluído com sucesso.', 'success')
    return redirect(url_for('admin.list_users'))

@admin_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = query(
        """
        SELECT id, username, role, full_name, cro, cro_uf, cns, cbo, cnes, ine, active
        FROM users
        WHERE id = %s
        """,
        (user_id,),
        one=True,
    )
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('admin.list_users'))

    if request.method == 'POST':
        full_name = _clean_form_value('full_name')
        username = _clean_form_value('username')
        password = request.form.get('password')
        role = request.form.get('role')
        active = request.form.get('active') == '1'
        cro = _clean_form_value('cro')
        cro_uf = _clean_form_value('cro_uf')
        cns = _clean_form_value('cns')
        cbo = _clean_form_value('cbo')
        cnes = _clean_form_value('cnes')
        ine = _clean_form_value('ine')

        valid_roles = {role_value for role_value, _ in get_role_choices()}
        if role not in valid_roles:
            flash('Perfil de acesso inválido.', 'danger')
            return render_template('admin/edit_user.html', user=user, role_choices=get_role_choices())

        validation_error = _validate_required_professional_fields(role)
        if validation_error:
            flash(validation_error, 'danger')
            form_user = dict(user)
            form_user.update({
                'username': username,
                'role': role,
                'full_name': full_name,
                'cro': cro,
                'cro_uf': cro_uf,
                'cns': cns,
                'cbo': cbo,
                'cnes': cnes,
                'ine': ine,
                'active': active,
            })
            return render_template('admin/edit_user.html', user=form_user, role_choices=get_role_choices())

        try:
            if password:
                hashed_password = generate_password_hash(password)
                execute(
                    """
                    UPDATE users
                    SET username=%s, password=%s, role=%s, full_name=%s,
                        cro=%s, cro_uf=%s, cns=%s, cbo=%s, cnes=%s, ine=%s, active=%s
                    WHERE id=%s
                    """,
                    (username, hashed_password, role, full_name, cro, cro_uf, cns, cbo, cnes, ine, active, user_id)
                )
            else:
                execute(
                    """
                    UPDATE users
                    SET username=%s, role=%s, full_name=%s,
                        cro=%s, cro_uf=%s, cns=%s, cbo=%s, cnes=%s, ine=%s, active=%s
                    WHERE id=%s
                    """,
                    (username, role, full_name, cro, cro_uf, cns, cbo, cnes, ine, active, user_id)
                )
            audit_log(
                action='user_updated',
                module='admin',
                entity_type='user',
                entity_id=user_id,
                details={
                    'username': username,
                    'previous_role': user['role'],
                    'new_role': role,
                    'active': active,
                    'password_changed': bool(password)
                }
            )
            flash(f'Usuário {full_name or username} atualizado com sucesso!', 'success')
            return redirect(url_for('admin.list_users'))
        except Exception as e:
            flash(f'Erro ao atualizar usuário: {str(e)}', 'danger')

    return render_template('admin/edit_user.html', user=user, role_choices=get_role_choices())


@admin_bp.route('/audit')
@login_required
@permission_required('audit:view')
def audit_logs():
    filters = {
        'user_id': request.args.get('user_id') or None,
        'module': request.args.get('module') or None,
        'action': request.args.get('action') or None,
        'patient_id': request.args.get('patient_id') or None,
        'status': request.args.get('status') or None,
    }
    logs = list_audit_logs(filters=filters, limit=300)
    users = query("SELECT id, username, full_name FROM users ORDER BY username")
    modules = query("SELECT DISTINCT module FROM audit_logs ORDER BY module")
    return render_template(
        'admin/audit_logs.html',
        logs=logs,
        users=users,
        modules=modules,
        filters=filters,
    )


@admin_bp.route('/integrations/esus')
@login_required
@permission_required('integrations:view')
def esus_integration():
    month = request.args.get('month') or None
    dashboard = get_esus_dashboard(month)
    return render_template(
        'admin/esus_integration.html',
        dashboard=dashboard,
        sigtap_summary=get_sigtap_summary(),
        sigtap_options=build_sigtap_options(),
        can_write=current_user.can('integrations:write'),
    )


@admin_bp.route('/integrations/esus/settings', methods=['POST'])
@login_required
@permission_required('integrations:write')
def update_esus_integration_settings():
    settings_id = update_esus_settings({
        'environment': request.form.get('environment'),
        'base_url': request.form.get('base_url'),
        'pec_version': request.form.get('pec_version'),
        'ledi_version': request.form.get('ledi_version'),
        'cnes': request.form.get('cnes'),
        'ine': request.form.get('ine'),
        'installation_id': request.form.get('installation_id'),
        'client_id': request.form.get('client_id'),
        'credential_status': request.form.get('credential_status'),
        'notes': request.form.get('notes'),
        'active': request.form.get('active') == '1',
    })
    audit_log(
        action='esus_settings_updated',
        module='integrations',
        entity_type='esus_integration_settings',
        entity_id=settings_id,
        details={'environment': request.form.get('environment'), 'credential_status': request.form.get('credential_status')},
    )
    flash('Configuração e-SUS atualizada.', 'success')
    return redirect(url_for('admin.esus_integration', month=request.form.get('month') or None))


@admin_bp.route('/integrations/esus/procedure/<int:procedure_id>/sigtap', methods=['POST'])
@login_required
@permission_required('integrations:write')
def update_procedure_sigtap(procedure_id):
    try:
        sigtap = update_treatment_sigtap(
            procedure_id,
            request.form.get('sigtap_code'),
            request.form.get('sigtap_competence') or None,
        )
        audit_log(
            action='procedure_sigtap_updated',
            module='integrations',
            entity_type='tratamento_procedimentos',
            entity_id=procedure_id,
            details={'sigtap_code': sigtap['code'], 'competence': sigtap['competence']},
        )
        flash('Código SIGTAP vinculado ao procedimento.', 'success')
    except Exception as exc:
        flash(f'Erro ao vincular SIGTAP: {str(exc)}', 'danger')
    return redirect(url_for('admin.esus_integration', month=request.form.get('month') or None))


@admin_bp.route('/integrations/esus/batches', methods=['POST'])
@login_required
@permission_required('integrations:write')
def create_esus_batch():
    month = request.form.get('month') or None
    batch_id, payload = register_esus_export_batch(month, generated_by=current_user.id)
    audit_log(
        action='esus_batch_created',
        module='integrations',
        entity_type='esus_export_batch',
        entity_id=batch_id,
        details=payload.get('summary'),
    )
    flash('Lote draft e-SUS gerado para conferência.', 'success')
    return redirect(url_for('admin.esus_batch_detail', batch_id=batch_id))


@admin_bp.route('/integrations/esus/batches/<int:batch_id>')
@login_required
@permission_required('integrations:view')
def esus_batch_detail(batch_id):
    detail = get_esus_batch_detail(batch_id)
    if not detail:
        flash('Lote e-SUS não encontrado.', 'danger')
        return redirect(url_for('admin.esus_integration'))

    audit_log(
        action='esus_batch_opened',
        module='integrations',
        entity_type='esus_export_batch',
        entity_id=batch_id,
        details={
            'reference_month': detail['batch']['reference_month'],
            'status': detail['batch']['status'],
        },
    )
    return render_template(
        'admin/esus_batch_detail.html',
        detail=detail,
        can_write=current_user.can('integrations:write'),
    )


@admin_bp.route('/integrations/esus/batches/<int:batch_id>/download')
@login_required
@permission_required('integrations:view')
def download_esus_batch(batch_id):
    detail = get_esus_batch_detail(batch_id)
    if not detail:
        flash('Lote e-SUS não encontrado.', 'danger')
        return redirect(url_for('admin.esus_integration'))

    audit_log(
        action='esus_batch_downloaded',
        module='integrations',
        entity_type='esus_export_batch',
        entity_id=batch_id,
        details={
            'reference_month': detail['batch']['reference_month'],
            'status': detail['batch']['status'],
            'payload_hash': detail['batch']['payload_hash'],
        },
    )
    filename = f"esus_lote_{batch_id}_{detail['batch']['reference_month']}.json"
    payload_json = json.dumps(detail['payload'], ensure_ascii=False, indent=2, default=str)
    return Response(
        payload_json,
        mimetype='application/json; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@admin_bp.route('/integrations/esus/batches/<int:batch_id>/validate', methods=['POST'])
@login_required
@permission_required('integrations:write')
def validate_esus_batch(batch_id):
    try:
        batch = validate_esus_export_batch(
            batch_id,
            validated_by=current_user.id,
            notes=request.form.get('validation_notes'),
        )
        audit_log(
            action='esus_batch_validated_internally',
            module='integrations',
            entity_type='esus_export_batch',
            entity_id=batch_id,
            details={
                'reference_month': batch['reference_month'],
                'records_ready': batch['records_ready'],
                'payload_hash': batch['payload_hash'],
            },
        )
        flash('Lote validado internamente e bloqueado para conferência.', 'success')
    except Exception as exc:
        flash(f'Erro ao validar lote: {str(exc)}', 'danger')
    return redirect(url_for('admin.esus_batch_detail', batch_id=batch_id))
