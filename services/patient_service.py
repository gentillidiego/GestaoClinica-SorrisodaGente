import json
from database import query
from constants import Role

class PatientService:
    @staticmethod
    def get_patient_basic_info(patient_id):
        patient = query("SELECT * FROM patients WHERE id = %s", (patient_id,), one=True)
        if not patient:
            return None
        
        tcle = query("SELECT data_assinatura FROM patient_tcle WHERE patient_id = %s ORDER BY id DESC LIMIT 1", (patient_id,), one=True)
        tcle_signed = True if tcle else False
        
        return {
            'patient': patient,
            'tcle_signed': tcle_signed
        }

    @staticmethod
    def get_patient_anamnesis(patient_id):
        return query("SELECT * FROM anamnesis WHERE patient_id = %s ORDER BY id DESC LIMIT 1", (patient_id,), one=True)

    @staticmethod
    def get_patient_exams(patient_id):
        return query("""
            SELECT e.*, 
                   COALESCE(e.resumo_clinico, ef.estado_geral, eo.observacoes) as resumo_clinico,
                   u.username as professor_nome, u.full_name as professor_full_name,
                   u.role as professor_role
            FROM exams e 
            LEFT JOIN exam_fisico ef ON e.id = ef.exam_id 
            LEFT JOIN exam_odontograma eo ON e.id = eo.exam_id
            LEFT JOIN users u ON e.professor_id = u.id
            WHERE e.patient_id = %s 
            ORDER BY e.data_criacao DESC
        """, (patient_id,))

    @staticmethod
    def get_patient_appointments(patient_id):
        return query("""
            SELECT a.*, up.username as professor_nome, ua.username as aluno_executor_nome,
                   up.role as professor_role, up.full_name as professor_full_name
            FROM atendimentos a
            LEFT JOIN users up ON a.professor_id = up.id
            LEFT JOIN users ua ON a.aluno_executor_id = ua.id
            WHERE a.patient_id = %s 
            ORDER BY a.data DESC, a.id DESC
        """, (patient_id,))

    @staticmethod
    def get_patient_treatments(patient_id):
        plans = query("SELECT * FROM planos_tratamento WHERE patient_id = %s ORDER BY criado_em DESC", (patient_id,))
        treatments = query("""
            SELECT tp.*, u.username as professor_nome, u.role as professor_role, u.full_name as professor_full_name
            FROM tratamento_procedimentos tp
            LEFT JOIN users u ON tp.professor_id = u.id
            WHERE tp.patient_id = %s
            ORDER BY tp.criado_em ASC
        """, (patient_id,))
        return {'plans': plans, 'treatments': treatments}

    @staticmethod
    def get_patient_documents(patient_id):
        receituarios_raw = query("SELECT * FROM receituarios WHERE patient_id = %s ORDER BY data DESC", (patient_id,))
        receituarios = []
        for r in receituarios_raw:
            rec = dict(r)
            try:
                if rec['prescricao'] and rec['prescricao'].strip().startswith('['):
                    rec['prescricao_parsed'] = json.loads(rec['prescricao'])
                else:
                    rec['prescricao_parsed'] = None
            except:
                rec['prescricao_parsed'] = None
            receituarios.append(rec)

        atestados = query("SELECT * FROM atestados WHERE patient_id = %s ORDER BY data DESC", (patient_id,))
        return {'receituarios': receituarios, 'atestados': atestados}

    @staticmethod
    def get_patient_prosthesis(patient_id):
        prosthesis_active = query("""
            SELECT p.*, u.username as aluno_nome 
            FROM prosthesis p
            LEFT JOIN users u ON p.aluno_responsavel_id = u.id
            WHERE p.patient_id = %s AND p.status = 'Ativo'
            ORDER BY p.data DESC LIMIT 1
        """, (patient_id,), one=True)
        
        etapas = []
        pagamentos = []
        if prosthesis_active:
            etapas = query("""
                SELECT e.*, u.username as professor_nome, u.role as professor_role, u.full_name as professor_full_name
                FROM prosthesis_etapas e
                LEFT JOIN users u ON e.professor_id = u.id
                WHERE e.prosthesis_id = %s
                ORDER BY e.numero_etapa ASC
            """, (prosthesis_active['id'],))
            
            pagamentos = query("""
                SELECT pg.*, u.username as responsavel_nome
                FROM prosthesis_pagamentos pg
                LEFT JOIN users u ON pg.responsavel_id = u.id
                WHERE pg.prosthesis_id = %s
                ORDER BY pg.data_pagamento DESC
            """, (prosthesis_active['id'],))

        history_prosthesis = query("SELECT * FROM prosthesis WHERE patient_id = %s AND status != 'Ativo' ORDER BY data DESC", (patient_id,))
        return {
            'prosthesis_active': prosthesis_active,
            'etapas': etapas,
            'pagamentos': pagamentos,
            'history_prosthesis': history_prosthesis
        }

    @staticmethod
    def get_patient_endodontia(patient_id):
        return query("""
            SELECT e.*, u.username as aluno_nome 
            FROM endodontia e
            LEFT JOIN users u ON e.aluno_id = u.id
            WHERE e.patient_id = %s
            ORDER BY e.criado_em DESC
        """, (patient_id,))

    @staticmethod
    def get_patient_full_profile(patient_id):
        basic = PatientService.get_patient_basic_info(patient_id)
        if not basic:
            return None
        
        anamnesis = PatientService.get_patient_anamnesis(patient_id)
        exams = PatientService.get_patient_exams(patient_id)
        appointments = PatientService.get_patient_appointments(patient_id)
        t_data = PatientService.get_patient_treatments(patient_id)
        d_data = PatientService.get_patient_documents(patient_id)
        p_data = PatientService.get_patient_prosthesis(patient_id)
        endodontia_elements = PatientService.get_patient_endodontia(patient_id)
        students = query("SELECT id, username, full_name FROM users WHERE role IN (%s, %s) ORDER BY full_name ASC", (Role.TSB, Role.DENTISTA))

        return {
            **basic,
            'anamnesis': anamnesis,
            'exams': exams,
            'appointments': appointments,
            'plans': t_data['plans'],
            'treatments': t_data['treatments'],
            'receituarios': d_data['receituarios'],
            'atestados': d_data['atestados'],
            **p_data,
            'endodontia_elements': endodontia_elements,
            'students': students
        }

