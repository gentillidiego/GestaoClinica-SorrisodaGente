import json
import datetime as dt
from decimal import Decimal, InvalidOperation

MM_QUANT = Decimal('0.01')


ENDODONTIA_PAIN_ONSET_OPTIONS = (
    ('espontanea', 'Espontânea'),
    ('provocada', 'Provocada'),
)

ENDODONTIA_PAIN_DURATION_OPTIONS = (
    ('fugaz', 'Fugaz'),
    ('persistente', 'Persistente'),
)

ENDODONTIA_PAIN_INTENSITY_OPTIONS = (
    ('leve', 'Leve'),
    ('moderada', 'Moderada'),
    ('severa', 'Severa'),
    ('insuportavel_pulsatil', 'Insuportável / pulsátil'),
)

ENDODONTIA_PAIN_LOCATION_OPTIONS = (
    ('localizada', 'Localizada'),
    ('difusa_quadrante', 'Difusa no quadrante'),
    ('referida', 'Referida'),
)

ENDODONTIA_EXACERBATING_FACTOR_OPTIONS = (
    ('frio', 'Frio'),
    ('calor', 'Calor'),
    ('mastigacao', 'Mastigação'),
    ('decubito', 'Decúbito'),
    ('espontanea', 'Espontânea'),
)

ENDODONTIA_RELIEF_FACTOR_OPTIONS = (
    ('analgesico', 'Analgésico'),
    ('antiinflamatorio', 'Anti-inflamatório'),
    ('frio', 'Frio'),
    ('calor', 'Calor'),
    ('nenhum', 'Nenhum'),
)

ENDODONTIA_MOBILITY_OPTIONS = (
    ('grau_0', 'Grau 0'),
    ('grau_I', 'Grau I'),
    ('grau_II', 'Grau II'),
    ('grau_III', 'Grau III'),
)

ENDODONTIA_LESION_TYPE_OPTIONS = (
    ('endodontica', 'Endodôntica'),
    ('periodontal', 'Periodontal'),
    ('endo_perio', 'Endo-perio'),
    ('inconclusivo', 'Inconclusivo'),
)

ENDODONTIA_PULP_DIAGNOSIS_OPTIONS = (
    ('polpa_normal', 'Polpa normal'),
    ('pulpite_reversivel', 'Pulpite reversível'),
    ('pulpite_irreversivel_sintomatica', 'Pulpite irreversível sintomática'),
    ('pulpite_irreversivel_assintomatica', 'Pulpite irreversível assintomática'),
    ('necrose_pulpar', 'Necrose pulpar'),
    ('dente_previamente_tratado', 'Dente previamente tratado'),
    ('terapia_previamente_iniciada', 'Terapia previamente iniciada'),
)

ENDODONTIA_APICAL_DIAGNOSIS_OPTIONS = (
    ('tecidos_apicais_normais', 'Tecidos apicais normais'),
    ('periodontite_apical_sintomatica', 'Periodontite apical sintomática'),
    ('periodontite_apical_assintomatica', 'Periodontite apical assintomática'),
    ('abscesso_apical_agudo', 'Abscesso apical agudo'),
    ('abscesso_apical_cronico', 'Abscesso apical crônico'),
    ('osteite_condensante', 'Osteíte condensante'),
)

ENDODONTIA_SESSION_STAGE_OPTIONS = (
    ('abertura', 'Abertura'),
    ('neutralizacao_septica', 'Neutralização séptica'),
    ('odontometria', 'Odontometria'),
    ('preparo_parcial', 'Preparo parcial'),
    ('preparo_completo', 'Preparo completo'),
    ('medicacao_intracanal', 'Medicação intracanal'),
    ('troca_medicacao', 'Troca de medicação'),
    ('obturacao', 'Obturação'),
    ('proservacao', 'Proservação'),
)

ENDODONTIA_SESSION_STATUS_OPTIONS = (
    ('em_andamento', 'Em andamento'),
    ('realizada', 'Realizada'),
    ('cancelada', 'Cancelada'),
    ('aguardando_retorno', 'Aguardando retorno'),
)

ENDODONTIA_TREATMENT_STATUS_OPTIONS = (
    ('aguardando_inicio', 'Aguardando início'),
    ('em_andamento', 'Em andamento'),
    ('aguardando_retorno', 'Aguardando retorno'),
    ('obturado_aguardando_restauracao', 'Obturado aguardando restauração'),
    ('concluido', 'Concluído'),
    ('abandono', 'Abandono'),
    ('retratamento_necessario', 'Retratamento necessário'),
)

ENDODONTIA_INSTRUMENTATION_TECHNIQUE_OPTIONS = (
    ('manual', 'Manual'),
    ('rotatoria', 'Rotatória'),
    ('reciprocante', 'Reciprocante'),
    ('hibrida', 'Híbrida'),
)

ENDODONTIA_INSTRUMENT_ALLOY_OPTIONS = (
    ('aco_inox', 'Aço inoxidável'),
    ('niti_convencional', 'NiTi convencional'),
    ('niti_tratado', 'NiTi tratado termicamente'),
)

ENDODONTIA_IRRIGANT_OPTIONS = (
    ('soro_fisiologico', 'Soro fisiológico'),
    ('clorexidina', 'Clorexidina'),
    ('hipoclorito_0_5', 'Hipoclorito 0,5%'),
    ('hipoclorito_1', 'Hipoclorito 1%'),
    ('hipoclorito_2_5', 'Hipoclorito 2,5%'),
    ('hipoclorito_5_25', 'Hipoclorito 5,25%'),
)

ENDODONTIA_IRRIGATION_AGITATION_OPTIONS = (
    ('sem_agitacao', 'Sem agitação'),
    ('manual_dinamica', 'Manual dinâmica'),
    ('ultrassonica', 'Ultrassônica'),
    ('sonica', 'Sônica'),
    ('pressao_negativa', 'Pressão negativa'),
)

ENDODONTIA_INTRACANAL_MEDICATION_OPTIONS = (
    ('nenhuma', 'Nenhuma'),
    ('hidroxido_calcio', 'Hidróxido de cálcio'),
    ('clorexidina_gel', 'Clorexidina gel'),
    ('pasta_antibiotica', 'Pasta antibiótica'),
    ('formocresol', 'Formocresol'),
    ('outro', 'Outro'),
)

ENDODONTIA_TEMPORARY_SEALING_OPTIONS = (
    ('coltosol', 'Coltosol'),
    ('ionomero_vidro', 'Ionômero de vidro'),
    ('cimpat', 'Cimpat'),
    ('resina_provisoria', 'Resina provisória'),
    ('oxido_zinco_eugenol', 'Óxido de zinco e eugenol'),
    ('outro', 'Outro'),
)

ENDODONTIA_SEALER_CLASS_OPTIONS = (
    ('resinoso', 'Resinoso'),
    ('bioceramico', 'Biocerâmico'),
    ('hidroxido_calcio', 'Hidróxido de cálcio'),
    ('oxido_zinco_eugenol', 'Óxido de zinco e eugenol'),
    ('outro', 'Outro'),
)

ENDODONTIA_OBTURATION_TECHNIQUE_OPTIONS = (
    ('condensacao_lateral', 'Condensação lateral'),
    ('cone_unico', 'Cone único'),
    ('termoplastificada', 'Termoplastificada'),
    ('hibrida', 'Híbrida'),
    ('outro', 'Outro'),
)

