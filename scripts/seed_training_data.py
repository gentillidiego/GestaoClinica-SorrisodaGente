#!/usr/bin/env python3
"""Cria usuários e cenários fictícios para gravação das videoaulas."""

import os
import secrets
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constants import Role
from database import execute, init_db, query
from services.demo_data_service import (
    DEMO_SIGNATURE,
    _create_anamnesis,
    create_demo_patients,
    generate_cns,
    generate_valid_cpf,
)


TRAINING_USERS = (
    ('treino.admin', Role.ADMIN, 'Administrador Treinamento'),
    ('treino.coordenacao', Role.COORDENACAO, 'Coordenação Treinamento'),
    ('treino.clinico', Role.CLINICOS, 'Dra. Clínica Treinamento'),
    ('treino.recepcao', Role.RECEPCAO, 'Recepção Treinamento'),
    ('treino.cme', Role.CME, 'CME Treinamento'),
    ('treino.radiologia', Role.RADIOLOGIA, 'Radiologia Treinamento'),
    ('treino.analises_clinicas', Role.ANALISES_CLINICAS, 'Análises Clínicas Treinamento'),
    ('treino.comunicacao', Role.COMUNICACAO, 'Comunicação Treinamento'),
    ('treino.ssa', Role.SSA_SMS, 'SSA SMS Treinamento'),
    ('treino.auditoria', Role.AUDITORIA, 'Auditoria Treinamento'),
)

SCENARIO_PATIENTS = (
    ('triagem', 'Paciente Triagem Treinamento'),
    ('agenda', 'Paciente Agenda Treinamento'),
    ('tcle', 'Paciente TCLE Treinamento'),
    ('anamnese', 'Paciente Anamnese Treinamento'),
    ('plano', 'Paciente Plano Treinamento'),
)


