import datetime as dt
from decimal import Decimal

from flask import Flask, url_for
import services.patient_service as patient_service
import services.traceability_service as traceability_service
from blueprints.endodontia import endodontia_bp
from services.endodontia_service import (
    ENDODONTIA_FORM_OPTIONS,
    build_anamnesis_risk_summary,
    build_budget_summary,
    build_case_details_payload,
    build_channel_payloads,
    build_diagnosis_context,
    build_endodontia_budget_items,
    build_obturation_payload,
    build_proservation_evaluation_payload,
    build_proservation_schedule_payloads,
    build_protocol_payload,
    build_protocol_safety_context,
    build_session_context,
    build_session_payload,
    calculate_crd,
    classify_tooth_complexity,
    derive_treatment_status,
    parse_json_list,
    suggest_crt,
    suggest_typical_channels,
)
from services.command_center_service import get_unsigned_document_alert_summary
from services.patient_service import PatientService
from services.traceability_service import TraceabilityService
import services.command_center_service as command_center_service
from werkzeug.datastructures import MultiDict


def test_patient_endodontia_hides_cancelled_cases(monkeypatch):
    captured = {}

    def fake_query(sql, params=(), one=False):
        captured['sql'] = sql
        captured['params'] = params
        return []

    monkeypatch.setattr(patient_service, 'query', fake_query)

    result = PatientService.get_patient_endodontia(42)

    assert result == []
    assert captured['params'] == (42,)
    assert "e.cancelado_em IS NULL" in captured['sql']
    assert "COALESCE(e.status, 'Ativo') != 'Cancelado'" in captured['sql']


def test_endodontia_cancelled_case_enters_patient_timeline(monkeypatch):
    def fake_query(sql, params=(), one=False):
        if 'FROM endodontia e' in sql:
            return [{
                'id': 9,
                'criado_em': dt.datetime(2026, 6, 1, 9, 0),
                'elemento_dentario': '36',
                'diagnostico': 'Necrose pulpar',
                'status': 'Cancelado',
                'cancelado_em': dt.datetime(2026, 6, 2, 10, 30),
                'motivo_cancelamento': 'Paciente encaminhado para outro serviço.',
                'full_name': 'Dra. Cibely',
                'username': 'cibely',
                'cancelado_por_nome': 'Dra. Cibely',
                'cancelado_por_username': 'cibely',
            }]
        return []

    monkeypatch.setattr(traceability_service, 'query', fake_query)

    events = TraceabilityService._endodontia_events(7)

    assert len(events) == 2
    assert events[0]['title'] == 'Endodontia do elemento 36'
    assert events[1]['title'] == 'Acompanhamento endodôntico cancelado - elemento 36'
    assert events[1]['status'] == 'Cancelado'
    assert events[1]['description'] == 'Paciente encaminhado para outro serviço.'


def test_unsigned_document_alerts_ignore_cancelled_endodontia_cases(monkeypatch):
    captured = {}

    def fake_query(sql, params=(), one=False):
        captured['sql'] = sql
        return []

    monkeypatch.setattr(command_center_service, 'query', fake_query)

    summary = get_unsigned_document_alert_summary(limit=5)

    assert summary['total'] == 0
    assert "e.cancelado_em IS NULL" in captured['sql']
    assert "COALESCE(e.status, 'Ativo') != 'Cancelado'" in captured['sql']


def test_endodontia_case_details_payload_normalizes_structured_e1_fields():
    form = MultiDict([
        ('coroa', ' Restauração extensa '),
        ('diagnostico', ' Pulpite irreversível provável '),
        ('queixa_inicio', 'espontanea'),
        ('queixa_duracao', 'persistente'),
        ('queixa_intensidade', 'severa'),
        ('queixa_localizacao', 'localizada'),
        ('fatores_exacerbantes[]', 'frio'),
        ('fatores_exacerbantes[]', 'mastigacao'),
        ('fatores_exacerbantes[]', 'valor_invalido'),
        ('fatores_alivio[]', 'analgesico'),
        ('linfadenopatia_cervical', '1'),
        ('fistula_trajeto', '1'),
        ('sondagem_mesial_mm', '4,5'),
        ('tipo_lesao', 'endodontica'),
        ('diagnostico_pulpar', 'necrose_pulpar'),
        ('diagnostico_apical', 'periodontite_apical_assintomatica'),
    ])

    payload = build_case_details_payload(form)

    assert payload['coroa'] == 'Restauração extensa'
    assert payload['diagnostico'] == 'Pulpite irreversível provável'
    assert payload['queixa_inicio'] == 'espontanea'
    assert payload['linfadenopatia_cervical'] is True
    assert payload['fistula_trajeto'] is True
    assert str(payload['sondagem_mesial_mm']) == '4.5'
    assert parse_json_list(payload['fatores_exacerbantes']) == ['frio', 'mastigacao']
    assert parse_json_list(payload['fatores_alivio']) == ['analgesico']
    assert payload['diagnostico_pulpar'] == 'necrose_pulpar'
    assert payload['diagnostico_apical'] == 'periodontite_apical_assintomatica'
    assert payload['cid10_sugerido'] == 'K04.5'
    assert payload['workflow_tipo'] == 'tratamento'
    assert payload['diagnostico_estruturado_status'] == 'completo'