ENDODONTIA_PROSERVATION_RETURN_OPTIONS = (
    ('proservacao_6m', 'Proservação 6 meses'),
    ('proservacao_1a', 'Proservação 1 ano'),
    ('proservacao_2a', 'Proservação 2 anos'),
    ('proservacao_4a', 'Proservação 4 anos'),
)

ENDODONTIA_PROSERVATION_STATUS_OPTIONS = (
    ('planejado', 'Planejado'),
    ('concluido', 'Concluído'),
    ('reagendado', 'Reagendado'),
    ('cancelado', 'Cancelado'),
)

ENDODONTIA_STRINDBERG_RESULT_OPTIONS = (
    ('sucesso', 'Sucesso'),
    ('duvida', 'Dúvida'),
    ('insucesso', 'Insucesso'),
)

ENDODONTIA_RESTORATION_TYPE_OPTIONS = (
    ('resina_composta', 'Resina composta'),
    ('coroa_ceramica', 'Coroa cerâmica'),
    ('onlay', 'Onlay'),
    ('nenhuma', 'Nenhuma'),
    ('outro', 'Outro'),
)

ENDODONTIA_BUDGET_STATUS_OPTIONS = (
    ('gerado', 'Gerado'),
    ('aprovado', 'Aprovado'),
    ('cancelado', 'Cancelado'),
)

ENDODONTIA_BUDGET_PROCEDURE_OPTIONS = (
    ('tratamento_canal_1_canal', 'Tratamento de canal - 1 canal'),
    ('tratamento_canal_por_canal_adicional', 'Tratamento de canal - canal adicional'),
    ('retratamento_1_canal', 'Retratamento endodôntico - 1 canal'),
    ('retratamento_por_canal_adicional', 'Retratamento endodôntico - canal adicional'),
)

ENDODONTIA_BUDGET_TUSS_MAP = {
    'tratamento_canal_1_canal': 'TUSS-ENDO-001',
    'tratamento_canal_por_canal_adicional': 'TUSS-ENDO-ADD',
    'retratamento_1_canal': 'TUSS-REENDO-001',
    'retratamento_por_canal_adicional': 'TUSS-REENDO-ADD',
}

ENDODONTIA_SIGTAP_BY_CHANNEL_COUNT = {
    1: '0307020061',
    2: '0307020045',
    3: '0307020053',
}

PULP_CID10_MAP = {
    'pulpite_reversivel': 'K04.0',
    'pulpite_irreversivel_sintomatica': 'K04.0',
    'pulpite_irreversivel_assintomatica': 'K04.0',
    'necrose_pulpar': 'K04.1',
    'dente_previamente_tratado': 'K04.9',
}

APICAL_CID10_MAP = {
    'periodontite_apical_sintomatica': 'K04.5',
    'periodontite_apical_assintomatica': 'K04.5',
    'abscesso_apical_agudo': 'K04.6',
    'abscesso_apical_cronico': 'K04.7',
    'osteite_condensante': 'K04.3',
}

ENDODONTIA_FORM_OPTIONS = {
    'pain_onset': ENDODONTIA_PAIN_ONSET_OPTIONS,
    'pain_duration': ENDODONTIA_PAIN_DURATION_OPTIONS,
    'pain_intensity': ENDODONTIA_PAIN_INTENSITY_OPTIONS,
    'pain_location': ENDODONTIA_PAIN_LOCATION_OPTIONS,
    'exacerbating_factors': ENDODONTIA_EXACERBATING_FACTOR_OPTIONS,
    'relief_factors': ENDODONTIA_RELIEF_FACTOR_OPTIONS,
    'mobility': ENDODONTIA_MOBILITY_OPTIONS,
    'lesion_type': ENDODONTIA_LESION_TYPE_OPTIONS,
    'pulp_diagnosis': ENDODONTIA_PULP_DIAGNOSIS_OPTIONS,
    'apical_diagnosis': ENDODONTIA_APICAL_DIAGNOSIS_OPTIONS,
    'session_stage': ENDODONTIA_SESSION_STAGE_OPTIONS,
    'session_status': ENDODONTIA_SESSION_STATUS_OPTIONS,
    'treatment_status': ENDODONTIA_TREATMENT_STATUS_OPTIONS,
    'instrumentation_technique': ENDODONTIA_INSTRUMENTATION_TECHNIQUE_OPTIONS,
    'instrument_alloy': ENDODONTIA_INSTRUMENT_ALLOY_OPTIONS,
    'irrigant': ENDODONTIA_IRRIGANT_OPTIONS,
    'irrigation_agitation': ENDODONTIA_IRRIGATION_AGITATION_OPTIONS,
    'intracanal_medication': ENDODONTIA_INTRACANAL_MEDICATION_OPTIONS,
    'temporary_sealing': ENDODONTIA_TEMPORARY_SEALING_OPTIONS,
    'sealer_class': ENDODONTIA_SEALER_CLASS_OPTIONS,
    'obturation_technique': ENDODONTIA_OBTURATION_TECHNIQUE_OPTIONS,
    'proservation_return': ENDODONTIA_PROSERVATION_RETURN_OPTIONS,
    'proservation_status': ENDODONTIA_PROSERVATION_STATUS_OPTIONS,
    'strindberg_result': ENDODONTIA_STRINDBERG_RESULT_OPTIONS,
    'restoration_type': ENDODONTIA_RESTORATION_TYPE_OPTIONS,
    'budget_status': ENDODONTIA_BUDGET_STATUS_OPTIONS,
    'budget_procedure': ENDODONTIA_BUDGET_PROCEDURE_OPTIONS,
}

BOOLEAN_FIELDS = (
    'linfadenopatia_cervical',
    'linfadenopatia_submandibular',
    'assimetria_facial',
    'edema_extraoral',
    'edema_submucoso',
    'fistula_trajeto',
    'carie_profunda',
    'restauracao_inadequada',
    'faceta_desgaste',
    'lesao_periapical_extensa',
)

DECIMAL_FIELDS = (
    'sondagem_mesial_mm',
    'sondagem_distal_mm',
    'sondagem_vestibular_mm',
    'sondagem_lingual_palatino_mm',
)

SELECT_FIELDS = {
    'queixa_inicio': ENDODONTIA_PAIN_ONSET_OPTIONS,
    'queixa_duracao': ENDODONTIA_PAIN_DURATION_OPTIONS,
    'queixa_intensidade': ENDODONTIA_PAIN_INTENSITY_OPTIONS,
    'queixa_localizacao': ENDODONTIA_PAIN_LOCATION_OPTIONS,
    'mobilidade': ENDODONTIA_MOBILITY_OPTIONS,
    'tipo_lesao': ENDODONTIA_LESION_TYPE_OPTIONS,
    'diagnostico_pulpar': ENDODONTIA_PULP_DIAGNOSIS_OPTIONS,
    'diagnostico_apical': ENDODONTIA_APICAL_DIAGNOSIS_OPTIONS,
}

TEXT_FIELDS = (
    'queixa_descricao',
    'exame_extraoral_observacoes',
    'fistula_localizacao',
    'exame_intraoral_observacoes',
    'polpa_normal_justificativa',
)

PROSERVATION_RETURN_MONTHS = {
    'proservacao_6m': 6,
    'proservacao_1a': 12,
    'proservacao_2a': 24,
    'proservacao_4a': 48,
}

PROSERVATION_CLINICAL_BOOL_FIELDS = (
    'dente_funcao_mastigatoria',
    'ausencia_dor_percussao',
    'ausencia_dor_palpacao_apical',
    'ausencia_edema_mucosa',
    'ausencia_fistula',
)

