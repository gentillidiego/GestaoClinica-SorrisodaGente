from flask import Blueprint, flash, render_template, request

from extensions import limiter
from services.professional_registration_service import (
    build_registration_payload,
    create_registration_request,
    get_public_registration_role_choices,
    role_requires_dental_license,
    role_requires_professional_documents,
    validate_registration_payload,
)
from services.security_service import audit_log, get_client_ip


professional_registration_bp = Blueprint('professional_registration', __name__)


@professional_registration_bp.route('/cadastro/', methods=['GET', 'POST'])
@limiter.limit('20 per hour')
def public_registration():
    role_choices = get_public_registration_role_choices()
    form_data = {}

    if request.method == 'POST':
        form_data = build_registration_payload(request.form)
        errors = validate_registration_payload(form_data)
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template(
                'professional_registration/public_form.html',
                form_data=form_data,
                role_choices=role_choices,
                role_requires_professional_documents=role_requires_professional_documents,
                role_requires_dental_license=role_requires_dental_license,
            ), 400

        registration_id = create_registration_request(
            form_data,
            source_ip=get_client_ip(),
            user_agent=request.headers.get('User-Agent'),
        )
        audit_log(
            action='professional_registration_submitted',
            module='professional_registration',
            entity_type='professional_registration_requests',
            entity_id=registration_id,
            details={
                'requested_role': form_data['requested_role'],
                'desired_username': form_data['desired_username'],
            },
        )
        return render_template(
            'professional_registration/submitted.html',
            protocolo=registration_id,
            email=form_data.get('email'),
        ), 201

    return render_template(
        'professional_registration/public_form.html',
        form_data=form_data,
        role_choices=role_choices,
        role_requires_professional_documents=role_requires_professional_documents,
        role_requires_dental_license=role_requires_dental_license,
    )
