class Role:
    # Perfis ativos exibidos na administracao.
    ADMIN = 'admin'
    COORDENACAO = 'coordenacao'
    CLINICOS = 'clinicos'
    RECEPCAO = 'recepcao'
    CME = 'cme'
    RADIOLOGIA = 'radiologia'
    COMUNICACAO = 'comunicacao'
    SSA_SMS = 'ssa_sms'
    AUDITORIA = 'auditoria'

    # Perfis legados mantidos como aliases internos para compatibilidade.
    TRIAGEM = 'triagem'
    CLINICA_GERAL = 'clinica_geral'
    DENTISTA = 'dentista'
    ENDODONTIA = 'endodontia'
    CIRURGIA = 'cirurgia'
    IMPLANTES = 'implantes'
    ESTOMATOLOGIA = 'estomatologia'
    LABORATORIO = 'laboratorio'
    FINANCEIRO = 'financeiro'
    EPIDEMIOLOGIA = 'epidemiologia'
    BI = 'bi'
    PREFEITURA = 'prefeitura'
    SSA = 'ssa'
    SMS = 'sms'
    MUTIRAO_MOVEL = 'mutirao_movel'
    TSB = 'tsb'
    ATENDENTE = 'atendente'
    ATENDIMENTO_LEGACY = 'atendimento'


ACTIVE_ROLE_LABELS = {
    Role.ADMIN: 'Administrador',
    Role.COORDENACAO: 'Coordenação',
    Role.CLINICOS: 'Clínicos',
    Role.RECEPCAO: 'Recepção',
    Role.CME: 'CME / Estoque',
    Role.RADIOLOGIA: 'Radiologia',
    Role.COMUNICACAO: 'Comunicação',
    Role.SSA_SMS: 'SSA/SMS',
    Role.AUDITORIA: 'Auditoria',
}


LEGACY_ROLE_MAP = {
    Role.ADMIN: Role.ADMIN,
    Role.COORDENACAO: Role.COORDENACAO,
    Role.CLINICOS: Role.CLINICOS,
    Role.RECEPCAO: Role.RECEPCAO,
    Role.CME: Role.CME,
    Role.RADIOLOGIA: Role.RADIOLOGIA,
    Role.COMUNICACAO: Role.COMUNICACAO,
    Role.SSA_SMS: Role.SSA_SMS,
    Role.AUDITORIA: Role.AUDITORIA,
    Role.TRIAGEM: Role.RECEPCAO,
    Role.ATENDENTE: Role.RECEPCAO,
    Role.ATENDIMENTO_LEGACY: Role.RECEPCAO,
    Role.MUTIRAO_MOVEL: Role.RECEPCAO,
    Role.CLINICA_GERAL: Role.CLINICOS,
    Role.DENTISTA: Role.CLINICOS,
    Role.ENDODONTIA: Role.CLINICOS,
    Role.CIRURGIA: Role.CLINICOS,
    Role.IMPLANTES: Role.CLINICOS,
    Role.ESTOMATOLOGIA: Role.CLINICOS,
    Role.TSB: Role.CLINICOS,
    Role.LABORATORIO: Role.CME,
    Role.FINANCEIRO: Role.COORDENACAO,
    Role.EPIDEMIOLOGIA: Role.COORDENACAO,
    Role.BI: Role.COORDENACAO,
    Role.PREFEITURA: Role.SSA_SMS,
    Role.SSA: Role.SSA_SMS,
    Role.SMS: Role.SSA_SMS,
}


ROLE_LABELS = {
    role: ACTIVE_ROLE_LABELS.get(canonical, role)
    for role, canonical in LEGACY_ROLE_MAP.items()
}


PROFESSIONAL_DATA_REQUIRED_ROLES = {
    Role.CLINICOS,
    Role.CME,
    Role.RADIOLOGIA,
}


DENTAL_LICENSE_REQUIRED_ROLES = {
    Role.CLINICOS,
}


CLINICAL_EXECUTOR_ROLES = {
    Role.CLINICOS,
    Role.CLINICA_GERAL,
    Role.DENTISTA,
    Role.ENDODONTIA,
    Role.CIRURGIA,
    Role.IMPLANTES,
    Role.ESTOMATOLOGIA,
    Role.TSB,
}

