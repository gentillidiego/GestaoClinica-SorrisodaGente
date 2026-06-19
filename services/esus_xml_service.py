"""Geração e validação do XML LEDI da Ficha de Atendimento Odontológico."""

import datetime as dt
import hashlib
import os
import uuid
from collections import OrderedDict

from lxml import etree


NS_DADO_TRANSPORTE = 'http://esus.ufsc.br/dadotransporte'
NS_DADO_INSTALACAO = 'http://esus.ufsc.br/dadoinstalacao'
NS_MASTER = 'http://esus.ufsc.br/fichaatendimentoodontologicomaster'

XSD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'xsd'))
TIPO_DADO_FICHA_ODONTOLOGICA = 5
TP_CDS_ORIGEM = 3
LOCAL_ATENDIMENTO_UBS = 1
TIPO_ATENDIMENTO_CONSULTA_AGENDADA = 2
TIPO_CONSULTA_PRIMEIRA = 1


class EsusXmlValidationError(ValueError):
    """Indica que o XML produzido não atende ao XSD oficial."""

    def __init__(self, errors):
        self.errors = list(errors or [])
        super().__init__('XML e-SUS inválido: ' + '; '.join(self.errors[:3]))


def only_digits(value):
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


def parse_date(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def parse_datetime(value):
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min)
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        parsed_date = parse_date(text)
        return dt.datetime.combine(parsed_date, dt.time.min) if parsed_date else None


def to_epoch_ms(value):
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone(dt.timedelta(hours=-3)))
    return int(parsed.timestamp() * 1000)


def normalize_boolean(value):
    if isinstance(value, bool):
        return value
    normalized = str(value or '').strip().lower()
    if normalized in {'1', 'true', 'sim', 's', 'yes'}:
        return True
    if normalized in {'0', 'false', 'não', 'nao', 'n', 'no'}:
        return False
    return None


def derive_turno(value):
    parsed = parse_datetime(value)
    if parsed is None or parsed.hour < 12:
        return 1
    if parsed.hour < 18:
        return 2
    return 3


def derive_sexo(value):
    normalized = str(value or '').strip().lower()
    if normalized in {'m', 'masc', 'masculino'}:
        return 0
    if normalized in {'f', 'fem', 'feminino'}:
        return 1
    return None


def _sub(parent, tag, text=None, namespace=None, **attributes):
    element = etree.SubElement(
        parent,
        etree.QName(namespace, tag) if namespace else tag,
        **{key: str(value) for key, value in attributes.items()},
    )
    if text is not None:
        element.text = str(text)
    return element


def _stable_transport_uuid(cnes, seed):
    return f'{only_digits(cnes)}-{uuid.uuid5(uuid.NAMESPACE_URL, seed)}'


def build_num_lote(data_inicio, data_fim, professional_id):
    """Gera número de lote estável para a chave idempotente período/profissional."""
    seed = f'{data_inicio}:{data_fim}:{professional_id}'
    return int(hashlib.sha256(seed.encode('utf-8')).hexdigest()[:14], 16)


def _attendance_key(row):
    service_at = parse_datetime(row.get('service_datetime'))
    return (
        row.get('patient_id'),
        service_at.isoformat() if service_at else '',
    )


def group_procedures_by_attendance(rows):
    grouped = OrderedDict()
    for row in sorted(
        rows,
        key=lambda item: (
            parse_datetime(item.get('service_datetime')) or dt.datetime.min,
            item.get('patient_id') or 0,
            item.get('id') or 0,
        ),
    ):
        key = _attendance_key(row)
        if key not in grouped:
            grouped[key] = dict(row)
            grouped[key]['procedures'] = []
        grouped[key]['procedures'].append({
            'id': row.get('id'),
            'code': ''.join(
                char for char in str(row.get('sigtap_code') or '').upper()
                if char.isalnum()
            ),
            'quantity': int(row.get('quantidade') or 1),
        })
    return list(grouped.values())


