import json
import os
import secrets

from flask import Blueprint, Response, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from database import query, execute, execute_returning
from functools import wraps
from constants import (
    Role,
    get_role_choices,
    role_requires_dental_license,
    role_requires_professional_data,
)
from services.security_service import audit_log, list_audit_logs, permission_required
from services.cost_reference_service import (
    get_cost_reference_dashboard,
    import_cost_references_csv,
    update_cost_reference as save_cost_reference,
)
from services.esus_export_service import (
    get_esus_batch_detail,
    get_esus_dashboard,
    get_esus_homologation_report,
    register_esus_export_batch,
    simulate_esus_transmission_preflight,
    update_esus_settings,
    update_treatment_sigtap,
    validate_esus_export_batch,
)
from services.inventory_service import (
    create_inventory_item,
    create_inventory_lot,
    get_inventory_dashboard,
    register_inventory_adjustment,
)
from services.execution_unit_service import (
    ExecutionUnitError,
    MAX_ACTIVE_EXECUTION_UNITS,
    create_execution_unit,
    get_execution_unit,
    list_execution_units,
    update_execution_unit,
)
from services.professional_registration_service import list_registration_requests
from services.professional_registration_service import (
    RegistrationApprovalError,
    approve_registration_request,
    reject_registration_request,
    send_registration_approved_email,
    send_registration_rejected_email,
)
from services.sigtap_service import build_sigtap_options, get_sigtap_summary
from services.sensitive_file_service import SENSITIVE_CACHE_HEADERS
from tasks.pdf_tasks import generate_pdf_task

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
    """Permite visualização da lista de usuários conforme permissão."""
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


def _decode_uploaded_csv(file_storage):
    raw = file_storage.read()
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return raw.decode('latin-1')


def _cost_reference_form_payload():
    return {
        'sigtap_code': request.form.get('sigtap_code'),
        'sigtap_name': request.form.get('sigtap_name'),
        'public_cost': request.form.get('public_cost'),
        'private_reference': request.form.get('private_reference'),
        'reference_label': request.form.get('reference_label'),
        'source': request.form.get('source'),
        'methodology_status': request.form.get('methodology_status'),
        'notes': request.form.get('notes'),
        'active': request.form.get('active'),
        'validation_notes': request.form.get('validation_notes'),
    }


def _inventory_item_form_payload():
    return {
        'name': request.form.get('name'),
        'category': request.form.get('category'),
        'unit': request.form.get('unit'),
        'min_quantity': request.form.get('min_quantity'),
        'center_cost': request.form.get('center_cost'),
        'notes': request.form.get('notes'),
        'active': request.form.get('active') or '1',
    }


def _inventory_lot_form_payload():
    return {
        'item_id': request.form.get('item_id'),
        'supplier_name': request.form.get('supplier_name'),
        'lot_number': request.form.get('lot_number'),
        'expiration_date': request.form.get('expiration_date'),
        'quantity_initial': request.form.get('quantity_initial'),
        'unit_cost': request.form.get('unit_cost'),
        'received_at': request.form.get('received_at'),
        'center_cost': request.form.get('center_cost'),
        'notes': request.form.get('notes'),
    }


def _inventory_adjustment_form_payload():
    return {
        'lot_id': request.form.get('lot_id'),
        'adjustment_type': request.form.get('adjustment_type'),
        'quantity': request.form.get('quantity'),
        'reason': request.form.get('reason'),
        'notes': request.form.get('notes'),
    }


def _execution_unit_form_payload(include_code=False):
    payload = {
        'name': request.form.get('name'),
        'cnes': request.form.get('cnes'),
        'address': request.form.get('address'),
        'notes': request.form.get('notes'),
        'active': request.form.get('active') == '1',
        'is_default': request.form.get('is_default') == '1',
    }
    if include_code:
        payload['code'] = request.form.get('code')
    return payload


