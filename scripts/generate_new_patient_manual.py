#!/usr/bin/env python3
"""Gera capturas e o PDF institucional do Manual 03 — Novo paciente."""

import html
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import dotenv_values
from weasyprint import HTML


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAINING_BASE_URL = os.getenv('TRAINING_BASE_URL', 'http://127.0.0.1:5103').rstrip('/')
CAPTURES_DIR = PROJECT_ROOT / 'docs' / 'manuais_e_treinamentos' / 'capturas'
MANUALS_DIR = PROJECT_ROOT / 'docs' / 'manuais_e_treinamentos' / 'manuais_pdf'
LOGO_PATH = PROJECT_ROOT / 'static' / 'logo_sorriso_horizontal.png'
APPROVED_HTML = MANUALS_DIR / '01_primeiro_acesso_v1.0.html'
OUTPUT_PATH = MANUALS_DIR / '03_novo_paciente_v1.0.pdf'
HTML_SOURCE_PATH = MANUALS_DIR / '03_novo_paciente_v1.0.html'

SCREENSHOTS = {
    'search': CAPTURES_DIR / '03_novo_paciente_01_pesquisa_duplicidade.png',
    'identification': CAPTURES_DIR / '03_novo_paciente_02_identificacao.png',
    'address': CAPTURES_DIR / '03_novo_paciente_03_endereco_responsavel.png',
    'result': CAPTURES_DIR / '03_novo_paciente_04_resultado_sem_triagem.png',
}

BASE_SCREEN_CSS = """
<style>
@page { size: 1366px 768px; margin: 0; }
html, body {
    width: 1366px !important;
    height: 768px !important;
    min-width: 1366px !important;
    overflow: hidden !important;
}
body { background: #f8fafc !important; }
.animate-fade { animation: none !important; }
input[type="hidden"] { display: none !important; }
</style>
"""


def _csrf_token(markup):
    match = re.search(r'name="csrf_token" value="([^"]+)"', markup)
    if not match:
        raise RuntimeError('Token CSRF não encontrado.')
    return html.unescape(match.group(1))


def _inject_css(markup, extra_css=''):
    css = BASE_SCREEN_CSS.replace('</style>', f'{extra_css}</style>')
    return markup.replace('</head>', f'{css}</head>', 1)


def _set_input_value(markup, input_id, value):
    pattern = rf'(<input\b[^>]*\bid="{re.escape(input_id)}"[^>]*)(>)'

    def replace(match):
        opening = re.sub(r'\svalue="[^"]*"', '', match.group(1))
        return f'{opening} value="{html.escape(value, quote=True)}"{match.group(2)}'

    return re.sub(pattern, replace, markup, count=1)


def _select_option(markup, select_id, value):
    pattern = rf'(<select\b[^>]*\bid="{re.escape(select_id)}"[^>]*>)(.*?)(</select>)'

    def replace(match):
        options = re.sub(r'\sselected(?=[\s>])', '', match.group(2))
        options = re.sub(
            rf'(<option\b[^>]*\bvalue="{re.escape(value)}"[^>]*)(>)',
            r'\1 selected\2',
            options,
            count=1,
        )
        return f'{match.group(1)}{options}{match.group(3)}'

    return re.sub(pattern, replace, markup, count=1, flags=re.S)


def _check_radio(markup, name, value):
    pattern = rf'(<input\b[^>]*\bname="{re.escape(name)}"[^>]*\bvalue="{re.escape(value)}"[^>]*)(>)'
    return re.sub(pattern, r'\1 checked\2', markup, count=1)


def _set_text(markup, element_id, value):
    pattern = rf'(<[^>]+\bid="{re.escape(element_id)}"[^>]*>)(.*?)(</[^>]+>)'
    return re.sub(
        pattern,
        lambda match: f'{match.group(1)}{html.escape(value)}{match.group(3)}',
        markup,
        count=1,
        flags=re.S,
    )


def _render_screen(markup, output_path, extra_css=''):
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError('PyMuPDF é necessário para gerar as capturas.') from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_pdf = Path('/tmp') / f'{output_path.stem}.pdf'
    HTML(
        string=_inject_css(markup, extra_css),
        base_url=f'{TRAINING_BASE_URL}/',
    ).write_pdf(temporary_pdf)
    document = fitz.open(temporary_pdf)
    pixmap = document[0].get_pixmap(matrix=fitz.Matrix(1.35, 1.35), alpha=False)
    pixmap.save(output_path)
    document.close()
    temporary_pdf.unlink(missing_ok=True)