def _append_installation(parent, tag, settings):
    installation = _sub(parent, tag, namespace=NS_DADO_INSTALACAO)
    _sub(installation, 'contraChave', settings['contra_chave'])
    if settings.get('uuid_instalacao'):
        _sub(installation, 'uuidInstalacao', settings['uuid_instalacao'])
    _sub(installation, 'cpfOuCnpj', only_digits(settings['cpf_cnpj']))
    _sub(installation, 'nomeOuRazaoSocial', settings['nome_razao_social'])
    if settings.get('fone'):
        _sub(installation, 'fone', only_digits(settings['fone']))
    if settings.get('email_institucional'):
        _sub(installation, 'email', settings['email_institucional'])
    if settings.get('versao_sistema'):
        _sub(installation, 'versaoSistema', settings['versao_sistema'])
    if settings.get('nome_banco_dados'):
        _sub(installation, 'nomeBancoDados', settings['nome_banco_dados'])


def build_xml_ficha_odontologica(
    atendimentos,
    settings,
    *,
    data_inicio,
    data_fim,
    professional_id,
    uuid_dado_serializado=None,
    uuid_ficha=None,
    num_lote=None,
):
    """Monta o envelope dadoTransporteTransportXml completo e determinístico."""
    if not atendimentos:
        raise ValueError('Nenhum atendimento pronto para compor a remessa e-SUS.')

    cnes = only_digits(settings.get('cnes'))
    ine = only_digits(settings.get('ine'))
    cod_ibge = only_digits(settings.get('cod_ibge'))
    seed = f'{data_inicio}:{data_fim}:{professional_id}'
    uuid_dado_serializado = uuid_dado_serializado or _stable_transport_uuid(cnes, f'dado:{seed}')
    uuid_ficha = uuid_ficha or _stable_transport_uuid(cnes, f'ficha:{seed}')
    num_lote = num_lote or build_num_lote(data_inicio, data_fim, professional_id)

    root = etree.Element(
        etree.QName(NS_DADO_TRANSPORTE, 'dadoTransporteTransportXml'),
        nsmap={
            'instalacao': NS_DADO_INSTALACAO,
            'transporte': NS_DADO_TRANSPORTE,
            'odonto': NS_MASTER,
        },
    )
    _sub(root, 'uuidDadoSerializado', uuid_dado_serializado)
    _sub(root, 'tipoDadoSerializado', TIPO_DADO_FICHA_ODONTOLOGICA)
    _sub(root, 'codIbge', cod_ibge)
    _sub(root, 'cnesDadoSerializado', cnes)
    _sub(root, 'ineDadoSerializado', ine)
    _sub(root, 'numLote', num_lote)

    master = _sub(root, 'fichaAtendimentoOdontologicoMasterTransport', namespace=NS_MASTER)
    _sub(master, 'uuidFicha', uuid_ficha)
    _sub(master, 'tpCdsOrigem', TP_CDS_ORIGEM)

    grouped_attendances = group_procedures_by_attendance(atendimentos)
    for attendance in grouped_attendances:
        child = _sub(master, 'atendimentosOdontologicos')
        _sub(child, 'numProntuario', attendance.get('patient_id'))

        cns = only_digits(attendance.get('cns'))
        cpf = only_digits(attendance.get('cpf'))
        if cns:
            _sub(child, 'cnsCidadao', cns)
        elif cpf:
            _sub(child, 'cpfCidadao', cpf)

        birth_ms = to_epoch_ms(attendance.get('data_nascimento'))
        if birth_ms is not None:
            _sub(child, 'dtNascimento', birth_ms)

        _sub(child, 'localAtendimento', LOCAL_ATENDIMENTO_UBS)
        gestante = normalize_boolean(attendance.get('gestante'))
        if gestante is not None:
            _sub(child, 'gestante', str(gestante).lower())
        necessidades_especiais = normalize_boolean(attendance.get('necessidades_especiais'))
        if necessidades_especiais is not None:
            _sub(child, 'necessidadesEspeciais', str(necessidades_especiais).lower())

        _sub(child, 'tipoAtendimento', TIPO_ATENDIMENTO_CONSULTA_AGENDADA)
        _sub(child, 'tiposConsultaOdonto', TIPO_CONSULTA_PRIMEIRA)

        for procedure in attendance['procedures']:
            procedure_element = _sub(child, 'procedimentosRealizados')
            _sub(procedure_element, 'coMsProcedimento', procedure['code'])
            _sub(procedure_element, 'quantidade', procedure['quantity'])

        service_datetime = attendance.get('service_datetime')
        _sub(child, 'turno', derive_turno(service_datetime))
        sexo = derive_sexo(attendance.get('genero'))
        if sexo is not None:
            _sub(child, 'sexo', sexo)
        service_ms = to_epoch_ms(service_datetime)
        if service_ms is not None:
            _sub(child, 'dataHoraInicialAtendimento', service_ms)
            _sub(child, 'dataHoraFinalAtendimento', service_ms)

    first = grouped_attendances[0]
    header = _sub(master, 'headerTransport')
    lotacao = _sub(header, 'lotacaoFormPrincipal')
    _sub(lotacao, 'profissionalCNS', only_digits(first.get('professional_cns')))
    _sub(lotacao, 'cboCodigo_2002', only_digits(first.get('professional_cbo')))
    _sub(lotacao, 'cnes', cnes)
    _sub(lotacao, 'ine', ine)
    _sub(header, 'dataAtendimento', to_epoch_ms(first.get('service_datetime')))
    _sub(header, 'codigoIbgeMunicipio', cod_ibge)

    _append_installation(root, 'remetente', settings)
    _append_installation(root, 'originadora', settings)
    _sub(
        root,
        'versao',
        major=int(settings.get('versao_major', 7)),
        minor=int(settings.get('versao_minor', 2)),
        revision=int(settings.get('versao_revision', 1)),
    )

    xml_bytes = etree.tostring(
        root,
        xml_declaration=True,
        encoding='UTF-8',
        pretty_print=True,
    )
    return xml_bytes, {
        'uuid_dado_serializado': uuid_dado_serializado,
        'uuid_ficha': uuid_ficha,
        'num_lote': num_lote,
        'attendance_count': len(grouped_attendances),
    }