PROSERVATION_RADIOGRAPHIC_BOOL_FIELDS = (
    'espaco_periodontal_normal',
    'lamina_dura_integra',
    'ausencia_lesao_radiolucida',
    'reducao_lesao_preexistente',
)

SHORTER_APICAL_MARGIN_DIAGNOSES = {
    'necrose_pulpar',
    'dente_previamente_tratado',
    'terapia_previamente_iniciada',
}

CHANNEL_ARRAY_FIELDS = (
    'canal',
    'cad',
    'referencia',
    'ct',
    'ponto_referencia_coronario',
    'cri_mm',
    'cai_mm',
    'crt_final_mm',
    'crt_override_justificativa',
    'localizador_apical_usado',
    'modelo_localizador',
    'leitura_localizador',
    'confirmacao_eletronica',
    'lima_inicial',
    'lima_final',
    'cone',
    'selamento',
)


def _clean(value):
    value = (value or '').strip()
    return value or None


def _selected(value, options):
    value = _clean(value)
    if not value:
        return None
    valid = {option for option, _label in options}
    return value if value in valid else None


def label_for_option(value, options):
    return dict(options).get(value)


def _as_bool(value):
    return value in ('1', 'true', 'True', 'on', 'sim', 'Sim')


def _as_decimal(value, label):
    value = _clean(value)
    if value is None:
        return None
    normalized = value.replace(',', '.')
    try:
        number = Decimal(normalized)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'{label} deve ser um número em milímetros.') from exc
    if number < 0 or number > 99:
        raise ValueError(f'{label} deve estar entre 0 e 99 mm.')
    return number


def _ensure_decimal(value, label):
    if value is None:
        return None
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, (int, float)):
        number = Decimal(str(value))
    else:
        number = _as_decimal(value, label)
    if number is None:
        return None
    if number < 0 or number > 99:
        raise ValueError(f'{label} deve estar entre 0 e 99 mm.')
    return number


def _quantize_mm(value):
    if value is None:
        return None
    return _ensure_decimal(value, 'Valor').quantize(MM_QUANT)


