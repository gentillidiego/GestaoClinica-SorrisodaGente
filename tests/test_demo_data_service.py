import services.demo_data_service as demo_data_service
from services.demo_data_service import clamp_demo_count, create_demo_patients, generate_valid_cpf


def _cpf_is_valid(value):
    digits = [int(char) for char in value if char.isdigit()]
    if len(digits) != 11:
        return False

    first_sum = sum(digit * weight for digit, weight in zip(digits[:9], range(10, 1, -1)))
    first_digit = 11 - (first_sum % 11)
    first_digit = 0 if first_digit >= 10 else first_digit

    second_sum = sum(digit * weight for digit, weight in zip(digits[:10], range(11, 1, -1)))
    second_digit = 11 - (second_sum % 11)
    second_digit = 0 if second_digit >= 10 else second_digit

    return digits[9] == first_digit and digits[10] == second_digit


def test_generate_valid_cpf_uses_standard_format_and_check_digits():
    cpf = generate_valid_cpf(42)

    assert len(cpf) == 14
    assert cpf[3] == '.'
    assert cpf[7] == '.'
    assert cpf[11] == '-'
    assert _cpf_is_valid(cpf)


def test_clamp_demo_count_limits_batch_size():
    assert clamp_demo_count(None) == 1
    assert clamp_demo_count('abc') == 1
    assert clamp_demo_count(0) == 1
    assert clamp_demo_count(15) == 15
    assert clamp_demo_count(150) == 100


def test_get_next_demo_index_counts_existing_demo_patients(monkeypatch):
    monkeypatch.setattr(
        demo_data_service,
        'query',
        lambda *args, **kwargs: {'total': 12},
    )

    assert demo_data_service.get_next_demo_index() == 13


def test_demo_municipality_selection_uses_curated_real_territories(monkeypatch):
    rows = [
        {'id': 1, 'nome': 'Maceió', 'codigo': '2704302'},
        {'id': 2, 'nome': 'Arapiraca', 'codigo': '2700300'},
        {'id': 3, 'nome': 'Município Fora da Carga', 'codigo': '9999999'},
    ]

    monkeypatch.setattr(demo_data_service, 'query', lambda *args, **kwargs: rows)

    municipality = demo_data_service._select_municipality(0)
    neighborhood = demo_data_service._select_neighborhood(municipality['nome'], 0)

    assert municipality['nome'] == 'Maceió'
    assert neighborhood in demo_data_service.DEMO_TERRITORIES['Maceió']


def test_create_demo_patients_registers_run_and_creates_sequential_patients(monkeypatch):
    created_indexes = []
    updates = []

    def fake_execute(sql, params=()):
        if 'INSERT INTO demo_seed_runs' in sql:
            assert params[0] == 'Carga teste'
            assert params[1] == 3
            return 77
        if 'UPDATE demo_seed_runs' in sql:
            updates.append((sql, params))
        return None

    def fake_create_demo_patient(index, run_id, created_by=None):
        created_indexes.append(index)
        return {
            'patient_id': 1000 + index,
            'name': f'Paciente {index}',
            'profile': 'Perfil demo',
            'municipality': 'Maceio',
        }

    monkeypatch.setattr(demo_data_service, 'execute', fake_execute)
    monkeypatch.setattr(demo_data_service, 'get_next_demo_index', lambda: 20)
    monkeypatch.setattr(demo_data_service, 'create_demo_patient', fake_create_demo_patient)

    result = create_demo_patients(count=3, created_by=9, label='Carga teste')

    assert result['run_id'] == 77
    assert result['created_count'] == 3
    assert created_indexes == [20, 21, 22]
    assert updates
    assert updates[0][1][0] == 3