def test_endodontia_case_details_payload_rejects_invalid_probe_depth():
    form = MultiDict([('sondagem_mesial_mm', 'abc')])

    try:
        build_case_details_payload(form)
    except ValueError as exc:
        assert 'Sondagem mesial' in str(exc)
    else:
        raise AssertionError('sondagem inválida deveria gerar ValueError')


def test_anamnesis_risk_summary_uses_existing_anamnesis_without_duplication():
    anamnesis = {
        'tem_alergia': 'Sim',
        'tem_alergia_explica': 'Alergia a dipirona',
        'tomando_medicamento': 'Sim',
        'tomando_medicamento_explica': 'Losartana',
        'gestante': 'Não',
        'sofre_doenca': 'Sim',
        'sofre_doenca_explica': 'Diabetes tipo 2',
        'reacao_anestesia': 'Sim',
        'reacao_anestesia_explica': 'Taquicardia',
    }

    summary = build_anamnesis_risk_summary(anamnesis)

    assert summary['available'] is True
    assert summary['critical_count'] == 2
    assert summary['warning_count'] == 2
    assert [item['label'] for item in summary['items']][:2] == ['Alergia registrada', 'Medicamento em uso']


def test_anamnesis_risk_summary_marks_missing_source():
    summary = build_anamnesis_risk_summary(None)

    assert summary == {
        'available': False,
        'items': [],
        'critical_count': 0,
        'warning_count': 0,
    }


def test_diagnosis_context_identifies_retratamento_and_cid10():
    context = build_diagnosis_context(
        'dente_previamente_tratado',
        'tecidos_apicais_normais',
    )

    assert context['can_advance'] is True
    assert context['status'] == 'completo'
    assert context['workflow_type'] == 'retratamento'
    assert context['cid10'] == 'K04.9'
    assert any(alert['label'] == 'Fluxo de retratamento' for alert in context['alerts'])


def test_diagnosis_context_blocks_polpa_normal_without_justification():
    context = build_diagnosis_context(
        'polpa_normal',
        'tecidos_apicais_normais',
    )

    assert context['can_advance'] is False
    assert context['status'] == 'bloqueado'
    assert context['workflow_type'] == 'avaliacao'
    assert context['blockers'] == ['Polpa normal não libera avanço endodôntico sem justificativa clínica.']


def test_diagnosis_context_allows_polpa_normal_with_auditable_justification():
    context = build_diagnosis_context(
        'polpa_normal',
        'tecidos_apicais_normais',
        'Dor referida persistente e necessidade de investigação complementar.',
    )

    assert context['can_advance'] is True
    assert context['status'] == 'completo'
    assert context['workflow_type'] == 'avaliacao'
    assert any(alert['label'] == 'Polpa normal com justificativa' for alert in context['alerts'])


def test_diagnosis_context_marks_missing_required_diagnoses():
    context = build_diagnosis_context(None, 'abscesso_apical_agudo')

    assert context['can_advance'] is False
    assert context['status'] == 'pendente'
    assert context['missing'] == ['diagnóstico pulpar']
    assert context['cid10'] == 'K04.6'
    assert any(alert['label'] == 'Abscesso apical agudo' for alert in context['alerts'])


def test_endodontia_calculates_crd_with_bregman_formula():
    crd = calculate_crd(Decimal('21'), Decimal('24'), Decimal('20'))

    assert crd == Decimal('25.20')


def test_endodontia_suggests_crt_by_pulp_diagnosis_margin():
    crd = Decimal('25.20')

    assert suggest_crt(crd, 'necrose_pulpar') == Decimal('24.70')
    assert suggest_crt(crd, 'dente_previamente_tratado') == Decimal('24.70')
    assert suggest_crt(crd, 'pulpite_irreversivel_sintomatica') == Decimal('24.20')