def validate_xml_against_xsd(xml_bytes):
    """Valida o envelope e, separadamente, a ficha contida no xs:any lax."""
    envelope_xsd_path = os.path.join(XSD_DIR, 'dadotransporte.xsd')
    master_xsd_path = os.path.join(XSD_DIR, 'fichaatendimentoodontologicomaster.xsd')
    missing_paths = [
        path for path in (envelope_xsd_path, master_xsd_path)
        if not os.path.exists(path)
    ]
    if missing_paths:
        return False, [f'XSD obrigatório não encontrado: {path}' for path in missing_paths]
    try:
        xml_doc = etree.fromstring(xml_bytes)
        envelope_schema = etree.XMLSchema(etree.parse(envelope_xsd_path))
        envelope_valid = envelope_schema.validate(xml_doc)
        errors = [f'envelope: {error}' for error in envelope_schema.error_log]

        master = xml_doc.find(f'{{{NS_MASTER}}}fichaAtendimentoOdontologicoMasterTransport')
        if master is None:
            errors.append('ficha: fichaAtendimentoOdontologicoMasterTransport ausente')
            return False, errors

        master_schema = etree.XMLSchema(etree.parse(master_xsd_path))
        master_valid = master_schema.validate(master)
        errors.extend(f'ficha: {error}' for error in master_schema.error_log)
        return envelope_valid and master_valid, errors
    except (OSError, etree.XMLSyntaxError, etree.XMLSchemaParseError) as exc:
        return False, [str(exc)]


def assert_valid_xml(xml_bytes):
    valid, errors = validate_xml_against_xsd(xml_bytes)
    if not valid:
        raise EsusXmlValidationError(errors)
    return True


def xml_sha256(xml_bytes):
    return hashlib.sha256(xml_bytes).hexdigest()
