from flask import Flask
import sys
import types


class FakeCache:
    def init_app(self, *args, **kwargs):
        return None

    def cached(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


class FakeLimiter:
    def init_app(self, *args, **kwargs):
        return None


extensions_stub = types.ModuleType('extensions')
extensions_stub.cache = FakeCache()
extensions_stub.limiter = FakeLimiter()
sys.modules.setdefault('extensions', extensions_stub)

import blueprints.patients as patients


def _app():
    app = Flask(__name__)
    app.config['LOGIN_DISABLED'] = True
    app.secret_key = 'test'
    app.register_blueprint(patients.patients_bp)
    return app


def test_compose_residential_address_prefers_structured_fields():
    address = patients._compose_residential_address(
        {
            'cep_residencial': '57000000',
            'endereco_logradouro': 'Rua das Flores',
            'endereco_numero': '123',
            'endereco_bairro': 'Centro',
            'endereco_cidade': 'Maceió',
            'endereco_estado': 'al',
        }
    )

    assert address == 'Rua das Flores, 123, Centro, Maceió - AL, CEP 57000-000'


def test_address_cep_returns_normalized_viacep_payload(monkeypatch):
    app = _app()

    monkeypatch.setattr(
        patients,
        '_fetch_json_url',
        lambda *args, **kwargs: {
            'cep': '57000-000',
            'logradouro': 'Rua das Flores',
            'bairro': 'Centro',
            'localidade': 'Maceió',
            'uf': 'AL',
            'ibge': '2704302',
        },
    )

    with app.test_request_context('/patients/address/cep/57000000'):
        response = patients.address_cep('57000000')

    assert response.status_code == 200
    assert response.get_json() == {
        'cep': '57000-000',
        'logradouro': 'Rua das Flores',
        'bairro': 'Centro',
        'cidade': 'Maceió',
        'estado': 'AL',
        'ibge_codigo': '2704302',
    }


def test_address_cities_for_alagoas_use_local_municipios(monkeypatch):
    app = _app()

    monkeypatch.setattr(
        patients,
        'query',
        lambda *args, **kwargs: [{'nome': 'Arapiraca'}, {'nome': 'Maceió'}],
    )

    with app.test_request_context('/patients/address/cities?uf=AL'):
        response = patients.address_cities()

    assert response.status_code == 200
    assert response.get_json() == [
        {'nome': 'Arapiraca', 'ibge_codigo': ''},
        {'nome': 'Maceió', 'ibge_codigo': ''},
    ]
