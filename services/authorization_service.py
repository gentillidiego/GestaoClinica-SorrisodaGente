from dataclasses import dataclass

from flask import request


@dataclass(frozen=True)
class AccessRule:
    all_of: tuple[str, ...] = ()
    any_of: tuple[str, ...] = ()


def rule(*permissions, any_of=()):
    return AccessRule(
        all_of=tuple(permissions),
        any_of=tuple(any_of),
    )


BLUEPRINT_DEFAULTS = {
    'patients': {
        'GET': rule('patients:view'),
        'POST': rule('patients:write'),
    },
    'anamnesis': {
        'GET': rule('anamnesis:view'),
        'POST': rule('anamnesis:write'),
    },
    'exams': {
        'GET': rule('patients:view', 'exams:view'),
        'POST': rule('patients:view', 'exams:write'),
    },
    'endodontia': {
        'GET': rule('patients:view', 'endodontia:view'),
        'POST': rule('patients:view', 'endodontia:write'),
    },
    'prosthesis': {
        'GET': rule('patients:view', 'prosthesis:view'),
        'POST': rule('patients:view', 'prosthesis:write'),
    },
    'radiologia': {
        'GET': rule('radiologia:view'),
        'POST': rule('radiologia:write'),
    },
    'analises_clinicas': {
        'GET': rule('analises_clinicas:view'),
        'POST': rule('analises_clinicas:write'),
    },
}


ENDPOINT_RULES = {
    # Paciente e dados auxiliares de cadastro.
    'patients.register': {'*': rule('patients:write')},
    'patients.address_states': {'*': rule('patients:write')},
    'patients.address_cities': {'*': rule('patients:write')},
    'patients.address_neighborhoods': {'*': rule('patients:write')},
    'patients.address_cep': {'*': rule('patients:write')},
    'patients.edit_patient': {'*': rule('patients:write')},
    'patients.delete_patient': {'*': rule('patients:delete')},
    'patients.patient_tcle': {
        'GET': rule('patients:view', any_of=('documents:generate', 'documents:sign')),
        'POST': rule('patients:view', 'documents:sign'),
    },
    # Materiais.
    'patients.add_material_usage': {'*': rule('patients:view', 'inventory:write')},
    'patients.complete_material_post_op': {'*': rule('patients:view', 'inventory:write')},
    # Biblioteca visual e Estomatologia.
    'patients.serve_estomatologia_photo': {'*': rule('patients:view', 'estomatologia:view')},
    'patients.update_exam_visual_metadata': {'*': rule('patients:view', 'exams:write')},
    'patients.update_estomatologia_visual_metadata': {
        '*': rule('patients:view', 'estomatologia:write')
    },
    'patients.update_endodontia_visual_metadata': {
        '*': rule('patients:view', 'endodontia:write')
    },
    'patients.save_estomatologia': {'*': rule('patients:view', 'estomatologia:write')},
    'patients.upload_estomatologia_photo': {
        '*': rule('patients:view', 'estomatologia:write')
    },
    'patients.delete_estomatologia_photo': {
        '*': rule('patients:view', 'estomatologia:write')
    },
    'patients.red_alert_list': {'*': rule('patients:view', 'estomatologia:view')},
    # Plano de tratamento.
    'patients.add_treatment': {'*': rule('patients:view', 'treatment:write')},
    'patients.edit_treatment': {'*': rule('patients:view', 'treatment:write')},
    'patients.delete_treatment': {'*': rule('patients:view', 'treatment:write')},
    'patients.sign_treatment': {
        '*': rule('patients:view', 'treatment:write', 'documents:sign')
    },
    'patients.pending_treatments': {'*': rule('patients:view', 'treatment:view')},
    # Atendimento e assinaturas.
    'patients.add_atendimento': {'*': rule('patients:view', 'attendance:write')},
    'patients.edit_atendimento': {'*': rule('patients:view', 'attendance:write')},
    'patients.delete_atendimento': {'*': rule('patients:view', 'attendance:write')},
    'patients.sign_executor_atendimento': {
        '*': rule('patients:view', 'attendance:write', 'documents:sign')
    },
    # Anamnese: formulários de criação/edição são atos clínicos inclusive no GET.
    'anamnesis.form': {'*': rule('patients:view', 'anamnesis:write')},
    'anamnesis.edit_anamnesis': {'*': rule('patients:view', 'anamnesis:write')},
    'anamnesis.search': {'*': rule('patients:view', 'anamnesis:view')},
    'anamnesis.list_completed': {'*': rule('patients:view', 'anamnesis:view')},
    'anamnesis.view_anamnesis': {'*': rule('patients:view', 'anamnesis:view')},
    # Exames clínico/laboratoriais podem ser operados por Clínicos ou CME.
    'exams.clinico_laboratorial': {
        'GET': rule('patients:view', 'laboratorio:view'),
        'POST': rule('patients:view', 'laboratorio:write'),
    },
    'exams.visualizar': {
        '*': rule('patients:view', any_of=('exams:view', 'laboratorio:view'))
    },
    'exams.upload_clinico_laboratorial': {
        '*': rule('patients:view', 'laboratorio:write')
    },
    'exams.status_clinico_laboratorial_arquivo': {
        '*': rule('patients:view', 'laboratorio:view')
    },
    'exams.serve_clinico_laboratorial_thumbnail': {
        '*': rule('patients:view', 'laboratorio:view')
    },
    'exams.serve_clinico_laboratorial_preview': {
        '*': rule('patients:view', 'laboratorio:view')
    },
    'exams.serve_clinico_laboratorial_arquivo': {
        '*': rule('patients:view', 'laboratorio:view')
    },
    'exams.delete_exam': {'*': rule('patients:view', 'exams:delete')},
    # Solicitação de exame (fila Imagem / Clínico-Laboratorial para Radiologia).
    'exams.solicitar_tipo': {
        '*': rule('patients:view', any_of=('exams:write', 'laboratorio:write'))
    },
    'exams.solicitar_imagem': {'*': rule('patients:view', 'exams:write')},
    'exams.solicitar_clinico_laboratorial': {
        '*': rule('patients:view', 'laboratorio:write')
    },
    'exams.cancelar_solicitacao': {
        '*': rule('patients:view', any_of=('exams:write', 'laboratorio:write'))
    },
    # Comprovantes e PDFs clínicos.
    'documents.signature_receipt': {
        '*': rule('patients:view', 'documents:sign')
    },
    'documents.add_receituario': {
        '*': rule('patients:view', 'documents:generate')
    },
    'documents.delete_receituario': {
        '*': rule('patients:view', 'documents:generate')
    },
    'documents.add_atestado': {
        '*': rule('patients:view', 'documents:generate')
    },
    'documents.delete_atestado': {
        '*': rule('patients:view', 'documents:generate')
    },
    'documents.pdf_receituario': {
        '*': rule('patients:view', 'documents:generate')
    },
    'documents.pdf_atestado': {
        '*': rule('patients:view', 'documents:generate')
    },
    'documents.pdf_estomatologia': {
        '*': rule('patients:view', 'documents:generate', 'estomatologia:view')
    },
    'documents.pdf_status': {
        '*': rule(any_of=('documents:generate', 'reports:view', 'bi:view'))
    },
    'documents.download_pdf': {
        '*': rule(any_of=('documents:generate', 'reports:view', 'bi:view'))
    },
    # Assinaturas dos módulos clínicos ocultos.
    'endodontia.sign_patient': {
        '*': rule('patients:view', 'endodontia:write', 'documents:sign')
    },
    'endodontia.sign_validator': {
        '*': rule('patients:view', 'endodontia:write', 'documents:sign')
    },
    'prosthesis.sign_patient': {
        '*': rule('patients:view', 'prosthesis:write', 'documents:sign')
    },
    'prosthesis.sign_validator': {
        '*': rule('patients:view', 'prosthesis:write', 'documents:sign')
    },
    'prosthesis.add_payment': {
        '*': rule('patients:view', 'prosthesis:write', 'documents:sign')
    },
}