def test_endodontia_channel_payload_computes_odontometry_without_override():
    form = MultiDict([
        ('canal[]', 'MV'),
        ('cad[]', '24'),
        ('ponto_referencia_coronario[]', 'Cúspide mésio-vestibular'),
        ('cri_mm[]', '21'),
        ('cai_mm[]', '20'),
        ('crt_final_mm[]', ''),
        ('crt_override_justificativa[]', ''),
        ('localizador_apical_usado[]', '1'),
        ('modelo_localizador[]', 'Root ZX'),
        ('leitura_localizador[]', '0,5'),
        ('confirmacao_eletronica[]', '1'),
        ('lima_inicial[]', '#10'),
        ('lima_final[]', '#35'),
        ('cone[]', '35.04'),
        ('selamento[]', 'AH Plus'),
    ])

    result = build_channel_payloads(form, 'necrose_pulpar')

    assert result['overrides'] == []
    assert len(result['channels']) == 1
    channel = result['channels'][0]
    assert channel['canal'] == 'MV'
    assert channel['crd_mm'] == Decimal('25.20')
    assert channel['crt_sugerido_mm'] == Decimal('24.70')
    assert channel['crt_final_mm'] == Decimal('24.70')
    assert channel['ct'] == '24.7'
    assert channel['localizador_apical_usado'] is True
    assert channel['confirmacao_eletronica'] is True


def test_endodontia_channel_payload_requires_justification_for_crt_override():
    form = MultiDict([
        ('canal[]', 'D'),
        ('cad[]', '24'),
        ('cri_mm[]', '21'),
        ('cai_mm[]', '20'),
        ('crt_final_mm[]', '24.00'),
        ('crt_override_justificativa[]', ''),
    ])

    try:
        build_channel_payloads(form, 'pulpite_irreversivel_sintomatica')
    except ValueError as exc:
        assert 'justifique o CRT final' in str(exc)
    else:
        raise AssertionError('override de CRT sem justificativa deveria gerar ValueError')


def test_endodontia_channel_payload_tracks_justified_crt_override():
    form = MultiDict([
        ('canal[]', 'D'),
        ('cad[]', '24'),
        ('cri_mm[]', '21'),
        ('cai_mm[]', '20'),
        ('crt_final_mm[]', '24.00'),
        ('crt_override_justificativa[]', 'Imagem sugere ápice reabsorvido; manter aquém.'),
    ])

    result = build_channel_payloads(form, 'pulpite_irreversivel_sintomatica')

    assert len(result['overrides']) == 1
    assert result['overrides'][0] == {
        'canal': 'D',
        'crd_mm': '25.2',
        'crt_sugerido_mm': '24.2',
        'crt_final_mm': '24',
        'justificativa': 'Imagem sugere ápice reabsorvido; manter aquém.',
    }


def test_endodontia_typical_channel_suggestion_flags_upper_molar_mv2():
    suggestion = suggest_typical_channels('16')

    assert suggestion['available'] is True
    assert suggestion['group'] == 'Molar superior'
    assert suggestion['channels'] == ['Mésio-vestibular', 'Disto-vestibular', 'Palatino']
    assert any('MV2' in alert for alert in suggestion['alerts'])


def test_endodontia_typical_channel_suggestion_flags_lower_incisor_variation():
    suggestion = suggest_typical_channels('31')

    assert suggestion['available'] is True
    assert suggestion['group'] == 'Incisivo inferior'
    assert suggestion['channels'] == ['Canal principal']
    assert any('vestibular e lingual' in alert for alert in suggestion['alerts'])


def test_endodontia_typical_channel_suggestion_rejects_unknown_notation():
    suggestion = suggest_typical_channels('A')

    assert suggestion['available'] is False
    assert suggestion['channels'] == []
    assert suggestion['alerts'] == ['Elemento dentário não informado em padrão FDI.']


def test_endodontia_session_payload_structures_e4_fields_and_status():
    form = MultiDict([
        ('data', '2026-06-12'),
        ('etapa_realizada', 'obturacao'),
        ('status_sessao', 'realizada'),
        ('evolucao', 'Obturação concluída com controle radiográfico.'),
        ('sessoes_planejadas', '4'),
        ('proxima_sessao_prevista', '2026-06-20'),
        ('janela_retorno_dias', '8'),
        ('observacao_clinica', 'Encaminhar para restauração definitiva.'),
    ])

    payload = build_session_payload(form, next_session_number=3)

    assert payload == {
        'numero_sessao': 3,
        'data': '2026-06-12',
        'evolucao': 'Obturação concluída com controle radiográfico.',
        'etapa_realizada': 'obturacao',
        'status_sessao': 'realizada',
        'sessoes_planejadas': 4,
        'proxima_sessao_prevista': '2026-06-20',
        'janela_retorno_dias': 8,
        'observacao_clinica': 'Encaminhar para restauração definitiva.',
        'status_tratamento': 'obturado_aguardando_restauracao',
    }


