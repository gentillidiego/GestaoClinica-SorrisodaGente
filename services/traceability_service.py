import datetime as dt

from database import query


def _as_datetime(value):
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min)
    if isinstance(value, str):
        normalized = value.strip()
        try:
            return dt.datetime.fromisoformat(normalized)
        except ValueError:
            pass

        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d', '%d/%m/%Y'):
            try:
                return dt.datetime.strptime(normalized, fmt)
            except ValueError:
                continue
    return None


def _event(date_value, category, title, description, actor=None, status=None, metadata=None):
    occurred_at = _as_datetime(date_value)
    return {
        'occurred_at': occurred_at,
        'category': category,
        'title': title,
        'description': description,
        'actor': actor,
        'status': status,
        'metadata': metadata or {},
    }


def _sort_events(events):
    return sorted(
        [event for event in events if event.get('occurred_at')],
        key=lambda item: item['occurred_at'],
        reverse=True,
    )


class TraceabilityService:
    @staticmethod
    def get_patient_timeline(patient_id):
        events = []

        patient = query("SELECT id, nome, criado_em FROM patients WHERE id = %s", (patient_id,), one=True)
        if not patient:
            return []

        events.append(_event(
            patient['criado_em'],
            'Cadastro',
            'Paciente cadastrado',
            f"Prontuário #{patient['id']} criado para {patient['nome']}.",
            status='Concluído',
        ))

        events.extend(TraceabilityService._triage_events(patient_id))
        events.extend(TraceabilityService._consent_events(patient_id))
        events.extend(TraceabilityService._agenda_events(patient_id))
        events.extend(TraceabilityService._appointment_events(patient_id))
        events.extend(TraceabilityService._exam_events(patient_id))
        events.extend(TraceabilityService._treatment_events(patient_id))
        events.extend(TraceabilityService._prosthesis_events(patient_id))
        events.extend(TraceabilityService._endodontia_events(patient_id))
        events.extend(TraceabilityService._document_events(patient_id))
        events.extend(TraceabilityService._estomatologia_events(patient_id))
        events.extend(TraceabilityService._audit_events(patient_id))

        return _sort_events(events)

    @staticmethod
    def get_patient_traceability_summary(patient_id):
        timeline = TraceabilityService.get_patient_timeline(patient_id)
        categories = {}
        for event in timeline:
            categories[event['category']] = categories.get(event['category'], 0) + 1

        return {
            'timeline': timeline,
            'total_events': len(timeline),
            'categories': categories,
            'first_event': timeline[-1] if timeline else None,
            'last_event': timeline[0] if timeline else None,
        }

    @staticmethod
    def _triage_events(patient_id):
        rows = query("""
            SELECT s.codigo, s.status, s.vinculada_em, s.entregue_em, s.criado_em,
                   e.nome as especialidade_nome, m.nome as municipio_nome,
                   a.data_acao, a.local as triagem_local
            FROM triagem_senhas s
            JOIN especialidades e ON s.especialidade_id = e.id
            JOIN municipios m ON s.municipio_id = m.id
            JOIN triagem_acoes a ON s.triagem_acao_id = a.id
            WHERE s.patient_id = %s
        """, (patient_id,))

        events = []
        for row in rows or []:
            events.append(_event(
                row['vinculada_em'] or row['entregue_em'] or row['criado_em'] or row['data_acao'],
                'Triagem',
                'Senha de triagem vinculada',
                f"{row['codigo']} · {row['especialidade_nome']} · {row['municipio_nome']}.",
                status=row['status'],
                metadata={'local': row['triagem_local']},
            ))
        return events

    @staticmethod
    def _consent_events(patient_id):
        rows = query("""
            SELECT t.data_assinatura, t.texto_opcional, u.username, u.full_name
            FROM patient_tcle t
            LEFT JOIN users u ON t.aluno_id = u.id
            WHERE t.patient_id = %s
            ORDER BY t.data_assinatura DESC
        """, (patient_id,))

        return [
            _event(
                row['data_assinatura'],
                'Consentimento',
                'TCLE assinado',
                'Termo de consentimento registrado no prontuário.',
                actor=row['full_name'] or row['username'],
                status='Assinado',
                metadata={'observacao': row['texto_opcional']},
            )
            for row in rows or []
        ]

    @staticmethod
    def _agenda_events(patient_id):
        rows = query("""
            SELECT c.id, c.data_consulta, c.status, c.observacoes, c.criado_em,
                   u.full_name, u.username
            FROM consultas c
            LEFT JOIN users u ON c.dentista_id = u.id
            WHERE c.patient_id = %s
            ORDER BY c.data_consulta DESC
        """, (patient_id,))

        return [
            _event(
                row['data_consulta'] or row['criado_em'],
                'Agenda',
                f"Consulta {row['status'].lower()}",
                row['observacoes'] or f"Consulta #{row['id']} registrada na agenda.",
                actor=row['full_name'] or row['username'],
                status=row['status'],
            )
            for row in rows or []
        ]

    @staticmethod
    def _appointment_events(patient_id):
        rows = query("""
            SELECT a.id, a.data, a.status, a.observacoes,
                   up.full_name as professor_nome, up.username as professor_username,
                   ua.full_name as executor_nome, ua.username as executor_username
            FROM atendimentos a
            LEFT JOIN users up ON a.professor_id = up.id
            LEFT JOIN users ua ON a.aluno_executor_id = ua.id
            WHERE a.patient_id = %s
        """, (patient_id,))

        events = []
        for row in rows or []:
            actor = row['executor_nome'] or row['executor_username'] or row['professor_nome'] or row['professor_username']
            events.append(_event(
                row['data'],
                'Atendimento',
                'Atendimento clínico',
                row['observacoes'] or f"Atendimento #{row['id']} registrado.",
                actor=actor,
                status=row['status'],
            ))
        return events

    @staticmethod
    def _exam_events(patient_id):
        rows = query("""
            SELECT e.id, e.tipo, e.data_criacao, e.resumo_clinico, e.data_validacao,
                   u.full_name, u.username
            FROM exams e
            LEFT JOIN users u ON e.professor_id = u.id
            WHERE e.patient_id = %s
        """, (patient_id,))

        events = []
        for row in rows or []:
            events.append(_event(
                row['data_criacao'],
                'Exame',
                f"Exame {row['tipo']}",
                row['resumo_clinico'] or f"Exame #{row['id']} registrado.",
                actor=row['full_name'] or row['username'],
                status='Validado' if row['data_validacao'] else 'Registrado',
            ))
            if row['data_validacao']:
                events.append(_event(
                    row['data_validacao'],
                    'Exame',
                    f"Exame {row['tipo']} validado",
                    f"Validação clínica do exame #{row['id']}.",
                    actor=row['full_name'] or row['username'],
                    status='Validado',
                ))
        return events

    @staticmethod
    def _treatment_events(patient_id):
        rows = query("""
            SELECT tp.id, tp.data_sessao, tp.dente, tp.descricao, tp.status, tp.criado_em,
                   u.full_name, u.username
            FROM tratamento_procedimentos tp
            LEFT JOIN users u ON tp.professor_id = u.id
            WHERE tp.patient_id = %s
        """, (patient_id,))

        return [
            _event(
                row['data_sessao'] or row['criado_em'],
                'Tratamento',
                f"Procedimento {row['status'].lower()}",
                row['descricao'] or f"Procedimento #{row['id']}.",
                actor=row['full_name'] or row['username'],
                status=row['status'],
                metadata={'dente': row['dente']},
            )
            for row in rows or []
        ]

    @staticmethod
    def _prosthesis_events(patient_id):
        rows = query("""
            SELECT p.id, p.data, p.descricao, p.tipo, p.status,
                   u.full_name, u.username
            FROM prosthesis p
            LEFT JOIN users u ON p.aluno_responsavel_id = u.id
            WHERE p.patient_id = %s
        """, (patient_id,))

        events = [
            _event(
                row['data'],
                'Prótese',
                f"Prótese {row['status'].lower()}",
                row['descricao'] or row['tipo'] or f"Prótese #{row['id']}.",
                actor=row['full_name'] or row['username'],
                status=row['status'],
            )
            for row in rows or []
        ]

        etapas = query("""
            SELECT e.data_etapa, e.nome_etapa, e.servico_solicitado, e.status,
                   u.full_name, u.username
            FROM prosthesis_etapas e
            JOIN prosthesis p ON e.prosthesis_id = p.id
            LEFT JOIN users u ON e.professor_id = u.id
            WHERE p.patient_id = %s
        """, (patient_id,))
        for row in etapas or []:
            events.append(_event(
                row['data_etapa'],
                'Prótese',
                row['nome_etapa'],
                row['servico_solicitado'] or 'Etapa laboratorial/clínica registrada.',
                actor=row['full_name'] or row['username'],
                status=row['status'],
            ))
        return events

    @staticmethod
    def _endodontia_events(patient_id):
        rows = query("""
            SELECT e.id, e.criado_em, e.elemento_dentario, e.diagnostico, e.status,
                   u.full_name, u.username
            FROM endodontia e
            LEFT JOIN users u ON e.aluno_id = u.id
            WHERE e.patient_id = %s
        """, (patient_id,))

        return [
            _event(
                row['criado_em'],
                'Endodontia',
                f"Endodontia do elemento {row['elemento_dentario']}",
                row['diagnostico'] or f"Ficha endodôntica #{row['id']} registrada.",
                actor=row['full_name'] or row['username'],
                status=row['status'],
            )
            for row in rows or []
        ]

    @staticmethod
    def _document_events(patient_id):
        events = []
        receituarios = query("SELECT id, data, uso FROM receituarios WHERE patient_id = %s", (patient_id,))
        for row in receituarios or []:
            events.append(_event(row['data'], 'Documento', 'Receituário emitido', row['uso'] or f"Receituário #{row['id']}.", status='Emitido'))

        atestados = query("SELECT id, data, motivo, dias_repouso FROM atestados WHERE patient_id = %s", (patient_id,))
        for row in atestados or []:
            desc = row['motivo'] or f"Atestado #{row['id']}."
            if row['dias_repouso']:
                desc = f"{desc} Repouso: {row['dias_repouso']} dia(s)."
            events.append(_event(row['data'], 'Documento', 'Atestado emitido', desc, status='Emitido'))
        return events

    @staticmethod
    def _estomatologia_events(patient_id):
        rows = query("""
            SELECT e.id, e.data_registro, e.localizacao_lesao, e.hipotese_diagnostica,
                   e.suspeita_neoplasia, e.encaminhado_para_biopsia, u.full_name, u.username
            FROM estomatologia e
            LEFT JOIN users u ON e.dentista_id = u.id
            WHERE e.patient_id = %s
        """, (patient_id,))

        events = []
        for row in rows or []:
            status = 'Alerta vermelho' if row['suspeita_neoplasia'] else 'Registrado'
            events.append(_event(
                row['data_registro'],
                'Estomatologia',
                'Ficha de estomatologia',
                row['hipotese_diagnostica'] or f"Lesão em {row['localizacao_lesao']}.",
                actor=row['full_name'] or row['username'],
                status=status,
                metadata={'encaminhado_para_biopsia': row['encaminhado_para_biopsia']},
            ))

            photos = query(
                "SELECT legenda, data_upload FROM estomatologia_fotos WHERE estomatologia_id = %s",
                (row['id'],)
            )
            for photo in photos or []:
                events.append(_event(
                    photo['data_upload'],
                    'Foto Clínica',
                    'Foto de lesão anexada',
                    photo['legenda'] or 'Registro fotográfico da lesão.',
                    actor=row['full_name'] or row['username'],
                    status='Anexada',
                ))
        return events

    @staticmethod
    def _audit_events(patient_id):
        rows = query("""
            SELECT created_at, action, module, username, user_role, status
            FROM audit_logs
            WHERE patient_id = %s
            ORDER BY created_at DESC
            LIMIT 50
        """, (patient_id,))

        return [
            _event(
                row['created_at'],
                'Auditoria',
                row['action'],
                f"Módulo {row['module']} registrou evento de auditoria.",
                actor=row['username'],
                status=row['status'],
                metadata={'role': row['user_role']},
            )
            for row in rows or []
        ]