def _decimal_to_text(value):
    if value is None:
        return None
    text = format(_quantize_mm(value), 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def calculate_crd(cri_mm, cad_mm, cai_mm):
    cri = _ensure_decimal(cri_mm, 'CRI')
    cad = _ensure_decimal(cad_mm, 'CAD')
    cai = _ensure_decimal(cai_mm, 'CAI')
    if cri is None or cad is None or cai is None:
        return None
    if cai == 0:
        raise ValueError('CAI deve ser maior que zero para calcular o CRD.')
    return ((cri * cad) / cai).quantize(MM_QUANT)


def suggest_crt(crd_mm, diagnostico_pulpar):
    crd = _ensure_decimal(crd_mm, 'CRD')
    if crd is None:
        return None
    margin = Decimal('0.50') if diagnostico_pulpar in SHORTER_APICAL_MARGIN_DIAGNOSES else Decimal('1.00')
    suggested = crd - margin
    if suggested < 0:
        suggested = Decimal('0')
    return suggested.quantize(MM_QUANT)


def suggest_typical_channels(elemento_dentario):
    raw = ''.join(char for char in str(elemento_dentario or '') if char.isdigit())
    if len(raw) < 2:
        return {
            'available': False,
            'group': None,
            'channels': [],
            'alerts': ['Elemento dentário não informado em padrão FDI.'],
        }

    quadrant = int(raw[0])
    position = int(raw[1])
    if quadrant not in {1, 2, 3, 4} or position < 1 or position > 8:
        return {
            'available': False,
            'group': None,
            'channels': [],
            'alerts': ['Sugestão anatômica disponível para dentição permanente em padrão FDI.'],
        }

    upper = quadrant in {1, 2}
    arch_label = 'superior' if upper else 'inferior'
    alerts = []

    if position in {1, 2}:
        group = f'Incisivo {arch_label}'
        channels = ['Canal principal']
        if not upper:
            alerts.append('Incisivos inferiores podem apresentar canal vestibular e lingual.')
    elif position == 3:
        group = f'Canino {arch_label}'
        channels = ['Canal principal']
        alerts.append('Confirmar curvatura radicular e comprimento aparente na imagem.')
    elif position in {4, 5}:
        group = f'Pré-molar {arch_label}'
        if upper and position == 4:
            channels = ['Vestibular', 'Palatino']
            alerts.append('Primeiro pré-molar superior costuma ter dois canais, mas pode variar.')
        elif upper:
            channels = ['Canal principal', 'Vestibular/Palatino se bifurcado']
            alerts.append('Segundo pré-molar superior exige busca ativa de bifurcação quando indicada.')
        else:
            channels = ['Canal principal']
            alerts.append('Pré-molares inferiores têm anatomia variável; avaliar divisão no terço médio/apical.')
    else:
        group = f'Molar {arch_label}'
        if upper:
            channels = ['Mésio-vestibular', 'Disto-vestibular', 'Palatino']
            alerts.append('Pesquisar MV2 em molares superiores, especialmente primeiros molares.')
        else:
            channels = ['Mésio-vestibular', 'Mésio-lingual', 'Distal']
            alerts.append('Avaliar se a raiz distal possui canal único ou canais disto-vestibular/disto-lingual.')

    return {
        'available': True,
        'group': group,
        'channels': channels,
        'alerts': alerts,
    }


def _getlist(form_data, key):
    if hasattr(form_data, 'getlist'):
        return form_data.getlist(key)
    value = form_data.get(key)
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _list_value(values, index):
    return values[index] if index < len(values) else None


def _row_has_channel_content(values):
    text_fields = (
        'canal',
        'cad',
        'referencia',
        'ct',
        'ponto_referencia_coronario',
        'cri_mm',
        'cai_mm',
        'crt_final_mm',
        'crt_override_justificativa',
        'modelo_localizador',
        'leitura_localizador',
        'lima_inicial',
        'lima_final',
        'cone',
        'selamento',
    )
    if any(_clean(values.get(field)) for field in text_fields):
        return True
    return _as_bool(values.get('localizador_apical_usado')) or _as_bool(values.get('confirmacao_eletronica'))


def _parse_cad_for_odontometry(cad_text, channel_label, require_numeric=False):
    if not cad_text:
        if require_numeric:
            raise ValueError(f'CAD do canal {channel_label} é obrigatório para calcular a odontometria.')
        return None
    try:
        return _as_decimal(cad_text, f'CAD do canal {channel_label}')
    except ValueError:
        if require_numeric:
            raise
        return None


def build_channel_payloads(form_data, diagnostico_pulpar=None):
    values_by_field = {
        field: _getlist(form_data, f'{field}[]')
        for field in CHANNEL_ARRAY_FIELDS
    }
    row_count = max([len(values) for values in values_by_field.values()] or [0])
    channels = []
    overrides = []

    for index in range(row_count):
        row = {
            field: _list_value(values, index)
            for field, values in values_by_field.items()
        }
        if not _row_has_channel_content(row):
            continue

        channel_name = _clean(row.get('canal')) or f'linha {index + 1}'
        cad_text = _clean(row.get('cad'))
        cri_mm = _as_decimal(row.get('cri_mm'), f'CRI do canal {channel_name}')
        cai_mm = _as_decimal(row.get('cai_mm'), f'CAI do canal {channel_name}')
        has_bregman_input = cri_mm is not None or cai_mm is not None
        cad_mm = _parse_cad_for_odontometry(cad_text, channel_name, require_numeric=has_bregman_input)

        if has_bregman_input and (cri_mm is None or cai_mm is None or cad_mm is None):
            raise ValueError(f'Canal {channel_name}: informe CRI, CAD e CAI para calcular o CRD.')

        crd_mm = calculate_crd(cri_mm, cad_mm, cai_mm) if has_bregman_input else None
        crt_sugerido_mm = suggest_crt(crd_mm, diagnostico_pulpar) if crd_mm is not None else None
        crt_final_mm = _as_decimal(row.get('crt_final_mm'), f'CRT final do canal {channel_name}')
        if crt_final_mm is None and crt_sugerido_mm is not None:
            crt_final_mm = crt_sugerido_mm
        elif crt_final_mm is not None:
            crt_final_mm = _quantize_mm(crt_final_mm)

        override_justification = _clean(row.get('crt_override_justificativa'))
        if crt_sugerido_mm is not None and crt_final_mm is not None and crt_final_mm != crt_sugerido_mm:
            if not override_justification:
                raise ValueError(
                    f'Canal {channel_name}: justifique o CRT final quando ele divergir do CRT sugerido.'
                )
            overrides.append({
                'canal': channel_name,
                'crd_mm': _decimal_to_text(crd_mm),
                'crt_sugerido_mm': _decimal_to_text(crt_sugerido_mm),
                'crt_final_mm': _decimal_to_text(crt_final_mm),
                'justificativa': override_justification,
            })

        leitura_localizador = _as_decimal(
            row.get('leitura_localizador'),
            f'Leitura do localizador do canal {channel_name}',
        )

        channels.append({
            'canal': _clean(row.get('canal')),
            'cad': cad_text,
            'referencia': _clean(row.get('referencia')),
            'ct': _clean(row.get('ct')) or _decimal_to_text(crt_final_mm),
            'ponto_referencia_coronario': (
                _clean(row.get('ponto_referencia_coronario')) or _clean(row.get('referencia'))
            ),
            'cri_mm': _quantize_mm(cri_mm) if cri_mm is not None else None,
            'cai_mm': _quantize_mm(cai_mm) if cai_mm is not None else None,
            'crd_mm': crd_mm,
            'crt_sugerido_mm': crt_sugerido_mm,
            'crt_final_mm': crt_final_mm,
            'crt_override_justificativa': override_justification,
            'localizador_apical_usado': _as_bool(row.get('localizador_apical_usado')),
            'modelo_localizador': _clean(row.get('modelo_localizador')),
            'leitura_localizador': _quantize_mm(leitura_localizador) if leitura_localizador is not None else None,
            'confirmacao_eletronica': _as_bool(row.get('confirmacao_eletronica')),
            'lima_inicial': _clean(row.get('lima_inicial')),
            'lima_final': _clean(row.get('lima_final')),
            'cone': _clean(row.get('cone')),
            'selamento': _clean(row.get('selamento')),
        })

    return {
        'channels': channels,
        'overrides': overrides,
    }


def _selected_list(values, options):
    valid = {option for option, _label in options}
    return [value for value in values if value in valid]


def _json_list(values):
    return json.dumps(values or [], ensure_ascii=False)


def parse_json_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def build_case_details_payload(form_data):
    payload = {
        'coroa': _clean(form_data.get('coroa')),
        'canais_radiculares': _clean(form_data.get('canais_radiculares')),
        'regiao_apical': _clean(form_data.get('regiao_apical')),
        'demais': _clean(form_data.get('demais')),
        'diagnostico': _clean(form_data.get('diagnostico')),
        'grampo': _clean(form_data.get('grampo')),
        'finalidade_protetica': _clean(form_data.get('finalidade_protetica')),
    }

    for field, options in SELECT_FIELDS.items():
        payload[field] = _selected(form_data.get(field), options)
    for field in TEXT_FIELDS:
        payload[field] = _clean(form_data.get(field))
    for field in BOOLEAN_FIELDS:
        payload[field] = _as_bool(form_data.get(field))

    labels = {
        'sondagem_mesial_mm': 'Sondagem mesial',
        'sondagem_distal_mm': 'Sondagem distal',
        'sondagem_vestibular_mm': 'Sondagem vestibular',
        'sondagem_lingual_palatino_mm': 'Sondagem lingual/palatina',
    }
    for field in DECIMAL_FIELDS:
        payload[field] = _as_decimal(form_data.get(field), labels[field])

    payload['fatores_exacerbantes'] = _json_list(
        _selected_list(
            form_data.getlist('fatores_exacerbantes[]'),
            ENDODONTIA_EXACERBATING_FACTOR_OPTIONS,
        )
    )
    payload['fatores_alivio'] = _json_list(
        _selected_list(
            form_data.getlist('fatores_alivio[]'),
            ENDODONTIA_RELIEF_FACTOR_OPTIONS,
        )
    )

    diagnosis = build_diagnosis_context(
        payload.get('diagnostico_pulpar'),
        payload.get('diagnostico_apical'),
        payload.get('polpa_normal_justificativa'),
    )
    payload['cid10_sugerido'] = diagnosis['cid10']
    payload['workflow_tipo'] = diagnosis['workflow_type']
    payload['diagnostico_estruturado_status'] = diagnosis['status']
    return payload


def build_diagnosis_context(pulp_diagnosis=None, apical_diagnosis=None, polpa_normal_justificativa=None):
    pulp_diagnosis = _selected(pulp_diagnosis, ENDODONTIA_PULP_DIAGNOSIS_OPTIONS)
    apical_diagnosis = _selected(apical_diagnosis, ENDODONTIA_APICAL_DIAGNOSIS_OPTIONS)
    justification = _clean(polpa_normal_justificativa)

    missing = []
    if not pulp_diagnosis:
        missing.append('diagnóstico pulpar')
    if not apical_diagnosis:
        missing.append('diagnóstico apical')

    alerts = []
    blockers = []
    workflow_type = 'tratamento'
    cid10 = None

    if pulp_diagnosis == 'polpa_normal':
        workflow_type = 'avaliacao'
        if not justification:
            blockers.append('Polpa normal não libera avanço endodôntico sem justificativa clínica.')
        else:
            alerts.append({
                'tone': 'warning',
                'label': 'Polpa normal com justificativa',
                'detail': 'Avanço permitido mediante justificativa auditável.',
            })
    elif pulp_diagnosis == 'pulpite_reversivel':
        workflow_type = 'conservador'
        alerts.append({
            'tone': 'warning',
            'label': 'Controle conservador sugerido',
            'detail': 'Evite tratamento radical sem justificativa clínica.',
        })
    elif pulp_diagnosis == 'dente_previamente_tratado':
        workflow_type = 'retratamento'
        alerts.append({
            'tone': 'info',
            'label': 'Fluxo de retratamento',
            'detail': 'Caso deve ser conduzido como retratamento endodôntico.',
        })
    elif pulp_diagnosis == 'terapia_previamente_iniciada':
        workflow_type = 'continuidade'
        alerts.append({
            'tone': 'info',
            'label': 'Continuidade de cuidado',
            'detail': 'Verifique registros e terapias anteriores antes de avançar.',
        })

    if pulp_diagnosis == 'pulpite_irreversivel_sintomatica':
        alerts.append({
            'tone': 'warning',
            'label': 'Urgência endodôntica',
            'detail': 'Pulpite irreversível sintomática pode demandar prioridade clínica.',
        })
    if apical_diagnosis == 'periodontite_apical_sintomatica':
        alerts.append({
            'tone': 'warning',
            'label': 'Periodontite apical sintomática',
            'detail': 'Avaliar dor à percussão/palpação e prioridade operacional.',
        })
    if apical_diagnosis == 'abscesso_apical_agudo':
        alerts.append({
            'tone': 'danger',
            'label': 'Abscesso apical agudo',
            'detail': 'Avaliar drenagem, medicação e necessidade de receituário/atestado.',
        })
    if apical_diagnosis == 'abscesso_apical_cronico':
        alerts.append({
            'tone': 'warning',
            'label': 'Abscesso apical crônico',
            'detail': 'Verifique presença e localização de fístula no exame intraoral.',
        })
    if apical_diagnosis == 'osteite_condensante':
        alerts.append({
            'tone': 'info',
            'label': 'Osteíte condensante',
            'detail': 'Registrar achado radiográfico compatível quando houver imagem.',
        })

    if apical_diagnosis in APICAL_CID10_MAP:
        cid10 = APICAL_CID10_MAP[apical_diagnosis]
    elif pulp_diagnosis in PULP_CID10_MAP:
        cid10 = PULP_CID10_MAP[pulp_diagnosis]

    can_advance = not missing and not blockers
    if missing:
        status = 'pendente'
    elif blockers:
        status = 'bloqueado'
    else:
        status = 'completo'

    return {
        'pulp_diagnosis': pulp_diagnosis,
        'pulp_label': label_for_option(pulp_diagnosis, ENDODONTIA_PULP_DIAGNOSIS_OPTIONS),
        'apical_diagnosis': apical_diagnosis,
        'apical_label': label_for_option(apical_diagnosis, ENDODONTIA_APICAL_DIAGNOSIS_OPTIONS),
        'cid10': cid10,
        'workflow_type': workflow_type,
        'workflow_label': {
            'tratamento': 'Tratamento',
            'retratamento': 'Retratamento',
            'continuidade': 'Continuidade terapêutica',
            'conservador': 'Controle conservador',
            'avaliacao': 'Avaliação / sem indicação radical',
        }.get(workflow_type, 'Tratamento'),
        'missing': missing,
        'blockers': blockers,
        'alerts': alerts,
        'can_advance': can_advance,
        'status': status,
    }


def _as_int_range(value, label, minimum=0, maximum=999):
    value = _clean(value)
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{label} deve ser numérico.') from exc
    if number < minimum or number > maximum:
        raise ValueError(f'{label} deve estar entre {minimum} e {maximum}.')
    return number


def _as_date(value, label):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    value = _clean(value)
    if value is None:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return dt.datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    raise ValueError(f'{label} deve ser uma data válida.')


def _as_decimal_range(value, label, minimum=0, maximum=999):
    value = _clean(value)
    if value is None:
        return None
    normalized = value.replace(',', '.')
    try:
        number = Decimal(normalized)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'{label} deve ser numérico.') from exc
    if number < Decimal(str(minimum)) or number > Decimal(str(maximum)):
        raise ValueError(f'{label} deve estar entre {minimum} e {maximum}.')
    return number.quantize(MM_QUANT)