def test_endodontia_session_payload_requires_structured_stage():
    form = MultiDict([
        ('data', '2026-06-12'),
        ('evolucao', 'Abertura realizada.'),
    ])

    try:
        build_session_payload(form, next_session_number=1)
    except ValueError as exc:
        assert 'Etapa realizada' in str(exc)
    else:
        raise AssertionError('sessão sem etapa estruturada deveria gerar ValueError')


def test_endodontia_treatment_status_can_be_explicit_for_abandonment():
    assert derive_treatment_status(
        'preparo_parcial',
        'aguardando_retorno',
        explicit_status='abandono',
    ) == 'abandono'


def test_endodontia_session_context_keeps_legacy_followups_compatible():
    endo = {
        'status_tratamento': None,
        'sessoes_planejadas': None,
        'proxima_sessao_prevista': None,
        'janela_retorno_dias': None,
    }
    followups = [
        {'id': 1, 'numero_sessao': None},
        {'id': 2, 'numero_sessao': 4},
    ]

    context = build_session_context(endo, followups)

    assert context['next_number'] == 5
    assert context['status'] == 'aguardando_inicio'
    assert context['status_label'] == 'Aguardando início'


def test_endodontia_protocol_payload_structures_e5_fields():
    form = MultiDict([
        ('lai_mm', '24,5'),
        ('tecnica_instrumentacao', 'rotatoria'),
        ('sistema_instrumentacao', 'ProTaper Gold'),
        ('liga_instrumento', 'niti_tratado'),
        ('solucao_irrigadora', 'hipoclorito_2_5'),
        ('edta_usado', '1'),
        ('tempo_irrigacao_min', '12'),
        ('agitacao_irrigadora', 'ultrassonica'),
        ('volume_irrigacao_ml', '18,5'),
        ('medicacao_intracanal', 'hidroxido_calcio'),
        ('medicacao_veiculo', 'Propilenoglicol'),
        ('medicacao_quantidade', 'Preenchimento do canal'),
        ('selamento_provisorio', 'ionomero_vidro'),
    ])

    payload = build_protocol_payload(form, anamnesis={'tem_alergia_explica': 'Alergia a dipirona'})

    assert payload['lai_mm'] == Decimal('24.50')
    assert payload['tecnica_instrumentacao'] == 'rotatoria'
    assert payload['liga_instrumento'] == 'niti_tratado'
    assert payload['solucao_irrigadora'] == 'hipoclorito_2_5'
    assert payload['edta_usado'] is True
    assert payload['tempo_irrigacao_min'] == 12
    assert payload['volume_irrigacao_ml'] == Decimal('18.50')
    assert payload['medicacao_intracanal'] == 'hidroxido_calcio'
    assert payload['selamento_provisorio'] == 'ionomero_vidro'


def test_endodontia_session_payload_accepts_e5_protocol_fields():
    form = MultiDict([
        ('data', '2026-06-12'),
        ('etapa_realizada', 'medicacao_intracanal'),
        ('status_sessao', 'aguardando_retorno'),
        ('evolucao', 'Preparo químico-mecânico e medicação intracanal.'),
        ('proxima_sessao_prevista', '2026-06-19'),
        ('janela_retorno_dias', '7'),
        ('lai_mm', '23'),
        ('tecnica_instrumentacao', 'reciprocante'),
        ('solucao_irrigadora', 'clorexidina'),
        ('medicacao_intracanal', 'hidroxido_calcio'),
        ('selamento_provisorio', 'coltosol'),
    ])

    payload = build_session_payload(form, next_session_number=2)

    assert payload['numero_sessao'] == 2
    assert payload['status_tratamento'] == 'aguardando_retorno'
    assert payload['lai_mm'] == Decimal('23.00')
    assert payload['tecnica_instrumentacao'] == 'reciprocante'
    assert payload['solucao_irrigadora'] == 'clorexidina'
    assert payload['medicacao_intracanal'] == 'hidroxido_calcio'


def test_endodontia_protocol_blocks_hypochlorite_with_allergy():
    form = MultiDict([
        ('solucao_irrigadora', 'hipoclorito_2_5'),
    ])
    anamnesis = {'tem_alergia': 'Sim', 'tem_alergia_explica': 'Alergia a hipoclorito de sódio'}

    try:
        build_protocol_payload(form, anamnesis=anamnesis)
    except ValueError as exc:
        assert 'hipoclorito' in str(exc).lower()
    else:
        raise AssertionError('hipoclorito deveria ser bloqueado por alergia registrada')


def test_endodontia_protocol_blocks_eugenol_material_with_allergy():
    form = MultiDict([
        ('selamento_provisorio', 'oxido_zinco_eugenol'),
    ])
    anamnesis = {'tem_alergia': 'Sim', 'tem_alergia_explica': 'Eugenol'}

    try:
        build_protocol_payload(form, anamnesis=anamnesis)
    except ValueError as exc:
        assert 'eugenol' in str(exc).lower()
    else:
        raise AssertionError('material eugenólico deveria ser bloqueado por alergia registrada')


