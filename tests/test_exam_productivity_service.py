import services.exam_productivity_service as exam_productivity_service
from services.exam_productivity_service import credit_exam_request_productivity


def _exam_request(**overrides):
    base = {
        'id': 1,
        'patient_id': 10,
        'tipo': 'imagem',
        'tipo_imagem': 'Panorâmica',
        'categoria': None,
        'requested_by': 5,
    }
    base.update(overrides)
    return base


def _fake_get_sigtap_procedure(code, competence=None):
    return {'code': code, 'name': f'Procedimento {code}', 'competence': '202603'}


def test_credit_returns_empty_list_when_no_exam_request():
    assert credit_exam_request_productivity(None, exam_id=99) == []


def test_credit_image_request_creates_one_procedure(monkeypatch):
    captured = {}
    audited = []

    def fake_query(sql, params=()):
        return []  # nenhum lançamento prévio para este exam_request_id

    def fake_execute(sql, params=()):
        captured['sql'] = sql
        captured['params'] = params
        return 42

    monkeypatch.setattr(exam_productivity_service, 'query', fake_query)
    monkeypatch.setattr(exam_productivity_service, 'execute', fake_execute)
    monkeypatch.setattr(exam_productivity_service, 'get_sigtap_procedure', _fake_get_sigtap_procedure)
    monkeypatch.setattr(
        exam_productivity_service,
        'audit_log',
        lambda **kwargs: audited.append(kwargs),
    )

    request_row = _exam_request()
    created = credit_exam_request_productivity(request_row, exam_id=77)

    assert created == [42]
    patient_id, descricao, especialidade, code, competence, name, validator_id, exam_request_id = captured['params']
    assert patient_id == 10
    assert especialidade == 'diagnostico_estomatologia_radiologia'
    assert code == '0204010179'  # Panorâmica
    assert validator_id == 5  # quem solicitou, não quem anexou
    assert exam_request_id == 1
    assert audited[0]['details']['credited_to'] == 5
    assert audited[0]['details']['exam_id'] == 77


def test_credit_lab_request_funcao_renal_creates_two_procedures(monkeypatch):
    inserted_codes = []

    def fake_query(sql, params=()):
        return []

    def fake_execute(sql, params=()):
        inserted_codes.append(params[3])
        return len(inserted_codes)

    monkeypatch.setattr(exam_productivity_service, 'query', fake_query)
    monkeypatch.setattr(exam_productivity_service, 'execute', fake_execute)
    monkeypatch.setattr(exam_productivity_service, 'get_sigtap_procedure', _fake_get_sigtap_procedure)
    monkeypatch.setattr(exam_productivity_service, 'audit_log', lambda **kwargs: None)

    request_row = _exam_request(
        tipo='clinico_laboratorial',
        tipo_imagem=None,
        categoria='funcao_renal',
    )
    created = credit_exam_request_productivity(request_row, exam_id=88)

    assert len(created) == 2
    assert set(inserted_codes) == {'0202010317', '0202010694'}


def test_credit_skips_unmapped_type_without_touching_database(monkeypatch):
    def fail_query(*args, **kwargs):
        raise AssertionError('não deveria consultar o banco')

    def fail_execute(*args, **kwargs):
        raise AssertionError('não deveria inserir no banco')

    monkeypatch.setattr(exam_productivity_service, 'query', fail_query)
    monkeypatch.setattr(exam_productivity_service, 'execute', fail_execute)

    request_row = _exam_request(tipo_imagem='Outro')
    assert credit_exam_request_productivity(request_row, exam_id=1) == []


def test_credit_is_idempotent_when_already_credited(monkeypatch):
    def fake_query(sql, params=()):
        return [{'id': 123}]

    def fail_execute(*args, **kwargs):
        raise AssertionError('não deveria inserir de novo')

    monkeypatch.setattr(exam_productivity_service, 'query', fake_query)
    monkeypatch.setattr(exam_productivity_service, 'execute', fail_execute)

    request_row = _exam_request()
    assert credit_exam_request_productivity(request_row, exam_id=77) == [123]