def _add_months(source_date, months):
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(
        source_date.day,
        [
            31,
            29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
            31,
            30,
            31,
            30,
            31,
            31,
            30,
            31,
            30,
            31,
        ][month - 1],
    )
    return dt.date(year, month, day)


def has_extensive_periapical_lesion(endo):
    if not endo:
        return False
    if endo.get('lesao_periapical_extensa'):
        return True
    text = _normalize_for_safety(
        endo.get('regiao_apical'),
        endo.get('demais'),
        endo.get('diagnostico'),
        endo.get('exame_intraoral_observacoes'),
    )
    keywords = (
        'lesao extensa',
        'lesao periapical extensa',
        'rarefacao extensa',
        'rarefacao periapical extensa',
        'grande lesao',
    )
    return any(keyword in text for keyword in keywords)


def build_proservation_schedule_payloads(endo, obturation_date):
    base_date = _as_date(obturation_date, 'Data da obturação')
    if base_date is None:
        raise ValueError('Data da obturação é obrigatória para gerar proservação.')
    return_types = ['proservacao_6m', 'proservacao_1a', 'proservacao_2a']
    if has_extensive_periapical_lesion(endo):
        return_types.append('proservacao_4a')

    return [
        {
            'tipo_retorno': return_type,
            'data_prevista': _add_months(base_date, PROSERVATION_RETURN_MONTHS[return_type]).isoformat(),
            'lembrete_dias': 7,
        }
        for return_type in return_types
    ]


def classify_strindberg_result(payload):
    clinical_values = [payload.get(field) for field in PROSERVATION_CLINICAL_BOOL_FIELDS]
    radiographic_values = [payload.get(field) for field in PROSERVATION_RADIOGRAPHIC_BOOL_FIELDS]
    if all(clinical_values) and all(radiographic_values):
        return 'sucesso'
    if (
        payload.get('criterio_negativo_instavel')
        or not payload.get('dente_funcao_mastigatoria')
        or not payload.get('ausencia_dor_percussao')
        or not payload.get('ausencia_dor_palpacao_apical')
        or not payload.get('ausencia_edema_mucosa')
        or not payload.get('ausencia_fistula')
    ):
        return 'insucesso'
    return 'duvida'


def build_proservation_evaluation_payload(form_data):
    payload = {
        'status': _selected(
            form_data.get('status'),
            ENDODONTIA_PROSERVATION_STATUS_OPTIONS,
        ) or 'concluido',
        'data_realizada': _clean(form_data.get('data_realizada')),
        'clinica_observacoes': _clean(form_data.get('clinica_observacoes')),
        'radiografica_observacoes': _clean(form_data.get('radiografica_observacoes')),
        'resultado_observacoes': _clean(form_data.get('resultado_observacoes')),
        'criterio_negativo_instavel': _as_bool(form_data.get('criterio_negativo_instavel')),
        'restauracao_tipo': _selected(
            form_data.get('restauracao_tipo'),
            ENDODONTIA_RESTORATION_TYPE_OPTIONS,
        ),
        'restauracao_selamento_adequado': _as_bool(form_data.get('restauracao_selamento_adequado')),
        'restauracao_data': _clean(form_data.get('restauracao_data')),
        'restauracao_observacoes': _clean(form_data.get('restauracao_observacoes')),
    }
    for field in PROSERVATION_CLINICAL_BOOL_FIELDS:
        payload[field] = _as_bool(form_data.get(field))
    for field in PROSERVATION_RADIOGRAPHIC_BOOL_FIELDS:
        payload[field] = _as_bool(form_data.get(field))

    if payload['status'] == 'concluido':
        if not payload['data_realizada']:
            raise ValueError('Informe a data realizada da proservação.')
        payload['resultado_strindberg'] = classify_strindberg_result(payload)
    else:
        payload['resultado_strindberg'] = None
    return payload


def classify_tooth_complexity(elemento_dentario, channel_count=None):
    raw = ''.join(char for char in str(elemento_dentario or '') if char.isdigit())
    position = int(raw[1]) if len(raw) >= 2 else None
    channel_count = int(channel_count or 0)

    if position in {1, 2, 3}:
        return {
            'grupo': 'incisivo_canino',
            'label': 'Incisivos / caninos',
            'complexidade': 'baixa',
            'multiplicador': Decimal('1.00'),
        }
    if position in {4, 5}:
        multiplier = Decimal('1.50') if channel_count >= 2 else Decimal('1.30')
        return {
            'grupo': 'pre_molar',
            'label': 'Pré-molares',
            'complexidade': 'intermediaria',
            'multiplicador': multiplier,
        }
    if position in {6, 7, 8}:
        multiplier = Decimal('2.50') if channel_count >= 4 else Decimal('1.80')
        return {
            'grupo': 'molar',
            'label': 'Molares',
            'complexidade': 'alta',
            'multiplicador': multiplier,
        }
    return {
        'grupo': 'indefinido',
        'label': 'Grupo indefinido',
        'complexidade': 'avaliar',
        'multiplicador': Decimal('1.00'),
    }