def _authenticated_reception_session():
    environment = dotenv_values(PROJECT_ROOT / '.env.training')
    password = environment.get('TRAINING_DEFAULT_PASSWORD')
    if not password:
        raise RuntimeError('TRAINING_DEFAULT_PASSWORD não está configurada.')

    session = requests.Session()
    login_page = session.get(f'{TRAINING_BASE_URL}/login', timeout=15)
    login_page.raise_for_status()
    response = session.post(
        f'{TRAINING_BASE_URL}/login',
        data={
            'csrf_token': _csrf_token(login_page.text),
            'username': 'treino.recepcao',
            'password': password,
        },
        timeout=15,
        allow_redirects=True,
    )
    response.raise_for_status()
    if response.url.rstrip('/').endswith('/login'):
        raise RuntimeError('Não foi possível autenticar a Recepção fictícia.')
    return session


def _prepared_patient_form(markup):
    values = {
        'cns': '790.0000.0000.0303',
        'nome': 'Helena Andrade Treinamento',
        'rg': 'TREINO-303',
        'cpf': '100.000.303-50',
        'profissao': 'Artesã',
        'cep_residencial': '57020-000',
        'endereco_bairro': 'Centro',
        'endereco_logradouro': 'Rua do Comércio',
        'endereco_numero': '303',
        'endereco_residencial': 'Rua do Comércio, 303, Centro, Maceió - AL, CEP 57020-000',
        'endereco_ibge_codigo': '2704302',
        'email': 'helena.treinamento@example.com',
        'data_nascimento': '1987-03-18',
        'nacionalidade': 'Brasileira',
        'celular': '(82) 99999-0303',
        'estado_civil': 'Casada',
        'atendido_em': 'Unidade de Treinamento',
        'nome_responsavel': 'Carlos Andrade Treinamento',
        'rg_responsavel': 'RESP-303',
        'email_responsavel': 'responsavel.treinamento@example.com',
    }
    for input_id, value in values.items():
        markup = _set_input_value(markup, input_id, value)
    markup = _select_option(markup, 'endereco_estado', 'AL')
    markup = _select_option(markup, 'endereco_cidade', 'Maceió')
    markup = _check_radio(markup, 'genero', 'Fem')
    markup = _set_text(markup, 'cep_status', 'CEP encontrado.')
    markup = _set_text(
        markup,
        'endereco_preview',
        'Endereço: Rua do Comércio, 303, Centro, Maceió - AL, CEP 57020-000',
    )
    return markup


def _inject_patient_result(markup):
    row = """
    <tr style="border-bottom:1px solid #dbe5f0;background:#eff6ff;">
      <td style="padding:1.25rem;font-weight:700;">
        <span style="color:#0d47a1;border-bottom:2px solid #0d47a1;">Helena Andrade Treinamento</span>
      </td>
      <td style="padding:1.25rem;color:#64748b;">100.000.303-50</td>
      <td style="padding:1.25rem;"><span style="color:#64748b;font-weight:700;">Sem triagem</span></td>
      <td style="padding:1.25rem;text-align:right;">
        <span class="btn btn-outline" style="padding:.4rem .8rem;font-size:.8rem;background:white;">Abrir prontuário</span>
        <span class="btn btn-outline" style="padding:.4rem .8rem;font-size:.8rem;background:white;">Editar ✏️</span>
      </td>
    </tr>
    """
    return markup.replace('<tbody>', f'<tbody>{row}', 1)


def capture_training_screens():
    requests.get(f'{TRAINING_BASE_URL}/health', timeout=10).raise_for_status()
    session = _authenticated_reception_session()

    search_response = session.get(
        f'{TRAINING_BASE_URL}/patients/list',
        params={'q': 'Helena Andrade Treinamento'},
        timeout=15,
    )
    search_response.raise_for_status()
    search_css = """
    .content-area { padding:1.25rem 1.5rem !important; }
    .content-area .animate-fade > div:first-child { display:none !important; }
    .content-area .animate-fade > div:nth-child(2) { margin-bottom:1rem !important; }
    .content-area .card { margin-bottom:1rem !important; }
    """
    _render_screen(search_response.text, SCREENSHOTS['search'], search_css)

    form_response = session.get(f'{TRAINING_BASE_URL}/patients/register', timeout=15)
    form_response.raise_for_status()
    prepared_form = _prepared_patient_form(form_response.text)

    identification_css = """
    .content-area { padding:0 !important; }
    .document-container { border-radius:0 !important; padding:1rem 2rem !important; box-shadow:none !important; }
    .document-container > div:first-child { display:none !important; }
    .document-header { margin-bottom:1rem !important; }
    .document-header h1 { font-size:1.65rem !important; }
    .document-header h2 { font-size:.85rem !important; }
    .form-grid { gap:1.25rem !important; }
    .form-group-inline { margin-bottom:.65rem !important; }
    .form-section-title { margin-top:.75rem !important; margin-bottom:.65rem !important; }
    [data-address-widget], .form-actions { display:none !important; }
    """
    _render_screen(prepared_form, SCREENSHOTS['identification'], identification_css)

    address_css = """
    .content-area { padding:0 !important; }
    .document-container { border-radius:0 !important; padding:1rem 2rem !important; box-shadow:none !important; }
    .document-container > div:first-child, .document-header { display:none !important; }
    .document-container form { margin-top:-245px !important; }
    .form-grid { gap:1.25rem !important; }
    .form-group-inline { margin-bottom:.65rem !important; }
    .form-section-title { margin-top:.75rem !important; margin-bottom:.65rem !important; }
    .form-actions { display:none !important; }
    """
    _render_screen(prepared_form, SCREENSHOTS['address'], address_css)

    list_response = session.get(f'{TRAINING_BASE_URL}/patients/list', timeout=15)
    list_response.raise_for_status()
    result_css = """
    .content-area { padding:1.25rem 1.5rem !important; }
    .content-area .animate-fade > div:first-child { display:none !important; }
    .content-area .animate-fade > div:nth-child(2) { margin-bottom:1rem !important; }
    .content-area .card { margin-bottom:1rem !important; }
    table th, table td { padding:.75rem !important; }
    """
    _render_screen(
        _inject_patient_result(list_response.text),
        SCREENSHOTS['result'],
        result_css,
    )