EXECUTION_UNITS = (
    ('unidade_principal', 'Unidade Principal'),
    ('unidade_apoio', 'Unidade de Apoio'),
)

DEFAULT_EXECUTION_UNIT = EXECUTION_UNITS[0][0]


MODULE_PERMISSIONS = {
    'dashboard:view',
    'patients:view',
    'patients:write',
    'triage:view',
    'triage:write',
    'agenda:view',
    'agenda:write',
    'exams:view',
    'exams:write',
    'documents:sign',
    'documents:generate',
    'estomatologia:view',
    'estomatologia:write',
    'radiologia:view',
    'radiologia:write',
    'laboratorio:view',
    'laboratorio:write',
    'financeiro:view',
    'financeiro:write',
    'inventory:view',
    'inventory:write',
    'reports:view',
    'bi:view',
    'epidemiologia:view',
    'audit:view',
    'integrations:view',
    'integrations:write',
    'users:view',
    'users:write',
    'command_center:view',
}


ROLE_PERMISSIONS = {
    Role.ADMIN: MODULE_PERMISSIONS,
    Role.COORDENACAO: {
        'dashboard:view', 'command_center:view',
        'patients:view', 'triage:view', 'agenda:view', 'agenda:write',
        'inventory:view', 'inventory:write',
        'reports:view', 'bi:view', 'epidemiologia:view',
        'financeiro:view', 'financeiro:write',
        'integrations:view', 'integrations:write',
    },
    Role.CLINICOS: {
        'dashboard:view', 'command_center:view',
        'patients:view', 'patients:write',
        'agenda:view', 'agenda:write',
        'exams:view', 'exams:write',
        'documents:generate', 'documents:sign',
        'estomatologia:view', 'estomatologia:write',
        'inventory:view', 'inventory:write',
    },
    Role.RECEPCAO: {
        'dashboard:view', 'command_center:view',
        'patients:view', 'patients:write',
        'triage:view', 'triage:write',
        'agenda:view', 'agenda:write',
        'documents:generate',
    },
    Role.CME: {
        'dashboard:view', 'command_center:view',
        'patients:view',
        'inventory:view', 'inventory:write',
        'laboratorio:view', 'laboratorio:write',
    },
    Role.RADIOLOGIA: {
        'dashboard:view', 'command_center:view',
        'patients:view',
        'exams:view', 'exams:write',
        'radiologia:view', 'radiologia:write',
    },
    Role.COMUNICACAO: {
        'dashboard:view', 'command_center:view',
        'reports:view', 'bi:view',
    },
    Role.SSA_SMS: {
        'dashboard:view', 'command_center:view',
        'reports:view', 'bi:view', 'epidemiologia:view',
    },
    Role.AUDITORIA: {
        'dashboard:view', 'command_center:view',
        'patients:view',
        'reports:view', 'audit:view', 'integrations:view',
    },
}


def canonical_role(role):
    return LEGACY_ROLE_MAP.get(role, role)


def get_legacy_role_migrations():
    return [
        (legacy_role, canonical)
        for legacy_role, canonical in LEGACY_ROLE_MAP.items()
        if legacy_role != canonical
    ]


def get_role_choices():
    return list(ACTIVE_ROLE_LABELS.items())


def get_role_label(role):
    if not role:
        return 'Usuário'
    canonical = canonical_role(role)
    return ACTIVE_ROLE_LABELS.get(canonical, role)


def get_execution_unit_choices():
    return list(EXECUTION_UNITS)


def get_execution_unit_label(unit):
    labels = dict(EXECUTION_UNITS)
    return labels.get(unit or DEFAULT_EXECUTION_UNIT, labels[DEFAULT_EXECUTION_UNIT])


def normalize_execution_unit(unit):
    valid_units = {value for value, _label in EXECUTION_UNITS}
    return unit if unit in valid_units else None


def role_has_permission(role, permission):
    return permission in ROLE_PERMISSIONS.get(canonical_role(role), set())


def role_requires_professional_data(role):
    return canonical_role(role) in PROFESSIONAL_DATA_REQUIRED_ROLES


def role_requires_dental_license(role):
    return canonical_role(role) in DENTAL_LICENSE_REQUIRED_ROLES


def can_sign_clinical_document(role):
    return canonical_role(role) in {Role.ADMIN, Role.CLINICOS}