def _audit_cost_reference_change(action, change, status='success', extra=None):
    reference = change.get('reference') or {}
    details = {
        'sigtap_code': change.get('new', {}).get('sigtap_code') or reference.get('sigtap_code'),
        'created': change.get('created'),
        'changed_fields': change.get('changed_fields'),
    }
    if extra:
        details.update(extra)
    audit_log(
        action=action,
        module='financeiro',
        entity_type='procedure_cost_references',
        entity_id=reference.get('id'),
        status=status,
        details=details,
    )

@admin_bp.route('/users')
@login_required
@admin_or_atendente_required
def list_users():
    users = query("""
        SELECT id, username, role, full_name, email, data_nascimento, is_first_access, active, last_login_at, last_login_ip,
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
        email = _clean_form_value('email').lower()
        celular = _clean_form_value('celular')
        data_nascimento = _clean_form_value('data_nascimento') or None
        is_first_access = request.form.get('is_first_access') == '1'
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

        if is_first_access and not data_nascimento:
            flash('Data de nascimento é obrigatória para usuário em primeiro acesso.', 'danger')
            return render_template('admin/add_user.html', role_choices=get_role_choices())

        if not is_first_access and not password:
            flash('Informe a senha inicial ou marque o fluxo de primeiro acesso.', 'danger')
            return render_template('admin/add_user.html', role_choices=get_role_choices())

        hashed_password = generate_password_hash(password or secrets.token_urlsafe(24))

        try:
            user_id = execute_returning(
                """
                INSERT INTO users (
                    username, password, role, full_name, email, celular, data_nascimento,
                    is_first_access, cro, cro_uf, cns, cbo, cnes, ine, active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    username, hashed_password, role, full_name, email or None, celular or None,
                    data_nascimento, is_first_access, cro, cro_uf, cns, cbo, cnes, ine, active,
                )
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
                    'is_first_access': is_first_access,
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
        SELECT id, username, role, full_name, email, celular, data_nascimento,
               is_first_access, cro, cro_uf, cns, cbo, cnes, ine, active
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
        email = _clean_form_value('email').lower()
        celular = _clean_form_value('celular')
        data_nascimento = _clean_form_value('data_nascimento') or None
        is_first_access = request.form.get('is_first_access') == '1'
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
                'email': email,
                'celular': celular,
                'data_nascimento': data_nascimento,
                'is_first_access': is_first_access,
                'cro': cro,
                'cro_uf': cro_uf,
                'cns': cns,
                'cbo': cbo,
                'cnes': cnes,
                'ine': ine,
                'active': active,
            })
            return render_template('admin/edit_user.html', user=form_user, role_choices=get_role_choices())

        if is_first_access and not data_nascimento:
            flash('Data de nascimento é obrigatória para usuário em primeiro acesso.', 'danger')
            form_user = dict(user)
            form_user.update({
                'username': username,
                'role': role,
                'full_name': full_name,
                'email': email,
                'celular': celular,
                'data_nascimento': data_nascimento,
                'is_first_access': is_first_access,
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
                    SET username=%s, password=%s, role=%s, full_name=%s, email=%s, celular=%s,
                        data_nascimento=%s, is_first_access=%s, cro=%s, cro_uf=%s,
                        cns=%s, cbo=%s, cnes=%s, ine=%s, active=%s
                    WHERE id=%s
                    """,
                    (
                        username, hashed_password, role, full_name, email or None, celular or None,
                        data_nascimento, is_first_access, cro, cro_uf, cns, cbo, cnes, ine, active, user_id,
                    )
                )
            else:
                execute(
                    """
                    UPDATE users
                    SET username=%s, role=%s, full_name=%s, email=%s, celular=%s,
                        data_nascimento=%s, is_first_access=%s, cro=%s, cro_uf=%s,
                        cns=%s, cbo=%s, cnes=%s, ine=%s, active=%s
                    WHERE id=%s
                    """,
                    (
                        username, role, full_name, email or None, celular or None, data_nascimento,
                        is_first_access, cro, cro_uf, cns, cbo, cnes, ine, active, user_id,
                    )
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
                    'is_first_access': is_first_access,
                    'password_changed': bool(password)
                }
            )
            flash(f'Usuário {full_name or username} atualizado com sucesso!', 'success')
            return redirect(url_for('admin.list_users'))
        except Exception as e:
            flash(f'Erro ao atualizar usuário: {str(e)}', 'danger')

    return render_template('admin/edit_user.html', user=user, role_choices=get_role_choices())


@admin_bp.route('/execution-units')
@login_required
@admin_required
def execution_units():
    units = list_execution_units(include_inactive=True, with_usage=True)
    active_count = sum(1 for unit in units if unit.get('active'))
    return render_template(
        'admin/execution_units.html',
        units=units,
        active_count=active_count,
        max_active_units=MAX_ACTIVE_EXECUTION_UNITS,
    )


@admin_bp.route('/execution-units/create', methods=['POST'])
@login_required
@admin_required
def create_execution_unit_route():
    try:
        unit = create_execution_unit(_execution_unit_form_payload(include_code=True))
        audit_log(
            action='execution_unit_created',
            module='admin',
            entity_type='execution_units',
            entity_id=unit['id'],
            details={
                'code': unit['code'],
                'name': unit['name'],
                'active': unit['active'],
                'is_default': unit['is_default'],
            },
        )
        flash('Unidade criada com sucesso.', 'success')
    except ExecutionUnitError as exc:
        flash(str(exc), 'danger')
    except Exception as exc:
        flash(f'Erro ao criar unidade: {str(exc)}', 'danger')
    return redirect(url_for('admin.execution_units'))


@admin_bp.route('/execution-units/<int:unit_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_execution_unit(unit_id):
    unit = get_execution_unit(unit_id)
    if not unit:
        flash('Unidade não encontrada.', 'danger')
        return redirect(url_for('admin.execution_units'))

    if request.method == 'POST':
        try:
            updated = update_execution_unit(unit_id, _execution_unit_form_payload())
            audit_log(
                action='execution_unit_updated',
                module='admin',
                entity_type='execution_units',
                entity_id=unit_id,
                details={
                    'code': updated['code'],
                    'previous_name': unit['name'],
                    'new_name': updated['name'],
                    'active': updated['active'],
                    'is_default': updated['is_default'],
                },
            )
            flash('Unidade atualizada com sucesso.', 'success')
            return redirect(url_for('admin.execution_units'))
        except ExecutionUnitError as exc:
            flash(str(exc), 'danger')
        except Exception as exc:
            flash(f'Erro ao atualizar unidade: {str(exc)}', 'danger')

    return render_template('admin/edit_execution_unit.html', unit=unit)


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
        'ip_address': request.args.get('ip_address') or None,
        'created_from': request.args.get('created_from') or None,
        'created_to': request.args.get('created_to') or None,
        'severity': request.args.get('severity') or None,
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


@admin_bp.route('/professional-registrations')
@login_required
@permission_required('users:view')
def professional_registrations():
    registrations = list_registration_requests(limit=300)
    return render_template('admin/professional_registrations.html', registrations=registrations)


@admin_bp.route('/professional-registrations/<int:registration_id>/approve', methods=['POST'])
@login_required
@permission_required('users:write')
def approve_professional_registration(registration_id):
    try:
        registration = approve_registration_request(registration_id, current_user.id)
        audit_log(
            action='professional_registration_approved',
            module='admin',
            entity_type='professional_registration_requests',
            entity_id=registration_id,
            details={
                'created_user_id': registration.get('created_user_id'),
                'desired_username': registration.get('desired_username'),
                'requested_role': registration.get('requested_role'),
            },
        )
        try:
            send_registration_approved_email(registration)
            flash('Pre-cadastro aprovado, usuario criado e e-mail de liberacao enviado.', 'success')
        except Exception as exc:
            flash(f'Pre-cadastro aprovado, mas nao foi possivel enviar o e-mail: {str(exc)}', 'warning')
    except RegistrationApprovalError as exc:
        flash(str(exc), 'danger')
    except Exception as exc:
        flash(f'Erro ao aprovar pre-cadastro: {str(exc)}', 'danger')
    return redirect(url_for('admin.professional_registrations'))


@admin_bp.route('/professional-registrations/<int:registration_id>/reject', methods=['POST'])
@login_required
@permission_required('users:write')
def reject_professional_registration(registration_id):
    try:
        review_notes = request.form.get('review_notes')
        if not (review_notes or '').strip():
            flash('Informe o motivo da recusa para enviar ao profissional.', 'danger')
            return redirect(url_for('admin.professional_registrations'))

        registration = reject_registration_request(
            registration_id,
            current_user.id,
            review_notes=review_notes,
        )
        audit_log(
            action='professional_registration_rejected',
            module='admin',
            entity_type='professional_registration_requests',
            entity_id=registration_id,
            details={
                'desired_username': registration.get('desired_username'),
                'requested_role': registration.get('requested_role'),
                'review_notes': registration.get('review_notes'),
            },
        )
        try:
            send_registration_rejected_email(registration)
            flash('Pre-cadastro recusado e e-mail com observacoes enviado.', 'success')
        except Exception as exc:
            flash(f'Pre-cadastro recusado, mas nao foi possivel enviar o e-mail: {str(exc)}', 'warning')
    except RegistrationApprovalError as exc:
        flash(str(exc), 'danger')
    except Exception as exc:
        flash(f'Erro ao recusar pre-cadastro: {str(exc)}', 'danger')
    return redirect(url_for('admin.professional_registrations'))


@admin_bp.route('/finance/cost-references')
@login_required
@permission_required('financeiro:view')
def cost_references():
    filters = {
        'q': request.args.get('q'),
        'methodology_status': request.args.get('methodology_status'),
        'source': request.args.get('source'),
        'active': request.args.get('active'),
    }
    dashboard = get_cost_reference_dashboard(filters)
    return render_template(
        'admin/cost_references.html',
        dashboard=dashboard,
        can_write=current_user.can('financeiro:write'),
    )


@admin_bp.route('/finance/cost-references/<int:reference_id>', methods=['POST'])
@login_required
@permission_required('financeiro:write')
def update_cost_reference(reference_id):
    try:
        change = save_cost_reference(
            reference_id,
            _cost_reference_form_payload(),
            actor_id=current_user.id,
        )
        action = 'cost_reference_validated'
        if change['new'].get('methodology_status') != 'validated':
            action = 'cost_reference_updated'
        _audit_cost_reference_change(
            action,
            change,
            extra={'change_reason': request.form.get('change_reason')},
        )
        flash('Referência de custo atualizada.', 'success')
    except Exception as exc:
        audit_log(
            action='cost_reference_update_failed',
            module='financeiro',
            entity_type='procedure_cost_references',
            entity_id=reference_id,
            status='failed',
            details={'error': str(exc)},
        )
        flash(f'Erro ao atualizar referência de custo: {str(exc)}', 'danger')
    return redirect(url_for('admin.cost_references'))


@admin_bp.route('/finance/cost-references/import', methods=['POST'])
@login_required
@permission_required('financeiro:write')
def import_cost_references():
    uploaded = request.files.get('cost_csv')
    if not uploaded or not uploaded.filename:
        flash('Selecione um arquivo CSV para importar.', 'danger')
        return redirect(url_for('admin.cost_references'))

    try:
        content = _decode_uploaded_csv(uploaded)
        result = import_cost_references_csv(content, actor_id=current_user.id)
    except Exception as exc:
        audit_log(
            action='cost_reference_import_failed',
            module='financeiro',
            entity_type='procedure_cost_references',
            status='failed',
            details={'filename': uploaded.filename, 'error': str(exc)},
        )
        flash(f'Erro ao importar CSV: {str(exc)}', 'danger')
        return redirect(url_for('admin.cost_references'))

    if result['errors']:
        audit_log(
            action='cost_reference_import_rejected',
            module='financeiro',
            entity_type='procedure_cost_references',
            status='failed',
            details={'filename': uploaded.filename, 'errors': result['errors'][:20]},
        )
        flash('CSV rejeitado. Corrija as linhas indicadas antes de importar.', 'danger')
        for error in result['errors'][:5]:
            flash(error, 'warning')
        return redirect(url_for('admin.cost_references'))

    audit_log(
        action='cost_reference_import_completed',
        module='financeiro',
        entity_type='procedure_cost_references',
        details={
            'filename': uploaded.filename,
            'imported': result['imported'],
            'created': result['created'],
            'updated': result['updated'],
        },
    )
    for change in result['changes']:
        action = 'cost_reference_import_created' if change['created'] else 'cost_reference_import_updated'
        _audit_cost_reference_change(
            action,
            change,
            extra={'filename': uploaded.filename},
        )

    flash(
        f"CSV importado: {result['imported']} referência(s), "
        f"{result['created']} nova(s) e {result['updated']} atualizada(s).",
        'success',
    )
    return redirect(url_for('admin.cost_references'))


@admin_bp.route('/inventory')
@login_required
@permission_required('inventory:view')
def inventory():
    dashboard = get_inventory_dashboard({
        'q': request.args.get('q'),
        'category': request.args.get('category'),
    })
    return render_template(
        'admin/inventory.html',
        dashboard=dashboard,
        can_write=current_user.can('inventory:write'),
    )


@admin_bp.route('/inventory/items', methods=['POST'])
@login_required
@permission_required('inventory:write')
def create_inventory_item_route():
    try:
        item_id = create_inventory_item(_inventory_item_form_payload(), actor_id=current_user.id)
        audit_log(
            action='inventory_item_created',
            module='inventory',
            entity_type='inventory_items',
            entity_id=item_id,
            details={
                'name': request.form.get('name'),
                'category': request.form.get('category'),
                'min_quantity': request.form.get('min_quantity'),
            },
        )
        flash('Material cadastrado no estoque.', 'success')
    except Exception as exc:
        audit_log(
            action='inventory_item_create_failed',
            module='inventory',
            entity_type='inventory_items',
            status='failed',
            details={'error': str(exc), 'name': request.form.get('name')},
        )
        flash(f'Erro ao cadastrar material: {str(exc)}', 'danger')
    return redirect(url_for('admin.inventory'))


@admin_bp.route('/inventory/lots', methods=['POST'])
@login_required
@permission_required('inventory:write')
def create_inventory_lot_route():
    try:
        lot_id = create_inventory_lot(_inventory_lot_form_payload(), actor_id=current_user.id)
        audit_log(
            action='inventory_lot_created',
            module='inventory',
            entity_type='inventory_lots',
            entity_id=lot_id,
            details={
                'item_id': request.form.get('item_id'),
                'lot_number': request.form.get('lot_number'),
                'quantity_initial': request.form.get('quantity_initial'),
                'expiration_date': request.form.get('expiration_date'),
            },
        )
        flash('Lote registrado no estoque.', 'success')
    except Exception as exc:
        audit_log(
            action='inventory_lot_create_failed',
            module='inventory',
            entity_type='inventory_lots',
            status='failed',
            details={'error': str(exc), 'lot_number': request.form.get('lot_number')},
        )
        flash(f'Erro ao registrar lote: {str(exc)}', 'danger')
    return redirect(url_for('admin.inventory'))


@admin_bp.route('/inventory/adjustments', methods=['POST'])
@login_required
@permission_required('inventory:write')
def create_inventory_adjustment_route():
    password = request.form.get('authorizer_password')
    user_data = query("SELECT password FROM users WHERE id = %s", (current_user.id,), one=True)
    if not password or not user_data or not check_password_hash(user_data['password'], password):
        audit_log(
            action='inventory_adjustment_authorization_failed',
            module='inventory',
            entity_type='inventory_adjustments',
            status='failed',
            details={
                'lot_id': request.form.get('lot_id'),
                'adjustment_type': request.form.get('adjustment_type'),
            },
        )
        flash('Senha de autorização inválida para ajuste de estoque.', 'danger')
        return redirect(url_for('admin.inventory'))

    try:
        result = register_inventory_adjustment(
            _inventory_adjustment_form_payload(),
            actor_id=current_user.id,
            authorized_by=current_user.id,
        )
        audit_log(
            action='inventory_adjustment_registered',
            module='inventory',
            entity_type='inventory_adjustments',
            entity_id=result['adjustment_id'],
            details={
                'item_id': result['item_id'],
                'item_name': result['item_name'],
                'lot_id': result['lot_id'],
                'lot_number': result['lot_number'],
                'adjustment_type': result['adjustment_type'],
                'quantity': str(result['quantity']),
                'previous_quantity': str(result['previous_quantity']),
                'new_quantity': str(result['new_quantity']),
                'reason': result['reason'],
            },
        )
        flash('Ajuste de estoque registrado com autorização.', 'success')
    except Exception as exc:
        audit_log(
            action='inventory_adjustment_register_failed',
            module='inventory',
            entity_type='inventory_adjustments',
            status='failed',
            details={
                'error': str(exc),
                'lot_id': request.form.get('lot_id'),
                'adjustment_type': request.form.get('adjustment_type'),
            },
        )
        flash(f'Erro ao registrar ajuste: {str(exc)}', 'danger')
    return redirect(url_for('admin.inventory'))


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
    response = Response(
        payload_json,
        mimetype='application/json; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
    response.headers.update(SENSITIVE_CACHE_HEADERS)
    return response


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


@admin_bp.route('/integrations/esus/batches/<int:batch_id>/preflight', methods=['POST'])
@login_required
@permission_required('integrations:write')
def simulate_esus_preflight(batch_id):
    try:
        result = simulate_esus_transmission_preflight(batch_id, attempted_by=current_user.id)
        audit_log(
            action='esus_batch_preflight_simulated',
            module='integrations',
            entity_type='esus_export_batch',
            entity_id=batch_id,
            status='success' if result['ready_to_send'] else 'blocked',
            details={
                'attempt_id': result['attempt_id'],
                'ready_to_send': result['ready_to_send'],
                'blockers': result['response'].get('blockers', []),
            },
        )
        if result['ready_to_send']:
            flash('Pré-envio simulado aprovado. Lote marcado como pronto para envio real.', 'success')
        else:
            flash('Pré-envio simulado bloqueado. Revise as pendências exibidas no lote.', 'warning')
    except Exception as exc:
        flash(f'Erro no pré-envio simulado: {str(exc)}', 'danger')
    return redirect(url_for('admin.esus_batch_detail', batch_id=batch_id))


@admin_bp.route('/integrations/esus/homologation-report')
@login_required
@permission_required('integrations:view')
def esus_homologation_report():
    report = get_esus_homologation_report(
        month_value=request.args.get('month') or None,
        batch_id=request.args.get('batch_id') or None,
    )
    audit_log(
        action='esus_homologation_report_opened',
        module='integrations',
        entity_type='esus_homologation_report',
        entity_id=report['batch_detail']['batch']['id'] if report['batch_detail'] else None,
        details={
            'month': report['month'],
            'status_label': report['status_label'],
        },
    )
    return render_template('admin/esus_homologation_report.html', report=report)


@admin_bp.route('/integrations/esus/homologation-report/export', methods=['POST'])
@login_required
@permission_required('integrations:view')
def export_esus_homologation_report():
    report = get_esus_homologation_report(
        month_value=request.form.get('month') or None,
        batch_id=request.form.get('batch_id') or None,
    )
    html = render_template('pdfs/esus_homologation_report_pdf.html', report=report)
    pdf_dir = os.path.join(os.getcwd(), 'pdf_temp')
    os.makedirs(pdf_dir, exist_ok=True)
    batch_suffix = report['batch_detail']['batch']['id'] if report['batch_detail'] else 'sem_lote'
    filename = f"esus_homologacao_{report['month']}_{batch_suffix}.pdf"
    output_path = os.path.join(pdf_dir, filename)
    task = generate_pdf_task.delay(html, output_path)

    audit_log(
        action='esus_homologation_report_exported',
        module='integrations',
        entity_type='esus_homologation_report',
        entity_id=batch_suffix,
        details={
            'month': report['month'],
            'filename': filename,
            'pending_count': len(report['pending_items']),
        },
    )
    return redirect(url_for('documents.pdf_status', task_id=task.id, filename=filename))