def _budget_reference_code(channel_count):
    if channel_count <= 1:
        return ENDODONTIA_SIGTAP_BY_CHANNEL_COUNT[1]
    if channel_count == 2:
        return ENDODONTIA_SIGTAP_BY_CHANNEL_COUNT[2]
    return ENDODONTIA_SIGTAP_BY_CHANNEL_COUNT[3]


def _as_money(value):
    if value in (None, ''):
        return Decimal('0.00')
    if isinstance(value, Decimal):
        return value.quantize(Decimal('0.01'))
    return Decimal(str(value)).quantize(Decimal('0.01'))


def _channel_names(canais, elemento_dentario):
    names = []
    for index, channel in enumerate(canais or [], start=1):
        name = _clean((channel or {}).get('canal')) or f'Canal {index}'
        names.append(name)
    if names:
        return names
    suggestions = suggest_typical_channels(elemento_dentario)
    suggested = suggestions.get('channels') or []
    return suggested or ['Canal principal']


def build_endodontia_budget_items(endo, canais, cost_references=None):
    endo = endo or {}
    channel_names = _channel_names(canais, endo.get('elemento_dentario'))
    channel_count = len(channel_names)
    if channel_count < 1:
        raise ValueError('Informe ao menos um canal para gerar orçamento endodôntico.')
    if endo.get('diagnostico_pulpar') == 'polpa_normal':
        raise ValueError('Polpa normal bloqueia geração de orçamento endodôntico para tratamento radical.')

    workflow = 'retratamento' if endo.get('diagnostico_pulpar') == 'dente_previamente_tratado' else 'tratamento'
    complexity = classify_tooth_complexity(endo.get('elemento_dentario'), channel_count=channel_count)
    reference_code = _budget_reference_code(channel_count)
    reference = (cost_references or {}).get(reference_code) or {}
    sigtap_name = reference.get('sigtap_name') or reference.get('name')
    private_total = _as_money(reference.get('private_reference'))
    public_total = _as_money(reference.get('public_cost'))
    if private_total == Decimal('0.00'):
        private_total = Decimal('0.00')
    if workflow == 'retratamento':
        private_total = (private_total * Decimal('1.25')).quantize(Decimal('0.01'))

    unit_private = (private_total / Decimal(channel_count)).quantize(Decimal('0.01'))
    unit_public = (public_total / Decimal(channel_count)).quantize(Decimal('0.01'))
    unit_savings = max(unit_private - unit_public, Decimal('0.00')).quantize(Decimal('0.01'))
    planned_sessions = endo.get('sessoes_planejadas') or max(2, min(6, channel_count + 1))

    items = []
    for index, channel_name in enumerate(channel_names, start=1):
        if workflow == 'retratamento':
            procedure = 'retratamento_1_canal' if index == 1 else 'retratamento_por_canal_adicional'
        else:
            procedure = 'tratamento_canal_1_canal' if index == 1 else 'tratamento_canal_por_canal_adicional'
        items.append({
            'dente_numero': str(endo.get('elemento_dentario') or ''),
            'canal_id': channel_name,
            'procedimento': procedure,
            'procedimento_label': dict(ENDODONTIA_BUDGET_PROCEDURE_OPTIONS).get(procedure, procedure),
            'codigo_tuss': ENDODONTIA_BUDGET_TUSS_MAP[procedure],
            'codigo_sigtap': reference_code,
            'sigtap_name': sigtap_name,
            'codigo_cid10': endo.get('cid10_sugerido'),
            'valor_unitario': unit_private,
            'valor_publico_unitario': unit_public,
            'economia_estimada_unitaria': unit_savings,
            'sessoes_previstas': planned_sessions,
            'complexidade': complexity['complexidade'],
            'grupo_dentario': complexity['grupo'],
            'multiplicador': complexity['multiplicador'],
            'observacoes': (
                f"{complexity['label']} · {workflow.capitalize()} · "
                f"referência SIGTAP {reference_code}"
            ),
        })
    return {
        'items': items,
        'workflow': workflow,
        'complexity': complexity,
        'channel_count': channel_count,
        'reference_code': reference_code,
    }


def build_budget_summary(items):
    items = items or []
    total_private = sum(
        (_as_money(item.get('valor_unitario')) for item in items),
        Decimal('0.00'),
    )
    total_public = sum(
        (_as_money(item.get('valor_publico_unitario')) for item in items),
        Decimal('0.00'),
    )
    total_savings = sum(
        (_as_money(item.get('economia_estimada_unitaria')) for item in items),
        Decimal('0.00'),
    )
    return {
        'count': len(items),
        'total_private': total_private.quantize(Decimal('0.01')),
        'total_public': total_public.quantize(Decimal('0.01')),
        'total_savings': total_savings.quantize(Decimal('0.01')),
    }


def _anamnesis_allergy_text(anamnesis):
    if not anamnesis:
        return ''
    return _normalize_for_safety(
        anamnesis.get('tem_alergia'),
        anamnesis.get('tem_alergia_explica'),
        anamnesis.get('reacao_anestesia'),
        anamnesis.get('reacao_anestesia_explica'),
    )


def _normalize_for_safety(*values):
    replacements = {
        'á': 'a',
        'à': 'a',
        'ã': 'a',
        'â': 'a',
        'é': 'e',
        'ê': 'e',
        'í': 'i',
        'ó': 'o',
        'ô': 'o',
        'õ': 'o',
        'ú': 'u',
        'ç': 'c',
    }
    text = ' '.join(str(value or '').lower() for value in values if value is not None)
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def build_protocol_safety_context(anamnesis):
    allergy_text = _anamnesis_allergy_text(anamnesis)
    return {
        'has_allergy_source': bool(allergy_text.strip()),
        'allergy_text': allergy_text,
        'blocks_hypochlorite': 'hipoclorito' in allergy_text or 'cloro' in allergy_text,
        'blocks_eugenol': 'eugenol' in allergy_text,
        'latex_alert': 'latex' in allergy_text,
    }


def _protocol_uses_hypochlorite(irrigant):
    return (irrigant or '').startswith('hipoclorito')


def _protocol_uses_eugenol(payload):
    selected_sealing = payload.get('selamento_provisorio') == 'oxido_zinco_eugenol'
    selected_sealer = payload.get('cimento_classe') == 'oxido_zinco_eugenol'
    free_text = _normalize_for_safety(
        payload.get('medicacao_intracanal_outra'),
        payload.get('selamento_provisorio_outro'),
        payload.get('cimento_obturador'),
        payload.get('cimento_classe_outro'),
        payload.get('protocolo_observacoes'),
        payload.get('irrigacao_observacoes'),
        payload.get('controle_qualidade_observacoes'),
    )
    return selected_sealing or selected_sealer or 'eugenol' in free_text


