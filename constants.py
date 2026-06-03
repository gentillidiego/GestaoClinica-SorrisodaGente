class Role:
    ADMIN = 'admin'
    RECEPCAO = 'recepcao'
    TRIAGEM = 'triagem'
    CLINICA_GERAL = 'clinica_geral'
    DENTISTA = 'dentista'
    ENDODONTIA = 'endodontia'
    CIRURGIA = 'cirurgia'
    IMPLANTES = 'implantes'
    ESTOMATOLOGIA = 'estomatologia'
    RADIOLOGIA = 'radiologia'
    LABORATORIO = 'laboratorio'
    FINANCEIRO = 'financeiro'
    AUDITORIA = 'auditoria'
    EPIDEMIOLOGIA = 'epidemiologia'
    BI = 'bi'
    PREFEITURA = 'prefeitura'
    SSA = 'ssa'
    SMS = 'sms'
    COMUNICACAO = 'comunicacao'
    MUTIRAO_MOVEL = 'mutirao_movel'
    TSB = 'tsb'
    ATENDENTE = 'atendente'
    ATENDIMENTO_LEGACY = 'atendimento'


ROLE_LABELS = {
    Role.ADMIN: 'Administrador',
    Role.RECEPCAO: 'Recepção',
    Role.TRIAGEM: 'Triagem',
    Role.CLINICA_GERAL: 'Clínica Geral',
    Role.DENTISTA: 'Cirurgião-Dentista',
    Role.ENDODONTIA: 'Endodontia',
    Role.CIRURGIA: 'Cirurgia',
    Role.IMPLANTES: 'Implantes',
    Role.ESTOMATOLOGIA: 'Estomatologia',
    Role.RADIOLOGIA: 'Radiologia',
    Role.LABORATORIO: 'Laboratório',
    Role.FINANCEIRO: 'Financeiro',
    Role.AUDITORIA: 'Auditoria',
    Role.EPIDEMIOLOGIA: 'Epidemiologia',
    Role.BI: 'BI',
    Role.PREFEITURA: 'Prefeitura',
    Role.SSA: 'SSA',
    Role.SMS: 'SMS',
    Role.COMUNICACAO: 'Comunicação',
    Role.MUTIRAO_MOVEL: 'Mutirão Móvel',
    Role.TSB: 'TSB / ASB',
    Role.ATENDENTE: 'Atendente',
    Role.ATENDIMENTO_LEGACY: 'Atendimento',
}


PROFESSIONAL_DATA_REQUIRED_ROLES = {
    Role.TRIAGEM,
    Role.CLINICA_GERAL,
    Role.DENTISTA,
    Role.ENDODONTIA,
    Role.CIRURGIA,
    Role.IMPLANTES,
    Role.ESTOMATOLOGIA,
    Role.RADIOLOGIA,
    Role.LABORATORIO,
    Role.MUTIRAO_MOVEL,
    Role.TSB,
}


