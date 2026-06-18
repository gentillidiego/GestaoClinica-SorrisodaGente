"""
Serviço de geração de XML no formato oficial e-SUS APS
Ficha de Atendimento Odontológico — fichaAtendimentoOdontologicoMasterTransport

Referências:
- XSD: scripts/xsd/fichaatendimentoodontologicomaster.xsd
- https://github.com/laboratoriobridge/esusaps-integracao
"""
import datetime as dt
import hashlib
import os
import uuid

from lxml import etree

# ─────────────────────────────────────────
# Namespaces XSD oficiais do e-SUS APS
# ─────────────────────────────────────────
NS_MASTER = 'http://esus.ufsc.br/fichaatendimentoodontologicomaster'
NS_CHILD = 'http://esus.ufsc.br/fichaatendimentoodontologicochild'
NS_LOTACAO = 'http://esus.ufsc.br/lotacaoheader'
NS_VARIAS = 'http://esus.ufsc.br/variaslotacoesheader'
NS_PROC = 'http://esus.ufsc.br/procedimentoquantidade'
NS_ENC = 'http://esus.ufsc.br/encaminhamentoexterno'
NS_MED = 'http://esus.ufsc.br/medicamento'

XSD_DIR = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'xsd')

# ─────────────────────────────────────────
# Enumerações do Dicionário de Dados e-SUS
# ─────────────────────────────────────────

# tipoAtendimento
TIPO_ATENDIMENTO = {
    'urgencia': 1,
    'consulta_agendada': 2,
    'demanda_espontanea': 3,
    'consulta_agendada_cuidado_continuado': 4,
}
TIPO_ATENDIMENTO_DEFAULT = 2  # consulta agendada

# tiposConsultaOdonto
TIPO_CONSULTA_ODONTO = {
    'primeira_consulta': 1,
    'retorno': 2,
    'tratamento_concluido': 3,
    'manutencao': 4,
    'atendimento_urgencia_nao_programado': 5,
}
TIPO_CONSULTA_DEFAULT = 1  # primeira consulta

# turno
TURNO = {
    'manha': 1,
    'tarde': 2,
    'noite': 3,
}

# sexo
SEXO = {
    'M': 0,
    'masculino': 0,
    'F': 1,
    'feminino': 1,
}
SEXO_DEFAULT = 0

# localAtendimento
LOCAL_ATENDIMENTO_UBS = 1

# tpCdsOrigem (sistema terceiro integrado)
TP_CDS_ORIGEM = 3


def _only_digits(value):
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