def build_protocol_payload(form_data, anamnesis=None):
    payload = {
        'lai_mm': _as_decimal_range(form_data.get('lai_mm'), 'LAI', 0, 99),
        'tecnica_instrumentacao': _selected(
            form_data.get('tecnica_instrumentacao'),
            ENDODONTIA_INSTRUMENTATION_TECHNIQUE_OPTIONS,
        ),
        'sistema_instrumentacao': _clean(form_data.get('sistema_instrumentacao')),
        'liga_instrumento': _selected(
            form_data.get('liga_instrumento'),
            ENDODONTIA_INSTRUMENT_ALLOY_OPTIONS,
        ),
        'protocolo_observacoes': _clean(form_data.get('protocolo_observacoes')),
        'solucao_irrigadora': _selected(form_data.get('solucao_irrigadora'), ENDODONTIA_IRRIGANT_OPTIONS),
        'edta_usado': _as_bool(form_data.get('edta_usado')),
        'tempo_irrigacao_min': _as_int_range(form_data.get('tempo_irrigacao_min'), 'Tempo de irrigação', 0, 240),
        'agitacao_irrigadora': _selected(
            form_data.get('agitacao_irrigadora'),
            ENDODONTIA_IRRIGATION_AGITATION_OPTIONS,
        ),
        'volume_irrigacao_ml': _as_decimal_range(form_data.get('volume_irrigacao_ml'), 'Volume de irrigação', 0, 999),
        'irrigacao_observacoes': _clean(form_data.get('irrigacao_observacoes')),
        'medicacao_intracanal': _selected(
            form_data.get('medicacao_intracanal'),
            ENDODONTIA_INTRACANAL_MEDICATION_OPTIONS,
        ),
        'medicacao_intracanal_outra': _clean(form_data.get('medicacao_intracanal_outra')),
        'medicacao_veiculo': _clean(form_data.get('medicacao_veiculo')),
        'medicacao_quantidade': _clean(form_data.get('medicacao_quantidade')),
        'selamento_provisorio': _selected(
            form_data.get('selamento_provisorio'),
            ENDODONTIA_TEMPORARY_SEALING_OPTIONS,
        ),
        'selamento_provisorio_outro': _clean(form_data.get('selamento_provisorio_outro')),
    }

    safety = build_protocol_safety_context(anamnesis)
    if safety['blocks_hypochlorite'] and _protocol_uses_hypochlorite(payload['solucao_irrigadora']):
        raise ValueError('Anamnese registra alergia compatível com hipoclorito/cloro. Selecione outra solução irrigadora.')
    if safety['blocks_eugenol'] and _protocol_uses_eugenol(payload):
        raise ValueError('Anamnese registra alergia a eugenol. Selecione material sem eugenol.')
    if payload['medicacao_intracanal'] == 'outro' and not payload['medicacao_intracanal_outra']:
        raise ValueError('Descreva a medicação intracanal quando selecionar Outro.')
    if payload['selamento_provisorio'] == 'outro' and not payload['selamento_provisorio_outro']:
        raise ValueError('Descreva o selamento provisório quando selecionar Outro.')

    return payload


def build_obturation_payload(form_data, anamnesis=None):
    payload = {
        'cone_principal_material': _clean(form_data.get('cone_principal_material')),
        'cone_principal_calibre': _clean(form_data.get('cone_principal_calibre')),
        'cone_principal_conicidade': _clean(form_data.get('cone_principal_conicidade')),
        'prova_cone': _as_bool(form_data.get('prova_cone')),
        'tug_back': _as_bool(form_data.get('tug_back')),
        'crt_confirmado_mm': _as_decimal_range(form_data.get('crt_confirmado_mm'), 'CRT confirmado', 0, 99),
        'cimento_obturador': _clean(form_data.get('cimento_obturador')),
        'cimento_classe': _selected(form_data.get('cimento_classe'), ENDODONTIA_SEALER_CLASS_OPTIONS),
        'cimento_classe_outro': _clean(form_data.get('cimento_classe_outro')),
        'cimento_lote': _clean(form_data.get('cimento_lote')),
        'cimento_validade': _clean(form_data.get('cimento_validade')),
        'tecnica_obturacao': _selected(form_data.get('tecnica_obturacao'), ENDODONTIA_OBTURATION_TECHNIQUE_OPTIONS),
        'tecnica_obturacao_outra': _clean(form_data.get('tecnica_obturacao_outra')),
        'radiografia_final_aprovada': _as_bool(form_data.get('radiografia_final_aprovada')),
        'radiografia_final_gaps': _as_bool(form_data.get('radiografia_final_gaps')),
        'radiografia_final_voids': _as_bool(form_data.get('radiografia_final_voids')),
        'controle_qualidade_observacoes': _clean(form_data.get('controle_qualidade_observacoes')),
        'restauracao_definitiva_registrada': _as_bool(form_data.get('restauracao_definitiva_registrada')),
        'restauracao_definitiva_data': _clean(form_data.get('restauracao_definitiva_data')),
        'restauracao_definitiva_material': _clean(form_data.get('restauracao_definitiva_material')),
        'selamento_coronario_adequado': _as_bool(form_data.get('selamento_coronario_adequado')),
        'restauracao_observacoes': _clean(form_data.get('restauracao_observacoes')),
    }

    safety = build_protocol_safety_context(anamnesis)
    if safety['blocks_eugenol'] and _protocol_uses_eugenol(payload):
        raise ValueError('Anamnese registra alergia a eugenol. Selecione cimento/material sem eugenol.')
    if payload['cimento_classe'] == 'outro' and not payload['cimento_classe_outro']:
        raise ValueError('Descreva a classe do cimento obturador quando selecionar Outro.')
    if payload['tecnica_obturacao'] == 'outro' and not payload['tecnica_obturacao_outra']:
        raise ValueError('Descreva a técnica de obturação quando selecionar Outra.')
    if payload['restauracao_definitiva_registrada'] and not payload['restauracao_definitiva_material']:
        raise ValueError('Informe o material da restauração definitiva.')

    return payload


def derive_treatment_status(session_stage, session_status, explicit_status=None):
    explicit_status = _selected(explicit_status, ENDODONTIA_TREATMENT_STATUS_OPTIONS)
    if explicit_status:
        return explicit_status
    session_stage = _selected(session_stage, ENDODONTIA_SESSION_STAGE_OPTIONS)
    session_status = _selected(session_status, ENDODONTIA_SESSION_STATUS_OPTIONS)

    if session_status == 'cancelada':
        return 'em_andamento'
    if session_stage == 'obturacao' and session_status == 'realizada':
        return 'obturado_aguardando_restauracao'
    if session_stage == 'proservacao' and session_status == 'realizada':
        return 'concluido'
    if session_status == 'aguardando_retorno':
        return 'aguardando_retorno'
    return 'em_andamento'