DENTAL_LICENSE_REQUIRED_ROLES = {
    Role.CLINICA_GERAL,
    Role.DENTISTA,
    Role.ENDODONTIA,
    Role.CIRURGIA,
    Role.IMPLANTES,
    Role.ESTOMATOLOGIA,
}


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
    Role.RECEPCAO: {
        'dashboard:view', 'patients:view', 'patients:write', 'agenda:view',
        'agenda:write', 'triage:view', 'documents:generate',
        'command_center:view'
    },
    Role.ATENDENTE: {
        'dashboard:view', 'patients:view', 'patients:write', 'agenda:view',
        'agenda:write', 'triage:view', 'triage:write', 'users:view',
        'documents:generate', 'command_center:view'
    },
    Role.ATENDIMENTO_LEGACY: {
        'dashboard:view', 'patients:view', 'patients:write', 'agenda:view',
        'agenda:write', 'triage:view', 'triage:write', 'users:view',
        'documents:generate', 'command_center:view'
    },
    Role.TRIAGEM: {
        'dashboard:view', 'patients:view', 'patients:write', 'triage:view',
        'triage:write', 'agenda:view', 'command_center:view'
    },
    Role.CLINICA_GERAL: {
        'dashboard:view', 'patients:view', 'patients:write', 'agenda:view',
        'agenda:write', 'exams:view', 'exams:write', 'documents:generate',
        'documents:sign', 'command_center:view'
    },
    Role.DENTISTA: {
        'dashboard:view', 'patients:view', 'patients:write', 'agenda:view',
        'agenda:write', 'exams:view', 'exams:write', 'documents:generate',
        'documents:sign', 'estomatologia:view', 'estomatologia:write',
        'inventory:view', 'inventory:write', 'command_center:view'
    },
    Role.ENDODONTIA: {
        'dashboard:view', 'patients:view', 'patients:write', 'agenda:view',
        'exams:view', 'exams:write', 'documents:generate', 'documents:sign',
        'command_center:view'
    },
    Role.CIRURGIA: {
        'dashboard:view', 'patients:view', 'patients:write', 'agenda:view',
        'exams:view', 'exams:write', 'documents:generate', 'documents:sign',
        'inventory:view', 'inventory:write', 'command_center:view'
    },
    Role.IMPLANTES: {
        'dashboard:view', 'patients:view', 'patients:write', 'agenda:view',
        'exams:view', 'exams:write', 'documents:generate', 'documents:sign',
        'inventory:view', 'inventory:write', 'command_center:view'
    },
    Role.ESTOMATOLOGIA: {
        'dashboard:view', 'patients:view', 'patients:write', 'agenda:view',
        'exams:view', 'exams:write', 'estomatologia:view',
        'estomatologia:write', 'documents:generate', 'documents:sign',
        'command_center:view'
    },
    Role.RADIOLOGIA: {
        'dashboard:view', 'patients:view', 'exams:view', 'radiologia:view',
        'radiologia:write', 'command_center:view'
    },
    Role.LABORATORIO: {
        'dashboard:view', 'patients:view', 'laboratorio:view',
        'laboratorio:write', 'inventory:view', 'inventory:write',
        'command_center:view'
    },
    Role.FINANCEIRO: {
        'dashboard:view', 'patients:view', 'financeiro:view',
        'financeiro:write', 'inventory:view', 'inventory:write',
        'reports:view', 'command_center:view'
    },
    Role.AUDITORIA: {
        'dashboard:view', 'patients:view', 'reports:view', 'audit:view',
        'integrations:view', 'command_center:view'
    },
    Role.EPIDEMIOLOGIA: {
        'dashboard:view', 'patients:view', 'reports:view', 'epidemiologia:view',
        'command_center:view'
    },
    Role.BI: {
        'dashboard:view', 'reports:view', 'bi:view', 'epidemiologia:view',
        'integrations:view', 'command_center:view'
    },
    Role.PREFEITURA: {
        'dashboard:view', 'reports:view', 'bi:view', 'command_center:view'
    },
    Role.SSA: {
        'dashboard:view', 'reports:view', 'bi:view', 'epidemiologia:view',
        'command_center:view'
    },
    Role.SMS: {
        'dashboard:view', 'reports:view', 'bi:view', 'epidemiologia:view',
        'command_center:view'
    },
    Role.COMUNICACAO: {
        'dashboard:view', 'patients:view', 'reports:view', 'command_center:view'
    },
    Role.MUTIRAO_MOVEL: {
        'dashboard:view', 'patients:view', 'patients:write', 'triage:view',
        'triage:write', 'agenda:view', 'command_center:view'
    },
    Role.TSB: {
        'dashboard:view', 'patients:view', 'patients:write', 'agenda:view',
        'exams:view', 'exams:write', 'command_center:view'
    },
}


def get_role_choices():
    return [
        (role, ROLE_LABELS[role])
        for role in ROLE_LABELS
        if role != Role.ATENDIMENTO_LEGACY
    ]


def get_role_label(role):
    return ROLE_LABELS.get(role, role or 'Usuário')


def role_has_permission(role, permission):
    return permission in ROLE_PERMISSIONS.get(role, set())


def role_requires_professional_data(role):
    return role in PROFESSIONAL_DATA_REQUIRED_ROLES


def role_requires_dental_license(role):
    return role in DENTAL_LICENSE_REQUIRED_ROLES