def image_uri(path):
    return path.resolve().as_uri()


def _approved_css():
    source = APPROVED_HTML.read_text(encoding='utf-8')
    match = re.search(r'<style>(.*?)</style>', source, re.S)
    if not match:
        raise RuntimeError('CSS do modelo aprovado não encontrado.')
    return match.group(1).replace('Manual 01', 'Manual 03')


def build_manual_html():
    logo = image_uri(LOGO_PATH)
    search = image_uri(SCREENSHOTS['search'])
    identification = image_uri(SCREENSHOTS['identification'])
    address = image_uri(SCREENSHOTS['address'])
    result = image_uri(SCREENSHOTS['result'])
    css = _approved_css()

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>Manual 03 — Novo paciente</title>
  <style>{css}</style>
</head>
<body>
  <section class="cover">
    <div class="cover-logo"><img src="{logo}" alt="Sorriso da Gente"></div>
    <div class="cover-kicker">Manual de operação • 03</div>
    <h1>Novo paciente</h1>
    <div class="cover-subtitle">Crie um prontuário único, identifique corretamente o paciente e prepare o cadastro para triagem e atendimento.</div>
    <div class="cover-meta">
      <div><strong>Público</strong>Recepção e Clínicos autorizados</div>
      <div><strong>Versão</strong>4.0.0-rc.1</div>
      <div><strong>Revisão</strong>22 de junho de 2026</div>
    </div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 03 • Novo paciente</div></header>
    <h2>Antes de começar</h2>
    <p class="lead">Um cadastro duplicado fragmenta o histórico clínico. Pesquise primeiro e confirme os identificadores antes de criar o prontuário.</p>
    <div class="flow">
      <div class="flow-step"><div class="flow-number">1</div><strong>Pesquisar</strong><span>Evite duplicidade.</span></div>
      <div class="flow-step"><div class="flow-number">2</div><strong>Identificar</strong><span>Informe CPF e CNS.</span></div>
      <div class="flow-step"><div class="flow-number">3</div><strong>Localizar</strong><span>Estruture o endereço.</span></div>
      <div class="flow-step"><div class="flow-number">4</div><strong>Conferir</strong><span>Revise o prontuário.</span></div>
    </div>
    <div class="check-grid">
      <div class="check-card"><strong>Pesquisa concluída</strong><span>Busque por nome, CPF e CNS antes de cadastrar.</span></div>
      <div class="check-card"><strong>Documentos conferidos</strong><span>CPF e CNS são obrigatórios.</span></div>
      <div class="check-card"><strong>CEP e número</strong><span>Revise o endereço sugerido pelo sistema.</span></div>
      <div class="check-card"><strong>Responsável legal</strong><span>Registre-o quando o paciente depender de responsável.</span></div>
    </div>
    <div class="warning"><strong>Cadastro não é Triagem</strong>O paciente será criado sem senha. A demanda e a senha serão vinculadas posteriormente dentro da ação de Triagem.</div>
    <table class="mini-table">
      <tr><th>Dado</th><th>Por que conferir</th></tr>
      <tr><td>CNS</td><td>Identifica o paciente no Sistema Único de Saúde.</td></tr>
      <tr><td>CPF</td><td>Reduz duplicidades e apoia integrações e documentos.</td></tr>
      <tr><td>Nascimento</td><td>Ajuda a confirmar identidade e faixa etária.</td></tr>
      <tr><td>Endereço estruturado</td><td>Alimenta epidemiologia, BI, relatórios e organização territorial.</td></tr>
    </table>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 03 • Pesquisa</div></header>
    <div class="step-banner"><div class="step-badge">1</div><div class="step-title"><h2>Pesquisar antes de cadastrar</h2><p>Confirme que o paciente ainda não possui prontuário.</p></div></div>
    <div class="screen">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Pesquisa com nome fictício</div>
      <img src="{search}" alt="Pesquisa de paciente sem resultado">
    </div>
    <div class="columns">
      <div>
        <div class="instruction"><strong>Pesquise de mais de uma forma</strong><p>Comece pelo nome e confirme também CPF ou CNS quando disponíveis.</p></div>
        <div class="instruction"><strong>Abra Novo Cadastro</strong><p>Prossiga somente quando a busca não localizar a mesma pessoa.</p></div>
      </div>
      <div class="warning"><strong>Encontrou cadastro semelhante?</strong>Abra e confira nascimento e documentos. Não crie outro prontuário por dúvida.</div>
    </div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 03 • Identificação</div></header>
    <div class="step-banner"><div class="step-badge">2</div><div class="step-title"><h2>Preencher a identificação</h2><p>Os dados exibidos são integralmente fictícios.</p></div></div>
    <div class="screen">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Cadastro de paciente • identificação</div>
      <img src="{identification}" alt="Identificação do paciente">
    </div>
    <div class="password-rules">
      <div class="rule"><b>CNS</b><span>obrigatório para identificação SUS</span></div>
      <div class="rule"><b>CPF</b><span>obrigatório e validado pelo sistema</span></div>
      <div class="rule"><b>Contato</b><span>celular e e-mail devem ser atuais</span></div>
    </div>
    <div class="tip"><strong>Revise antes de continuar</strong>Confira grafia do nome, nascimento, gênero e documentos diretamente com o paciente ou responsável.</div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 03 • Endereço e responsável</div></header>
    <div class="step-banner"><div class="step-badge">3</div><div class="step-title"><h2>Estruturar endereço e responsável</h2><p>Comece pelo CEP e revise o preenchimento automático.</p></div></div>
    <div class="screen">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> CEP público de demonstração • demais dados fictícios</div>
      <img src="{address}" alt="Endereço e responsável legal">
    </div>
    <div class="columns">
      <div>
        <div class="instruction"><strong>CEP localizado</strong><p>Confira rua, bairro, cidade e estado; depois informe o número.</p></div>
        <div class="instruction"><strong>Preenchimento manual</strong><p>Se o CEP falhar, selecione estado e cidade e complete os demais campos.</p></div>
      </div>
      <div class="warning"><strong>Responsável legal</strong>Preencha nome, documento e contato para menores ou pacientes que dependam de responsável.</div>
    </div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 03 • Conferência</div></header>
    <div class="step-banner"><div class="step-badge">4</div><div class="step-title"><h2>Salvar e conferir o prontuário</h2><p>Clique em Efetuar cadastro e confira o registro criado.</p></div></div>
    <div class="screen screen-compact">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Resultado ilustrativo • paciente não gravado</div>
      <img src="{result}" alt="Paciente cadastrado sem triagem">
    </div>
    <div class="columns">
      <div class="success"><strong>Resultado esperado</strong>Paciente único, identificado e disponível para prontuário, triagem e agenda.</div>
      <div class="warning"><strong>Sem triagem é correto</strong>O cadastro não recebe senha automaticamente. A senha será vinculada no Manual 04 — Triagem.</div>
    </div>
    <table class="mini-table">
      <tr><th>Se acontecer</th><th>O que fazer</th></tr>
      <tr><td>Paciente já cadastrado</td><td>Utilize e atualize o prontuário existente.</td></tr>
      <tr><td>CPF inválido</td><td>Confira os onze dígitos com o paciente.</td></tr>
      <tr><td>CEP não localizado</td><td>Faça o preenchimento manual do endereço.</td></tr>
      <tr><td>Paciente precisa de senha</td><td>Abra a ação correspondente na Triagem.</td></tr>
    </table>
    <div class="closing"><h3>Prontuário preparado</h3><p>O próximo passo operacional é vincular a demanda e a senha dentro da ação de <b>Triagem</b>.</p></div>
  </section>
</body>
</html>"""


def main():
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    MANUALS_DIR.mkdir(parents=True, exist_ok=True)
    if '--reuse-captures' not in sys.argv:
        capture_training_screens()
    elif not all(path.exists() for path in SCREENSHOTS.values()):
        raise RuntimeError('As capturas ainda não existem; gere sem --reuse-captures.')
    document = build_manual_html()
    HTML_SOURCE_PATH.write_text(document, encoding='utf-8')
    HTML(string=document, base_url=str(PROJECT_ROOT)).write_pdf(OUTPUT_PATH)
    print(OUTPUT_PATH.relative_to(PROJECT_ROOT))
    for screenshot in SCREENSHOTS.values():
        print(screenshot.relative_to(PROJECT_ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