def build_session_payload(form_data, next_session_number, anamnesis=None):
    try:
        session_number = int(next_session_number)
    except (TypeError, ValueError) as exc:
        raise ValueError('Número da sessão inválido.') from exc
    if session_number < 1:
        raise ValueError('Número da sessão deve ser maior que zero.')

    data = _clean(form_data.get('data'))
    evolucao = _clean(form_data.get('evolucao'))
    session_stage = _selected(form_data.get('etapa_realizada'), ENDODONTIA_SESSION_STAGE_OPTIONS)
    session_status = _selected(form_data.get('status_sessao'), ENDODONTIA_SESSION_STATUS_OPTIONS) or 'realizada'
    planned_sessions = _clean(form_data.get('sessoes_planejadas'))
    next_date = _clean(form_data.get('proxima_sessao_prevista'))
    return_window = _clean(form_data.get('janela_retorno_dias'))
    clinical_note = _clean(form_data.get('observacao_clinica'))
    explicit_treatment_status = _selected(
        form_data.get('status_tratamento'),
        ENDODONTIA_TREATMENT_STATUS_OPTIONS,
    )

    if not data:
        raise ValueError('Data da sessão é obrigatória.')
    if not session_stage:
        raise ValueError('Etapa realizada é obrigatória.')
    if not evolucao:
        raise ValueError('Procedimento executado/evolução é obrigatório.')

    if planned_sessions is not None:
        try:
            planned_sessions = int(planned_sessions)
        except ValueError as exc:
            raise ValueError('Total de sessões planejadas deve ser numérico.') from exc
        if planned_sessions < 1 or planned_sessions > 99:
            raise ValueError('Total de sessões planejadas deve estar entre 1 e 99.')

    if return_window is not None:
        try:
            return_window = int(return_window)
        except ValueError as exc:
            raise ValueError('Janela de retorno deve ser numérica.') from exc
        if return_window < 0 or return_window > 365:
            raise ValueError('Janela de retorno deve estar entre 0 e 365 dias.')

    treatment_status = derive_treatment_status(
        session_stage,
        session_status,
        explicit_treatment_status,
    )
    protocol_payload = build_protocol_payload(form_data, anamnesis=anamnesis)
    obturation_payload = build_obturation_payload(form_data, anamnesis=anamnesis)
    if obturation_payload.get('restauracao_definitiva_registrada') and not explicit_treatment_status:
        treatment_status = 'concluido'

    payload = {
        'numero_sessao': session_number,
        'data': data,
        'evolucao': evolucao,
        'etapa_realizada': session_stage,
        'status_sessao': session_status,
        'sessoes_planejadas': planned_sessions,
        'proxima_sessao_prevista': next_date,
        'janela_retorno_dias': return_window,
        'observacao_clinica': clinical_note,
        'status_tratamento': treatment_status,
    }
    if any(value not in (None, '', False) for value in protocol_payload.values()):
        payload.update(protocol_payload)
    if any(value not in (None, '', False) for value in obturation_payload.values()):
        payload.update(obturation_payload)
    return payload


def build_session_context(endo, followups):
    followups = followups or []
    numbers = [
        row.get('numero_sessao')
        for row in followups
        if row.get('numero_sessao') is not None
    ]
    next_number = (max(numbers) + 1) if numbers else (len(followups) + 1)
    status = (endo or {}).get('status_tratamento') or 'aguardando_inicio'
    return {
        'next_number': next_number,
        'status': status,
        'status_label': label_for_option(status, ENDODONTIA_TREATMENT_STATUS_OPTIONS) or 'Aguardando início',
        'planned_sessions': (endo or {}).get('sessoes_planejadas'),
        'next_session_date': (endo or {}).get('proxima_sessao_prevista'),
        'return_window_days': (endo or {}).get('janela_retorno_dias'),
        'stage_labels': dict(ENDODONTIA_SESSION_STAGE_OPTIONS),
        'session_status_labels': dict(ENDODONTIA_SESSION_STATUS_OPTIONS),
        'treatment_status_labels': dict(ENDODONTIA_TREATMENT_STATUS_OPTIONS),
        'instrumentation_technique_labels': dict(ENDODONTIA_INSTRUMENTATION_TECHNIQUE_OPTIONS),
        'instrument_alloy_labels': dict(ENDODONTIA_INSTRUMENT_ALLOY_OPTIONS),
        'irrigant_labels': dict(ENDODONTIA_IRRIGANT_OPTIONS),
        'irrigation_agitation_labels': dict(ENDODONTIA_IRRIGATION_AGITATION_OPTIONS),
        'intracanal_medication_labels': dict(ENDODONTIA_INTRACANAL_MEDICATION_OPTIONS),
        'temporary_sealing_labels': dict(ENDODONTIA_TEMPORARY_SEALING_OPTIONS),
        'sealer_class_labels': dict(ENDODONTIA_SEALER_CLASS_OPTIONS),
        'obturation_technique_labels': dict(ENDODONTIA_OBTURATION_TECHNIQUE_OPTIONS),
        'proservation_return_labels': dict(ENDODONTIA_PROSERVATION_RETURN_OPTIONS),
        'proservation_status_labels': dict(ENDODONTIA_PROSERVATION_STATUS_OPTIONS),
        'strindberg_result_labels': dict(ENDODONTIA_STRINDBERG_RESULT_OPTIONS),
        'restoration_type_labels': dict(ENDODONTIA_RESTORATION_TYPE_OPTIONS),
        'budget_status_labels': dict(ENDODONTIA_BUDGET_STATUS_OPTIONS),
        'budget_procedure_labels': dict(ENDODONTIA_BUDGET_PROCEDURE_OPTIONS),
    }


def _is_affirmative(value):
    return str(value or '').strip().lower() in {'sim', 's', 'true', '1', 'yes'}


def _risk_item(label, value=None, tone='warning'):
    return {
        'label': label,
        'value': value,
        'tone': tone,
    }


def build_anamnesis_risk_summary(anamnesis):
    if not anamnesis:
        return {
            'available': False,
            'items': [],
            'critical_count': 0,
            'warning_count': 0,
        }

    items = []
    if _is_affirmative(anamnesis.get('tem_alergia')) or _clean(anamnesis.get('tem_alergia_explica')):
        items.append(_risk_item('Alergia registrada', anamnesis.get('tem_alergia_explica'), 'danger'))
    if _is_affirmative(anamnesis.get('tomando_medicamento')) or _clean(anamnesis.get('tomando_medicamento_explica')):
        items.append(_risk_item('Medicamento em uso', anamnesis.get('tomando_medicamento_explica'), 'warning'))
    if _is_affirmative(anamnesis.get('sofre_doenca')) or _clean(anamnesis.get('sofre_doenca_explica')):
        items.append(_risk_item('Condição sistêmica', anamnesis.get('sofre_doenca_explica'), 'warning'))
    if _is_affirmative(anamnesis.get('tratamento_medico')) or _clean(anamnesis.get('tratamento_medico_explica')):
        items.append(_risk_item('Tratamento médico atual', anamnesis.get('tratamento_medico_explica'), 'warning'))
    if _is_affirmative(anamnesis.get('gestante')):
        detail = f"{anamnesis.get('gestante_semanas')} semana(s)" if anamnesis.get('gestante_semanas') else None
        items.append(_risk_item('Gestação', detail, 'danger'))
    if _is_affirmative(anamnesis.get('sangramento_cortar')):
        items.append(_risk_item('Relata sangramento ao cortar', None, 'warning'))
    if _is_affirmative(anamnesis.get('reacao_anestesia')) or _clean(anamnesis.get('reacao_anestesia_explica')):
        items.append(_risk_item('Reação à anestesia', anamnesis.get('reacao_anestesia_explica'), 'danger'))
    if _is_affirmative(anamnesis.get('fez_cirurgia')) or _clean(anamnesis.get('fez_cirurgia_explica')):
        items.append(_risk_item('Histórico cirúrgico', anamnesis.get('fez_cirurgia_explica'), 'info'))
    if _is_affirmative(anamnesis.get('foi_hospitalizado')) or _clean(anamnesis.get('foi_hospitalizado_explica')):
        items.append(_risk_item('Hospitalização prévia', anamnesis.get('foi_hospitalizado_explica'), 'info'))

    return {
        'available': True,
        'items': items,
        'critical_count': len([item for item in items if item['tone'] == 'danger']),
        'warning_count': len([item for item in items if item['tone'] == 'warning']),
    }