def upsert_user(username, role, full_name, password, *, first_access=False):
    professional = role in {Role.CLINICOS, Role.CME, Role.RADIOLOGIA, Role.ANALISES_CLINICAS}
    dental = role == Role.CLINICOS
    password_hash = generate_password_hash(password)
    existing = query(
        "SELECT id FROM users WHERE username = %s",
        (username,),
        one=True,
    )
    values = (
        password_hash,
        role,
        full_name,
        f'{username}@example.com',
        '1990-01-15',
        first_access,
        '12345' if dental else None,
        'AL' if dental else None,
        '700000000000001' if professional else None,
        '223208' if professional else None,
        '2000001' if professional else None,
        '0000000001' if professional else None,
        True,
    )
    if existing:
        execute(
            """
            UPDATE users
            SET password = %s, role = %s, full_name = %s, email = %s,
                data_nascimento = %s, is_first_access = %s, cro = %s,
                cro_uf = %s, cns = %s, cbo = %s, cnes = %s, ine = %s,
                active = %s
            WHERE id = %s
            """,
            (*values, existing['id']),
        )
        return existing['id']

    return execute(
        """
        INSERT INTO users (
            username, password, role, full_name, email, data_nascimento,
            is_first_access, cro, cro_uf, cns, cbo, cnes, ine, active
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (username, *values),
    )


def ensure_patient(key, name, index):
    existing = query(
        "SELECT id FROM patients WHERE demo_profile = %s LIMIT 1",
        (f'training_{key}',),
        one=True,
    )
    if existing:
        return existing['id']

    return execute(
        """
        INSERT INTO patients (
            cns, nome, rg, cpf, profissao, endereco_residencial,
            cep_residencial, endereco_logradouro, endereco_numero,
            endereco_bairro, endereco_cidade, endereco_estado,
            email, genero, data_nascimento, nacionalidade, celular,
            estado_civil, atendido_em, is_demo, demo_profile, criado_em
        )
        VALUES (
            %s, %s, %s, %s, 'Paciente fictício', %s,
            '57000-000', %s, %s, 'Centro', 'Maceió', 'AL',
            %s, 'Fem', '1985-05-20', 'Brasileira', '(82) 99999-0000',
            'Solteiro', 'Ambiente de treinamento', TRUE, %s, NOW()
        )
        RETURNING id
        """,
        (
            generate_cns(9000 + index),
            name,
            f'TREINO-{index:03d}',
            generate_valid_cpf(9000 + index),
            f'Rua Treinamento, {100 + index}, Centro, Maceió - AL',
            'Rua Treinamento',
            str(100 + index),
            f'paciente.treino{index}@example.com',
            f'training_{key}',
        ),
    )


def ensure_tcle(patient_id, clinical_user_id):
    existing = query(
        "SELECT id FROM patient_tcle WHERE patient_id = %s LIMIT 1",
        (patient_id,),
        one=True,
    )
    if not existing:
        execute(
            """
            INSERT INTO patient_tcle (
                patient_id, operator_id, assinatura_base64, data_assinatura,
                texto_opcional
            )
            VALUES (%s, %s, %s, NOW(), %s)
            """,
            (
                patient_id,
                clinical_user_id,
                DEMO_SIGNATURE,
                'TCLE fictício para treinamento.',
            ),
        )


def ensure_triage(patient_id, reception_user_id):
    existing = query(
        "SELECT id FROM triagem_senhas WHERE patient_id = %s LIMIT 1",
        (patient_id,),
        one=True,
    )
    if existing:
        return
    municipality = query(
        "SELECT id, codigo FROM municipios WHERE nome = 'Maceió' LIMIT 1",
        one=True,
    ) or query("SELECT id, codigo FROM municipios ORDER BY id LIMIT 1", one=True)
    specialty = query(
        "SELECT id, codigo FROM especialidades WHERE ativo = 1 ORDER BY id LIMIT 1",
        one=True,
    )
    action_id = execute(
        """
        INSERT INTO triagem_acoes (
            municipio_id, data_acao, local, observacoes, created_by
        )
        VALUES (%s, CURRENT_DATE, 'UBS Treinamento', %s, %s)
        RETURNING id
        """,
        (
            municipality['id'],
            'Ação fictícia preparada para videoaula.',
            reception_user_id,
        ),
    )
    execute(
        """
        INSERT INTO triagem_senhas (
            triagem_acao_id, municipio_id, especialidade_id, numero, codigo,
            status, patient_id, vinculada_em
        )
        VALUES (%s, %s, %s, 990001, %s, 'Vinculada', %s, NOW())
        """,
        (
            action_id,
            municipality['id'],
            specialty['id'],
            f"TRN-{municipality['codigo']}-{specialty['codigo']}-001",
            patient_id,
        ),
    )


def ensure_anamnesis(patient_id):
    existing = query(
        "SELECT id FROM anamnesis WHERE patient_id = %s LIMIT 1",
        (patient_id,),
        one=True,
    )
    if existing:
        return existing['id']
    profile = {
        'key': 'training_plano',
        'label': 'Paciente preparado para plano de tratamento',
        'age': 41,
        'complaint': 'Sensibilidade no elemento 16.',
        'conditions': {
            'sofre_doenca': 'Nao',
            'detail': '',
            'pressure': '120x80',
        },
        'prosthesis': False,
        'lesion': False,
        'specialty': 'D',
        'procedures': [],
    }
    return _create_anamnesis(patient_id, profile, query("SELECT NOW() AS now", one=True)['now'])


def seed():
    if os.getenv('TRAINING_ENVIRONMENT', '').lower() not in {'1', 'true', 'yes'}:
        raise RuntimeError(
            'Carga recusada: TRAINING_ENVIRONMENT=true não está definido.'
        )

    init_db()
    password = os.getenv('TRAINING_DEFAULT_PASSWORD', 'Treino@2026!')
    user_ids = {
        username: upsert_user(username, role, full_name, password)
        for username, role, full_name in TRAINING_USERS
    }
    first_access_password = secrets.token_urlsafe(24)
    upsert_user(
        'treino.primeiro',
        Role.RECEPCAO,
        'Primeiro Acesso Treinamento',
        first_access_password,
        first_access=True,
    )

    patient_ids = {
        key: ensure_patient(key, name, index)
        for index, (key, name) in enumerate(SCENARIO_PATIENTS, start=1)
    }
    ensure_triage(patient_ids['agenda'], user_ids['treino.recepcao'])
    ensure_tcle(patient_ids['anamnese'], user_ids['treino.clinico'])
    ensure_tcle(patient_ids['plano'], user_ids['treino.clinico'])
    ensure_anamnesis(patient_ids['plano'])

    demo_count = query(
        "SELECT COUNT(*) AS total FROM patients WHERE demo_profile NOT LIKE 'training_%%' AND is_demo = TRUE",
        one=True,
    )
    if int(demo_count['total'] or 0) < 8:
        create_demo_patients(
            count=8,
            created_by=user_ids['treino.admin'],
            label='Indicadores fictícios para videoaula da Central de Comando',
        )

    print('Ambiente de treinamento preparado.')
    print(f'Senha padrão dos usuários concluídos: {password}')
    print('Primeiro acesso: treino.primeiro | nascimento: 15/01/1990')
    for username, _role, full_name in TRAINING_USERS:
        print(f'- {username}: {full_name}')
    for key, patient_id in patient_ids.items():
        print(f'- cenário {key}: paciente #{patient_id}')


if __name__ == '__main__':
    seed()