def test_endodontia_protocol_safety_context_marks_latex_alert():
    context = build_protocol_safety_context({
        'tem_alergia': 'Sim',
        'tem_alergia_explica': 'Látex e cloro',
    })

    assert context['blocks_hypochlorite'] is True
    assert context['latex_alert'] is True


def test_endodontia_obturation_payload_structures_e6_fields():
    form = MultiDict([
        ('cone_principal_material', 'Guta-percha'),
        ('cone_principal_calibre', '35'),
        ('cone_principal_conicidade', '.04'),
        ('prova_cone', '1'),
        ('tug_back', '1'),
        ('crt_confirmado_mm', '24,5'),
        ('cimento_obturador', 'Biocerâmico XP'),
        ('cimento_classe', 'bioceramico'),
        ('cimento_lote', 'L123'),
        ('cimento_validade', '2027-12-31'),
        ('tecnica_obturacao', 'cone_unico'),
        ('radiografia_final_aprovada', '1'),
        ('restauracao_definitiva_registrada', '1'),
        ('restauracao_definitiva_data', '2026-06-12'),
        ('restauracao_definitiva_material', 'Resina composta'),
        ('selamento_coronario_adequado', '1'),
    ])

    payload = build_obturation_payload(form)

    assert payload['cone_principal_material'] == 'Guta-percha'
    assert payload['prova_cone'] is True
    assert payload['tug_back'] is True
    assert payload['crt_confirmado_mm'] == Decimal('24.50')
    assert payload['cimento_classe'] == 'bioceramico'
    assert payload['tecnica_obturacao'] == 'cone_unico'
    assert payload['radiografia_final_aprovada'] is True
    assert payload['restauracao_definitiva_registrada'] is True
    assert payload['restauracao_definitiva_material'] == 'Resina composta'


def test_endodontia_obturation_blocks_eugenol_sealer_with_allergy():
    form = MultiDict([
        ('cimento_classe', 'oxido_zinco_eugenol'),
    ])
    anamnesis = {'tem_alergia': 'Sim', 'tem_alergia_explica': 'Alergia a eugenol'}

    try:
        build_obturation_payload(form, anamnesis=anamnesis)
    except ValueError as exc:
        assert 'eugenol' in str(exc).lower()
    else:
        raise AssertionError('cimento eugenólico deveria ser bloqueado por alergia registrada')


def test_endodontia_session_payload_marks_treatment_complete_when_restoration_registered():
    form = MultiDict([
        ('data', '2026-06-12'),
        ('etapa_realizada', 'obturacao'),
        ('status_sessao', 'realizada'),
        ('evolucao', 'Obturação final e restauração definitiva registradas.'),
        ('cone_principal_material', 'Guta-percha'),
        ('tecnica_obturacao', 'cone_unico'),
        ('radiografia_final_aprovada', '1'),
        ('restauracao_definitiva_registrada', '1'),
        ('restauracao_definitiva_material', 'Resina composta'),
    ])

    payload = build_session_payload(form, next_session_number=4)

    assert payload['status_tratamento'] == 'concluido'
    assert payload['restauracao_definitiva_registrada'] is True
    assert payload['tecnica_obturacao'] == 'cone_unico'


def test_endodontia_session_payload_keeps_obturation_waiting_restoration_without_restoration():
    form = MultiDict([
        ('data', '2026-06-12'),
        ('etapa_realizada', 'obturacao'),
        ('status_sessao', 'realizada'),
        ('evolucao', 'Obturação final concluída.'),
        ('cone_principal_material', 'Guta-percha'),
        ('radiografia_final_aprovada', '1'),
    ])

    payload = build_session_payload(form, next_session_number=4)

    assert payload['status_tratamento'] == 'obturado_aguardando_restauracao'
    assert payload['radiografia_final_aprovada'] is True


def test_endodontia_proservation_schedule_generates_standard_returns():
    schedule = build_proservation_schedule_payloads(
        {'lesao_periapical_extensa': False},
        '2026-06-12',
    )

    assert [item['tipo_retorno'] for item in schedule] == [
        'proservacao_6m',
        'proservacao_1a',
        'proservacao_2a',
    ]
    assert [item['data_prevista'] for item in schedule] == [
        '2026-12-12',
        '2027-06-12',
        '2028-06-12',
    ]


def test_endodontia_proservation_schedule_adds_48m_for_extensive_lesion():
    schedule = build_proservation_schedule_payloads(
        {'lesao_periapical_extensa': True},
        '2026-06-12',
    )

    assert schedule[-1]['tipo_retorno'] == 'proservacao_4a'
    assert schedule[-1]['data_prevista'] == '2030-06-12'


