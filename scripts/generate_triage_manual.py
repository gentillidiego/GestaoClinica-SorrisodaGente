#!/usr/bin/env python3
"""Gera capturas e o PDF institucional do Manual 04 — Triagem."""

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
OUTPUT_PATH = MANUALS_DIR / '04_triagem_v1.0.pdf'
HTML_SOURCE_PATH = MANUALS_DIR / '04_triagem_v1.0.html'

SCREENSHOTS = {
    'action': CAPTURES_DIR / '04_triagem_01_nova_acao.png',
    'link': CAPTURES_DIR / '04_triagem_02_localizar_vincular.png',
    'generated': CAPTURES_DIR / '04_triagem_03_senha_gerada.png',
    'tickets': CAPTURES_DIR / '04_triagem_04_consultar_senhas.png',
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


def _set_input_by_name(markup, name, value):
    pattern = rf'(<input\b[^>]*\bname="{re.escape(name)}"[^>]*)(>)'

    def replace(match):
        opening = re.sub(r'\svalue="[^"]*"', '', match.group(1))
        return f'{opening} value="{html.escape(value, quote=True)}"{match.group(2)}'

    return re.sub(pattern, replace, markup, count=1)


def _set_textarea(markup, name, value):
    pattern = rf'(<textarea\b[^>]*\bname="{re.escape(name)}"[^>]*>)(.*?)(</textarea>)'
    return re.sub(
        pattern,
        lambda match: f'{match.group(1)}{html.escape(value)}{match.group(3)}',
        markup,
        count=1,
        flags=re.S,
    )


def _select_option(markup, select_name, *, value=None, contains=None):
    pattern = rf'(<select\b[^>]*\bname="{re.escape(select_name)}"[^>]*>)(.*?)(</select>)'

    def replace(match):
        options = re.sub(r'\sselected(?=[\s>])', '', match.group(2))
        if value is not None:
            option_pattern = rf'(<option\b[^>]*\bvalue="{re.escape(str(value))}"[^>]*)(>)'
        else:
            option_pattern = rf'(<option\b(?=[^>]*>[^<]*{re.escape(contains)}).*?)(>)'
        options = re.sub(option_pattern, r'\1 selected\2', options, count=1, flags=re.I)
        return f'{match.group(1)}{options}{match.group(3)}'

    return re.sub(pattern, replace, markup, count=1, flags=re.S)


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


def _prepare_action_form(markup):
    markup = _select_option(markup, 'municipio_id', contains='Maceió')
    markup = _set_input_by_name(markup, 'data_acao', '2026-06-22')
    markup = _set_input_by_name(markup, 'local', 'UBS Treinamento — Ação Manual 04')
    return _set_textarea(
        markup,
        'observacoes',
        'Equipe de acolhimento e logística fictícias para treinamento.',
    )


def _prepare_link_form(markup):
    markup = _set_input_by_name(markup, 'paciente', 'Paciente Triagem Treinamento')
    markup = _select_option(markup, 'patient_id', value='1')
    return _select_option(markup, 'especialidade_id', contains='Endodontia')


def _inject_generated_modal(markup):
    modal = """
    <div style="position:fixed;inset:0;background:rgba(15,23,42,.64);z-index:3000;display:flex;align-items:center;justify-content:center;padding:2rem;">
      <div class="card" style="width:min(760px,100%);text-align:center;padding:3rem;background:#FFC124;color:#111827;border:4px solid #111827;box-shadow:0 28px 90px rgba(15,23,42,.45);">
        <div style="font-size:.82rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.9rem;">Senha gerada</div>
        <div style="font-family:var(--font-heading);font-size:4.6rem;font-weight:900;line-height:1;margin-bottom:1.25rem;">MCZ-END-002</div>
        <p style="font-size:1rem;font-weight:700;margin-bottom:2rem;">Vinculada a Paciente Triagem Treinamento. Ela já está salva na ação e no prontuário.</p>
        <div style="display:flex;justify-content:center;gap:.75rem;"><span class="btn btn-outline" style="background:white;border-color:#111827;color:#111827;">Copiar</span><span class="btn btn-primary" style="background:#111827;">Entendi</span></div>
      </div>
    </div>
    """
    return markup.replace('</body>', f'{modal}</body>', 1)


def capture_training_screens():
    requests.get(f'{TRAINING_BASE_URL}/health', timeout=10).raise_for_status()
    session = _authenticated_reception_session()

    action_response = session.get(f'{TRAINING_BASE_URL}/triagem/acoes/nova', timeout=15)
    action_response.raise_for_status()
    action_css = """
    .content-area { padding:1.5rem 2rem !important; }
    .content-area > .animate-fade > div:first-child { display:none !important; }
    .content-area .card { margin:1rem auto !important; padding:2rem !important; }
    """
    _render_screen(
        _prepare_action_form(action_response.text),
        SCREENSHOTS['action'],
        action_css,
    )

    detail_response = session.get(
        f'{TRAINING_BASE_URL}/triagem/acoes/1',
        params={'paciente': 'Paciente Triagem Treinamento'},
        timeout=15,
    )
    detail_response.raise_for_status()
    prepared_detail = _prepare_link_form(detail_response.text)
    detail_css = """
    .content-area { padding:1rem 1.5rem !important; }
    .content-area > .animate-fade > div:first-child { display:none !important; }
    .content-area .card { margin-bottom:1rem !important; padding:1rem 1.25rem !important; }
    .content-area > .animate-fade > .card:nth-child(n+4) { display:none !important; }
    """
    _render_screen(prepared_detail, SCREENSHOTS['link'], detail_css)
    _render_screen(
        _inject_generated_modal(prepared_detail),
        SCREENSHOTS['generated'],
        detail_css,
    )

    tickets_response = session.get(
        f'{TRAINING_BASE_URL}/triagem/senhas',
        params={'q': 'MCZ', 'status': 'Vinculada'},
        timeout=15,
    )
    tickets_response.raise_for_status()
    tickets_css = """
    .content-area { padding:1rem 1.5rem !important; }
    .content-area .animate-fade > div:first-child { margin-bottom:1rem !important; }
    .content-area .card { margin-bottom:1rem !important; padding:1rem !important; }
    table th, table td { padding:.7rem !important; }
    """
    _render_screen(tickets_response.text, SCREENSHOTS['tickets'], tickets_css)


def image_uri(path):
    return path.resolve().as_uri()


def _approved_css():
    source = APPROVED_HTML.read_text(encoding='utf-8')
    match = re.search(r'<style>(.*?)</style>', source, re.S)
    if not match:
        raise RuntimeError('CSS do modelo aprovado não encontrado.')
    return match.group(1).replace('Manual 01', 'Manual 04')


def build_manual_html():
    logo = image_uri(LOGO_PATH)
    action = image_uri(SCREENSHOTS['action'])
    link = image_uri(SCREENSHOTS['link'])
    generated = image_uri(SCREENSHOTS['generated'])
    tickets = image_uri(SCREENSHOTS['tickets'])
    css = _approved_css()

    return f"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>Manual 04 — Triagem</title><style>{css}</style></head>
<body>
  <section class="cover">
    <div class="cover-logo"><img src="{logo}" alt="Sorriso da Gente"></div>
    <div class="cover-kicker">Manual de operação • 04</div>
    <h1>Triagem</h1>
    <div class="cover-subtitle">Registre a origem da demanda, vincule paciente e especialidade e prepare a fila para o agendamento.</div>
    <div class="cover-meta"><div><strong>Público</strong>Recepção</div><div><strong>Versão</strong>4.0.0-rc.1</div><div><strong>Revisão</strong>22 de junho de 2026</div></div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 04 • Triagem</div></header>
    <h2>Antes de começar</h2>
    <p class="lead">A Triagem registra a demanda identificada no município. O paciente deve estar cadastrado e a unidade de atendimento será escolhida somente na Agenda.</p>
    <div class="flow">
      <div class="flow-step"><div class="flow-number">1</div><strong>Criar ação</strong><span>Registre origem e data.</span></div>
      <div class="flow-step"><div class="flow-number">2</div><strong>Localizar</strong><span>Selecione o paciente.</span></div>
      <div class="flow-step"><div class="flow-number">3</div><strong>Vincular</strong><span>Escolha a especialidade.</span></div>
      <div class="flow-step"><div class="flow-number">4</div><strong>Consultar</strong><span>Acompanhe as senhas.</span></div>
    </div>
    <div class="check-grid">
      <div class="check-card"><strong>Paciente cadastrado</strong><span>A Triagem não cria prontuário.</span></div>
      <div class="check-card"><strong>Município confirmado</strong><span>A ação registra a origem da demanda.</span></div>
      <div class="check-card"><strong>Especialidade correta</strong><span>Cada demanda recebe sua própria senha.</span></div>
      <div class="check-card"><strong>Unidade ainda não definida</strong><span>Essa escolha pertence à Agenda.</span></div>
    </div>
    <div class="warning"><strong>Ordem operacional</strong>Cadastro do paciente → Triagem e senha → Agenda e unidade → Atendimento.</div>
    <table class="mini-table">
      <tr><th>Elemento</th><th>Responsabilidade</th></tr>
      <tr><td>Ação de Triagem</td><td>Registra município, data e local do acolhimento.</td></tr>
      <tr><td>Senha</td><td>Relaciona paciente e especialidade da demanda.</td></tr>
      <tr><td>Múltiplas demandas</td><td>Geram senhas distintas para o mesmo paciente.</td></tr>
      <tr><td>Unidade de execução</td><td>É escolhida posteriormente, durante o agendamento.</td></tr>
    </table>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 04 • Nova ação</div></header>
    <div class="step-banner"><div class="step-badge">1</div><div class="step-title"><h2>Criar a ação municipal</h2><p>Abra Triagem, clique em Nova Ação e registre a origem.</p></div></div>
    <div class="screen">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Exemplo integralmente fictício</div>
      <img src="{action}" alt="Nova ação de triagem">
    </div>
    <div class="columns">
      <div>
        <div class="instruction"><strong>Município e data</strong><p>São obrigatórios e identificam quando e onde a demanda foi registrada.</p></div>
        <div class="instruction"><strong>Local e observações</strong><p>Informe UBS, espaço da ação e detalhes úteis à logística.</p></div>
      </div>
      <div class="tip"><strong>Uma ação, várias senhas</strong>Depois de salvar a ação, gere as senhas correspondentes aos pacientes acolhidos.</div>
    </div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 04 • Paciente e especialidade</div></header>
    <div class="step-banner"><div class="step-badge">2</div><div class="step-title"><h2>Localizar e preparar o vínculo</h2><p>Pesquise o cadastro correto e escolha a demanda identificada.</p></div></div>
    <div class="screen">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Paciente e especialidade fictícios</div>
      <img src="{link}" alt="Localização e vínculo da senha">
    </div>
    <div class="columns">
      <div>
        <div class="instruction"><strong>Pesquise o paciente</strong><p>Use nome, CPF ou CNS e confirme o resultado antes de selecionar.</p></div>
        <div class="instruction"><strong>Escolha a especialidade</strong><p>A senha representa uma demanda específica, como Endodontia ou Prótese.</p></div>
      </div>
      <div class="warning"><strong>Paciente não encontrado?</strong>Interrompa o fluxo e faça o cadastro antes da Triagem.</div>
    </div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 04 • Senha vinculada</div></header>
    <div class="step-banner"><div class="step-badge">3</div><div class="step-title"><h2>Gerar e vincular a senha</h2><p>O código é criado automaticamente pelo sistema.</p></div></div>
    <div class="screen">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Resultado ilustrativo • senha não gravada</div>
      <img src="{generated}" alt="Confirmação de senha gerada">
    </div>
    <div class="password-rules">
      <div class="rule"><b>MCZ</b><span>código do município de origem</span></div>
      <div class="rule"><b>END</b><span>código da especialidade</span></div>
      <div class="rule"><b>002</b><span>sequencial gerado pelo sistema</span></div>
    </div>
    <div class="columns">
      <div class="success"><strong>Vínculo imediato</strong>A senha passa a aparecer na ação e no prontuário do paciente.</div>
      <div class="tip"><strong>Mais de uma demanda?</strong>Repita o processo para cada especialidade. O paciente pode possuir várias senhas.</div>
    </div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 04 • Consulta</div></header>
    <div class="step-banner"><div class="step-badge">4</div><div class="step-title"><h2>Consultar e acompanhar as senhas</h2><p>Use os filtros para localizar demandas e acompanhar o destino.</p></div></div>
    <div class="screen screen-compact">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Senhas vinculadas no ambiente de treinamento</div>
      <img src="{tickets}" alt="Consulta de senhas">
    </div>
    <div class="columns">
      <div class="success"><strong>Resultado esperado</strong>Senha vinculada ao paciente e pronta para organização da fila e agendamento.</div>
      <div class="warning"><strong>Status protegido</strong>Senhas vinculadas ao paciente não podem ter status alterado manualmente.</div>
    </div>
    <table class="mini-table">
      <tr><th>Se acontecer</th><th>O que fazer</th></tr>
      <tr><td>Paciente não aparece</td><td>Confirme o cadastro e repita a pesquisa por CPF ou CNS.</td></tr>
      <tr><td>Demanda adicional</td><td>Gere outra senha para a nova especialidade.</td></tr>
      <tr><td>Status sem ação disponível</td><td>A senha já está vinculada e protegida.</td></tr>
      <tr><td>Unidade ainda vazia</td><td>Defina-a posteriormente no agendamento.</td></tr>
    </table>
    <div class="closing"><h3>Demanda preparada</h3><p>O próximo passo é organizar data, profissional e <b>unidade de atendimento</b> no Manual 05 — Agenda.</p></div>
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