TAB_ACCESS_RULES = {
    'tab-anamnese': rule('anamnesis:view'),
    'tab-exames': rule('exams:view'),
    'tab-atendimento': rule('attendance:view'),
    'tab-tratamento': rule('treatment:view'),
    'tab-endodontia': rule('endodontia:view'),
    'tab-protese': rule('prosthesis:view'),
    'tab-receituario': rule('documents:generate'),
    'tab-atestado': rule('documents:generate'),
    'tab-estomatologia': rule('estomatologia:view'),
    'tab-visual': rule(
        any_of=('exams:view', 'estomatologia:view', 'endodontia:view')
    ),
    'tab-materiais': rule('inventory:view'),
    'tab-linha-tempo': rule('clinical_timeline:view'),
}


def get_access_rule(endpoint=None, method=None):
    endpoint = endpoint or request.endpoint
    method = (method or request.method or 'GET').upper()
    if method == 'HEAD':
        method = 'GET'
    if method == 'OPTIONS':
        return None
    if not endpoint or '.' not in endpoint:
        return None

    endpoint_policy = ENDPOINT_RULES.get(endpoint)
    if endpoint_policy:
        return endpoint_policy.get(method) or endpoint_policy.get('*')

    blueprint = endpoint.split('.', 1)[0]
    blueprint_policy = BLUEPRINT_DEFAULTS.get(blueprint)
    if not blueprint_policy:
        return None
    return blueprint_policy.get(method) or blueprint_policy.get('*')


def rule_allows(user, access_rule):
    if access_rule is None:
        return True
    if not getattr(user, 'is_authenticated', False):
        return False
    if any(not user.can(permission) for permission in access_rule.all_of):
        return False
    if access_rule.any_of and not any(user.can(permission) for permission in access_rule.any_of):
        return False
    return True


def describe_rule(access_rule):
    if access_rule is None:
        return {}
    return {
        'all_of': list(access_rule.all_of),
        'any_of': list(access_rule.any_of),
    }