def test_endodontia_proservation_payload_classifies_strindberg_success():
    form = MultiDict([
        ('data_realizada', '2026-12-12'),
        ('dente_funcao_mastigatoria', '1'),
        ('ausencia_dor_percussao', '1'),
        ('ausencia_dor_palpacao_apical', '1'),
        ('ausencia_edema_mucosa', '1'),
        ('ausencia_fistula', '1'),
        ('espaco_periodontal_normal', '1'),
        ('lamina_dura_integra', '1'),
        ('ausencia_lesao_radiolucida', '1'),
        ('reducao_lesao_preexistente', '1'),
        ('restauracao_tipo', 'resina_composta'),
        ('restauracao_selamento_adequado', '1'),
    ])

    payload = build_proservation_evaluation_payload(form)

    assert payload['resultado_strindberg'] == 'sucesso'
    assert payload['status'] == 'concluido'
    assert payload['restauracao_tipo'] == 'resina_composta'


def test_endodontia_proservation_payload_classifies_strindberg_uncertain_for_radiographic_repair():
    form = MultiDict([
        ('data_realizada', '2026-12-12'),
        ('dente_funcao_mastigatoria', '1'),
        ('ausencia_dor_percussao', '1'),
        ('ausencia_dor_palpacao_apical', '1'),
        ('ausencia_edema_mucosa', '1'),
        ('ausencia_fistula', '1'),
        ('reducao_lesao_preexistente', '1'),
    ])

    payload = build_proservation_evaluation_payload(form)

    assert payload['resultado_strindberg'] == 'duvida'


def test_endodontia_proservation_payload_classifies_strindberg_failure_for_clinical_symptom():
    form = MultiDict([
        ('data_realizada', '2026-12-12'),
        ('dente_funcao_mastigatoria', '1'),
        ('ausencia_dor_palpacao_apical', '1'),
        ('ausencia_edema_mucosa', '1'),
        ('ausencia_fistula', '1'),
        ('espaco_periodontal_normal', '1'),
        ('lamina_dura_integra', '1'),
    ])

    payload = build_proservation_evaluation_payload(form)

    assert payload['resultado_strindberg'] == 'insucesso'


def test_endodontia_proservation_payload_skips_strindberg_when_rescheduled():
    form = MultiDict([
        ('status', 'reagendado'),
        ('resultado_observacoes', 'Paciente remarcou retorno de proservação.'),
    ])

    payload = build_proservation_evaluation_payload(form)

    assert payload['status'] == 'reagendado'
    assert payload['data_realizada'] is None
    assert payload['resultado_strindberg'] is None


def test_endodontia_budget_classifies_tooth_complexity_by_group():
    assert classify_tooth_complexity('11', 1)['complexidade'] == 'baixa'
    premolar = classify_tooth_complexity('24', 2)
    molar = classify_tooth_complexity('36', 4)

    assert premolar['complexidade'] == 'intermediaria'
    assert str(premolar['multiplicador']) == '1.50'
    assert molar['complexidade'] == 'alta'
    assert str(molar['multiplicador']) == '2.50'


def test_endodontia_budget_generates_channel_by_channel_for_retreatment():
    endo = {
        'elemento_dentario': '36',
        'diagnostico_pulpar': 'dente_previamente_tratado',
        'cid10_sugerido': 'K04.9',
        'sessoes_planejadas': 4,
    }
    canais = [
        {'canal': 'MV'},
        {'canal': 'ML'},
        {'canal': 'D'},
    ]
    references = {
        '0307020053': {
            'sigtap_name': 'TRATAMENTO ENDODÔNTICO DE DENTE PERMANENTE COM TRÊS OU MAIS RAÍZES',
            'private_reference': Decimal('1200.00'),
            'public_cost': Decimal('220.00'),
        }
    }

    budget = build_endodontia_budget_items(endo, canais, references)

    assert budget['workflow'] == 'retratamento'
    assert budget['channel_count'] == 3
    assert budget['reference_code'] == '0307020053'
    assert [item['procedimento'] for item in budget['items']] == [
        'retratamento_1_canal',
        'retratamento_por_canal_adicional',
        'retratamento_por_canal_adicional',
    ]
    assert all(item['codigo_cid10'] == 'K04.9' for item in budget['items'])
    assert budget['items'][0]['codigo_tuss'] == 'TUSS-REENDO-001'
    assert budget['items'][1]['codigo_tuss'] == 'TUSS-REENDO-ADD'
    assert budget['items'][0]['valor_unitario'] == Decimal('500.00')