def _to_epoch_ms(value):
    """Converte date ou datetime para epoch em milissegundos (formato XSD xs:long)."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return int(value.timestamp() * 1000)
    if isinstance(value, dt.date):
        return int(dt.datetime(value.year, value.month, value.day).timestamp() * 1000)
    return None


def _derive_turno(data_hora):
    """Deriva o turno a partir do horário do atendimento."""
    if not data_hora:
        return TURNO['manha']
    if isinstance(data_hora, (dt.date,)) and not isinstance(data_hora, dt.datetime):
        return TURNO['manha']
    hora = data_hora.hour
    if hora < 12:
        return TURNO['manha']
    if hora < 18:
        return TURNO['tarde']
    return TURNO['noite']


def _derive_sexo(sexo_value):
    valor = str(sexo_value or '').strip().upper()
    return SEXO.get(valor, SEXO_DEFAULT)


def _sub(parent, tag, text=None, ns=None):
    """Cria subelemento com ou sem namespace."""
    if ns:
        el = etree.SubElement(parent, f'{{{ns}}}{tag}')
    else:
        el = etree.SubElement(parent, tag)
    if text is not None:
        el.text = str(text)
    return el


def build_xml_ficha_odontologica(atendimentos, cnes, ine, uuid_ficha=None):
    """
    Monta a árvore XML completa da Ficha de Atendimento Odontológico.

    Parâmetros:
        atendimentos: lista de dicts retornados por list_atendimentos_para_remessa()
        cnes: código CNES da unidade (str, 7 dígitos)
        ine: código INE da equipe (str, 10 dígitos)
        uuid_ficha: UUID gerado externamente; se None, gera automaticamente

    Retorna: (xml_bytes: bytes, uuid_ficha: str)
    """
    uuid_ficha = uuid_ficha or str(uuid.uuid4())

    # Elemento raiz
    root = etree.Element(
        f'{{{NS_MASTER}}}fichaAtendimentoOdontologicoMasterTransport',
        nsmap={
            None: NS_MASTER,
            'child': NS_CHILD,
            'lotacao': NS_LOTACAO,
            'varias': NS_VARIAS,
            'proc': NS_PROC,
        }
    )

    _sub(root, 'uuidFicha', uuid_ficha)
    _sub(root, 'tpCdsOrigem', TP_CDS_ORIGEM)

    # Agrupar atendimentos por profissional (headerTransport / variasLotacoesHeader)
    # O XSD permite múltiplos atendimentos por ficha com headerTransport
    # contendo as lotações de cada profissional. Para simplificar, usamos
    # um único lotacaoHeader com os dados do primeiro profissional encontrado
    # (caso haja múltiplos profissionais, gerar fichas separadas).
    profissional_cns = None
    profissional_cbo = None

    for atd in atendimentos:
        child_el = _sub(root, 'atendimentosOdontologicos')

        # Dados do paciente
        num_prontuario = str(atd.get('patient_id') or '')
        cns_cidadao = _only_digits(atd.get('cns')) or None
        cpf_cidadao = _only_digits(atd.get('cpf')) or None

        if num_prontuario:
            _sub(child_el, 'numProntuario', num_prontuario)
        if cns_cidadao:
            _sub(child_el, 'cnsCidadao', cns_cidadao)
        if cpf_cidadao:
            _sub(child_el, 'cpfCidadao', cpf_cidadao)

        dob_ms = _to_epoch_ms(atd.get('data_nascimento'))
        if dob_ms is not None:
            _sub(child_el, 'dtNascimento', dob_ms)

        _sub(child_el, 'localAtendimento', LOCAL_ATENDIMENTO_UBS)

        # Campos clínicos
        gestante = atd.get('gestante')
        if gestante is not None:
            _sub(child_el, 'gestante', str(gestante).lower())

        nec_especiais = atd.get('necessidade_especial')
        if nec_especiais is not None:
            _sub(child_el, 'necessidadesEspeciais', str(bool(nec_especiais)).lower())

        _sub(child_el, 'tipoAtendimento', TIPO_ATENDIMENTO_DEFAULT)
        _sub(child_el, 'tiposConsultaOdonto', TIPO_CONSULTA_DEFAULT)

        # Procedimentos SIGTAP
        proc_code = _only_digits(atd.get('sigtap_code'))
        if proc_code:
            proc_el = _sub(child_el, 'procedimentosRealizados')
            _sub(proc_el, 'codigoProcedimento', proc_code)
            _sub(proc_el, 'quantidade', int(atd.get('quantidade', 1) or 1))

        # Horário / turno
        data_hora = atd.get('criado_em') or atd.get('data_sessao')
        data_hora_ms = _to_epoch_ms(data_hora)
        turno = _derive_turno(data_hora)
        _sub(child_el, 'turno', turno)
        _sub(child_el, 'sexo', _derive_sexo(atd.get('sexo')))
        if data_hora_ms:
            _sub(child_el, 'dataHoraInicialAtendimento', data_hora_ms)
            _sub(child_el, 'dataHoraFinalAtendimento', data_hora_ms)

        # Captura do profissional para o header
        if not profissional_cns and atd.get('professional_cns'):
            profissional_cns = _only_digits(atd.get('professional_cns'))
        if not profissional_cbo and atd.get('professional_cbo'):
            profissional_cbo = _only_digits(atd.get('professional_cbo'))

    # Header de lotação (variasLotacoesHeader)
    header_el = _sub(root, 'headerTransport')
    lotacao_el = _sub(header_el, 'lotacaoHeader')
    if profissional_cns:
        _sub(lotacao_el, 'profissionalCNS', profissional_cns)
    if profissional_cbo:
        _sub(lotacao_el, 'cboCodigo_2002', profissional_cbo)
    _sub(lotacao_el, 'cnes', _only_digits(cnes) or '')
    if ine:
        _sub(lotacao_el, 'ine', _only_digits(ine))

    xml_bytes = etree.tostring(root, xml_declaration=True, encoding='UTF-8', pretty_print=True)
    return xml_bytes, uuid_ficha


def validate_xml_against_xsd(xml_bytes):
    """
    Valida o XML gerado contra o XSD oficial do e-SUS APS.
    Retorna (True, []) se válido ou (False, [lista de erros]) se inválido.
    """
    xsd_path = os.path.join(XSD_DIR, 'fichaatendimentoodontologicomaster.xsd')
    if not os.path.exists(xsd_path):
        return True, ['XSD não encontrado localmente — validação pulada']

    try:
        with open(xsd_path, 'rb') as f:
            xsd_doc = etree.parse(f)
        schema = etree.XMLSchema(xsd_doc)
        xml_doc = etree.fromstring(xml_bytes)
        schema.validate(xml_doc)
        errors = [str(e) for e in schema.error_log]
        return len(errors) == 0, errors
    except Exception as exc:
        return False, [str(exc)]


def xml_sha256(xml_bytes):
    """Retorna o hash SHA-256 hex do conteúdo XML."""
    return hashlib.sha256(xml_bytes).hexdigest()