def test_endodontia_budget_blocks_polpa_normal():
    try:
        build_endodontia_budget_items({'elemento_dentario': '11', 'diagnostico_pulpar': 'polpa_normal'}, [], {})
    except ValueError as exc:
        assert 'Polpa normal' in str(exc)
    else:
        raise AssertionError('polpa normal deveria bloquear orçamento endodôntico')


def test_endodontia_budget_summary_totals_references_and_savings():
    summary = build_budget_summary([
        {
            'valor_unitario': Decimal('500.00'),
            'valor_publico_unitario': Decimal('73.33'),
            'economia_estimada_unitaria': Decimal('426.67'),
        },
        {
            'valor_unitario': Decimal('500.00'),
            'valor_publico_unitario': Decimal('73.33'),
            'economia_estimada_unitaria': Decimal('426.67'),
        },
    ])

    assert summary['count'] == 2
    assert summary['total_private'] == Decimal('1000.00')
    assert summary['total_public'] == Decimal('146.66')
    assert summary['total_savings'] == Decimal('853.34')


def test_endodontia_budget_summary_handles_empty_budget():
    summary = build_budget_summary([])

    assert summary['count'] == 0
    assert summary['total_private'] == Decimal('0.00')
    assert summary['total_public'] == Decimal('0.00')
    assert summary['total_savings'] == Decimal('0.00')


def test_endodontia_e10_route_map_registers_critical_workflow_endpoints():
    app = Flask(__name__)
    app.secret_key = 'test'
    app.register_blueprint(endodontia_bp)

    with app.test_request_context():
        assert url_for('endodontia.add_element', patient_id=7) == '/endodontia/7/add_element'
        assert url_for('endodontia.followup', endo_id=9) == '/endodontia/followup/9'
        assert url_for('endodontia.save_case_details', endo_id=9) == '/endodontia/followup/save_details/9'
        assert url_for('endodontia.add_followup', endo_id=9) == '/endodontia/followup/add/9'
        assert url_for('endodontia.upload_image', endo_id=9) == '/endodontia/followup/9/images/upload'
        assert url_for('endodontia.serve_image', image_id=3) == '/endodontia/image/3'
        assert url_for('endodontia.evaluate_proservation', proservation_id=4) == '/endodontia/proservation/4/evaluate'
        assert url_for('endodontia.generate_budget', endo_id=9) == '/endodontia/followup/9/budget/generate'


def test_endodontia_e10_clinical_acceptance_flow_service_level():
    case_payload = build_case_details_payload(MultiDict([
        ('elemento_dentario', '36'),
        ('coroa', 'Restauração extensa com infiltração'),
        ('diagnostico_pulpar', 'necrose_pulpar'),
        ('diagnostico_apical', 'periodontite_apical_assintomatica'),
        ('queixa_inicio', 'espontanea'),
        ('queixa_duracao', 'persistente'),
        ('queixa_intensidade', 'severa'),
        ('queixa_localizacao', 'localizada'),
        ('lesao_periapical_extensa', '1'),
    ]))
    assert case_payload['cid10_sugerido'] == 'K04.5'
    assert case_payload['workflow_tipo'] == 'tratamento'
    assert case_payload['diagnostico_estruturado_status'] == 'completo'
    assert case_payload['lesao_periapical_extensa'] is True

    channels = build_channel_payloads(MultiDict([
        ('canal[]', 'MV'),
        ('canal[]', 'ML'),
        ('canal[]', 'D'),
        ('cad[]', '24'),
        ('cad[]', '24'),
        ('cad[]', '23'),
        ('referencia[]', 'Cúspide mésio-vestibular'),
        ('referencia[]', 'Cúspide mésio-lingual'),
        ('referencia[]', 'Crista marginal distal'),
        ('cri_mm[]', '21'),
        ('cri_mm[]', '20,5'),
        ('cri_mm[]', '20'),
        ('cai_mm[]', '20'),
        ('cai_mm[]', '20'),
        ('cai_mm[]', '20'),
        ('localizador_apical_usado[]', '1'),
        ('localizador_apical_usado[]', '1'),
        ('localizador_apical_usado[]', '1'),
        ('confirmacao_eletronica[]', '1'),
        ('confirmacao_eletronica[]', '1'),
        ('confirmacao_eletronica[]', '1'),
    ]), case_payload['diagnostico_pulpar'])
    assert len(channels['channels']) == 3
    assert channels['channels'][0]['crt_sugerido_mm'] == Decimal('24.70')
    assert channels['overrides'] == []

    safety_anamnesis = {'tem_alergia': 'Sim', 'tem_alergia_explica': 'Alergia a dipirona'}
    preparation = build_session_payload(MultiDict([
        ('data', '2026-06-14'),
        ('etapa_realizada', 'preparo_completo'),
        ('status_sessao', 'realizada'),
        ('evolucao', 'Preparo completo com irrigação e medicação intracanal.'),
        ('sessoes_planejadas', '4'),
        ('lai_mm', '24'),
        ('tecnica_instrumentacao', 'rotatoria'),
        ('sistema_instrumentacao', 'ProTaper Gold'),
        ('liga_instrumento', 'niti_tratado'),
        ('solucao_irrigadora', 'hipoclorito_2_5'),
        ('edta_usado', '1'),
        ('tempo_irrigacao_min', '12'),
        ('agitacao_irrigadora', 'ultrassonica'),
        ('volume_irrigacao_ml', '18'),
        ('medicacao_intracanal', 'hidroxido_calcio'),
        ('medicacao_veiculo', 'Propilenoglicol'),
        ('medicacao_quantidade', 'Preenchimento dos canais'),
        ('selamento_provisorio', 'ionomero_vidro'),
    ]), next_session_number=1, anamnesis=safety_anamnesis)
    assert preparation['status_tratamento'] == 'em_andamento'
    assert preparation['solucao_irrigadora'] == 'hipoclorito_2_5'
    assert preparation['medicacao_intracanal'] == 'hidroxido_calcio'

    obturation = build_session_payload(MultiDict([
        ('data', '2026-06-28'),
        ('etapa_realizada', 'obturacao'),
        ('status_sessao', 'realizada'),
        ('evolucao', 'Obturação final com radiografia de controle.'),
        ('sessoes_planejadas', '4'),
        ('cone_principal_material', 'Guta-percha'),
        ('cone_principal_calibre', '35'),
        ('cone_principal_conicidade', '0.06'),
        ('prova_cone', '1'),
        ('tug_back', '1'),
        ('crt_confirmado_mm', '24,5'),
        ('cimento_obturador', 'AH Plus'),
        ('cimento_classe', 'resinoso'),
        ('cimento_lote', 'LOTE-2026'),
        ('cimento_validade', '2027-06-01'),
        ('tecnica_obturacao', 'condensacao_lateral'),
        ('radiografia_final_aprovada', '1'),
    ]), next_session_number=2, anamnesis=safety_anamnesis)
    assert obturation['status_tratamento'] == 'obturado_aguardando_restauracao'
    assert obturation['radiografia_final_aprovada'] is True

    endo = {
        'elemento_dentario': '36',
        'diagnostico_pulpar': case_payload['diagnostico_pulpar'],
        'cid10_sugerido': case_payload['cid10_sugerido'],
        'lesao_periapical_extensa': case_payload['lesao_periapical_extensa'],
        'sessoes_planejadas': obturation['sessoes_planejadas'],
    }
    schedule = build_proservation_schedule_payloads(endo, obturation['data'])
    assert [item['tipo_retorno'] for item in schedule] == [
        'proservacao_6m',
        'proservacao_1a',
        'proservacao_2a',
        'proservacao_4a',
    ]

    proservation = build_proservation_evaluation_payload(MultiDict([
        ('data_realizada', '2026-12-28'),
        ('dente_funcao_mastigatoria', '1'),
        ('ausencia_dor_percussao', '1'),
        ('ausencia_dor_palpacao_apical', '1'),
        ('ausencia_edema_mucosa', '1'),
        ('ausencia_fistula', '1'),
        ('espaco_periodontal_normal', '1'),
        ('lamina_dura_integra', '1'),
        ('ausencia_lesao_radiolucida', '1'),
        ('reducao_lesao_preexistente', '1'),
        ('restauracao_tipo', 'coroa_ceramica'),
        ('restauracao_selamento_adequado', '1'),
        ('restauracao_data', '2026-07-15'),
    ]))
    assert proservation['resultado_strindberg'] == 'sucesso'
    assert proservation['restauracao_tipo'] == 'coroa_ceramica'

    budget = build_endodontia_budget_items(endo, channels['channels'], {
        '0307020053': {
            'sigtap_name': 'Tratamento endodôntico de dente permanente com três ou mais raízes',
            'private_reference': Decimal('1200.00'),
            'public_cost': Decimal('220.00'),
        }
    })
    summary = build_budget_summary(budget['items'])
    assert budget['reference_code'] == '0307020053'
    assert budget['complexity']['complexidade'] == 'alta'
    assert [item['procedimento'] for item in budget['items']] == [
        'tratamento_canal_1_canal',
        'tratamento_canal_por_canal_adicional',
        'tratamento_canal_por_canal_adicional',
    ]
    assert summary['count'] == 3
    assert summary['total_private'] == Decimal('1200.00')
    assert ENDODONTIA_FORM_OPTIONS['strindberg_result']
