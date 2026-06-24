#!/usr/bin/env python3
"""Gera capturas e o PDF institucional do Manual 05 — Agenda."""

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
OUTPUT_PATH = MANUALS_DIR / '05_agenda_v1.0.pdf'
HTML_SOURCE_PATH = MANUALS_DIR / '05_agenda_v1.0.html'

SCREENSHOTS = {
    'overview': CAPTURES_DIR / '05_agenda_01_visao_semanal_filtros.png',
    'new': CAPTURES_DIR / '05_agenda_02_nova_consulta.png',
    'edit': CAPTURES_DIR / '05_agenda_03_editar_status_unidade.png',
    'clinical': CAPTURES_DIR / '05_agenda_04_escopo_clinico.png',
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


def _select_option_last(markup, select_name, *, value=None, contains=None):
    pattern = re.compile(
        rf'(<select\b[^>]*\bname="{re.escape(select_name)}"[^>]*>)(.*?)(</select>)',
        re.S,
    )
    matches = list(pattern.finditer(markup))
    if not matches:
        return markup
    match = matches[-1]
    options = re.sub(r'\sselected(?=[\s>])', '', match.group(2))
    if value is not None:
        option_pattern = rf'(<option\b[^>]*\bvalue="{re.escape(str(value))}"[^>]*)(>)'
    else:
        option_pattern = rf'(<option\b(?=[^>]*>[^<]*{re.escape(contains)}).*?)(>)'
    options = re.sub(option_pattern, r'\1 selected\2', options, count=1, flags=re.I)
    replacement = f'{match.group(1)}{options}{match.group(3)}'
    return f'{markup[:match.start()]}{replacement}{markup[match.end():]}'


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


def _authenticated_session(username, source_ip):
    environment = dotenv_values(PROJECT_ROOT / '.env.training')
    password = environment.get('TRAINING_DEFAULT_PASSWORD')
    if not password:
        raise RuntimeError('TRAINING_DEFAULT_PASSWORD não está configurada.')

    session = requests.Session()
    session.headers.update({'X-Forwarded-For': source_ip})
    login_page = session.get(f'{TRAINING_BASE_URL}/login', timeout=15)
    login_page.raise_for_status()
    response = session.post(
        f'{TRAINING_BASE_URL}/login',
        data={
            'csrf_token': _csrf_token(login_page.text),
            'username': username,
            'password': password,
        },
        timeout=15,
        allow_redirects=True,
    )
    response.raise_for_status()
    if response.url.rstrip('/').endswith('/login'):
        raise RuntimeError(f'Não foi possível autenticar {username}.')
    return session


def _prepare_new_consultation(markup):
    markup = markup.replace(
        'id="modal-nova-consulta" class="agenda-modal-overlay" style="display:none;"',
        'id="modal-nova-consulta" class="agenda-modal-overlay" style="display:flex;"',
        1,
    )
    markup = _select_option(markup, 'patient_id', contains='Paciente Agenda Treinamento')
    markup = _select_option_last(markup, 'dentista_id', contains='Dra. Clínica Treinamento')
    markup = _set_input_by_name(markup, 'data_consulta', '2026-06-24T09:00')
    markup = _select_option(markup, 'duracao_minutos', value='60')
    markup = _select_option_last(markup, 'execution_unit', value='unidade_apoio')
    return _set_textarea(
        markup,
        'observacoes',
        'Avaliação inicial da demanda de Prótese — exemplo fictício.',
    )


def capture_training_screens():
    requests.get(f'{TRAINING_BASE_URL}/health', timeout=10).raise_for_status()

    reception = _authenticated_session('treino.recepcao', '198.51.100.51')
    agenda_response = reception.get(
        f'{TRAINING_BASE_URL}/agenda/',
        params={'semana': '2026-06-22'},
        timeout=15,
    )
    agenda_response.raise_for_status()
    overview_css = """
    .content-area { padding:1rem 1.25rem !important; }
    .content-area .animate-fade > div:first-child { margin-bottom:1rem !important; }
    .content-area .card { margin-bottom:1rem !important; }
    .agenda-grid-card { max-height:360px !important; }
    .content-area .animate-fade > .card:last-child { display:none !important; }
    """
    _render_screen(agenda_response.text, SCREENSHOTS['overview'], overview_css)

    modal_css = """
    .agenda-modal-overlay { position:fixed !important; inset:0 !important; z-index:4000 !important; }
    .agenda-modal { max-height:740px !important; overflow:hidden !important; }
    .agenda-modal-body { padding:1.25rem 2rem !important; }
    .agenda-modal-body .form-group { margin-bottom:.75rem !important; }
    """
    _render_screen(
        _prepare_new_consultation(agenda_response.text),
        SCREENSHOTS['new'],
        modal_css,
    )

    edit_response = reception.get(f'{TRAINING_BASE_URL}/agenda/18/editar', timeout=15)
    edit_response.raise_for_status()
    edit_markup = _select_option(edit_response.text, 'execution_unit', value='unidade_apoio')
    edit_markup = _select_option(edit_markup, 'status', value='Confirmado')
    edit_css = """
    .content-area { padding:1rem 1.5rem !important; }
    .content-area > .animate-fade > div:first-child { margin-bottom:.75rem !important; }
    .content-area .card { padding:1.25rem 1.75rem !important; margin-bottom:0 !important; }
    .content-area .form-group { margin-bottom:.8rem !important; }
    """
    _render_screen(edit_markup, SCREENSHOTS['edit'], edit_css)

    clinical = _authenticated_session('treino.clinico', '198.51.100.52')
    clinical_response = clinical.get(
        f'{TRAINING_BASE_URL}/agenda/',
        params={'semana': '2026-06-22'},
        timeout=15,
    )
    clinical_response.raise_for_status()
    clinical_css = """
    .content-area { padding:1rem 1.25rem !important; }
    .content-area .animate-fade > div:first-child { margin-bottom:1rem !important; }
    .content-area .card { margin-bottom:1rem !important; }
    .agenda-grid-card { max-height:360px !important; }
    .content-area .animate-fade > .card:last-child { display:none !important; }
    """
    _render_screen(clinical_response.text, SCREENSHOTS['clinical'], clinical_css)


def image_uri(path):
    return path.resolve().as_uri()


def _approved_css():
    source = APPROVED_HTML.read_text(encoding='utf-8')
    match = re.search(r'<style>(.*?)</style>', source, re.S)
    if not match:
        raise RuntimeError('CSS do modelo aprovado não encontrado.')
    return match.group(1).replace('Manual 01', 'Manual 05')


def build_manual_html():
    logo = image_uri(LOGO_PATH)
    overview = image_uri(SCREENSHOTS['overview'])
    new = image_uri(SCREENSHOTS['new'])
    edit = image_uri(SCREENSHOTS['edit'])
    clinical = image_uri(SCREENSHOTS['clinical'])
    css = _approved_css()

    return f"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>Manual 05 — Agenda</title><style>{css}</style></head>
<body>
  <section class="cover">
    <div class="cover-logo"><img src="{logo}" alt="Sorriso da Gente"></div>
    <div class="cover-kicker">Manual de operação • 05</div>
    <h1>Agenda</h1>
    <div class="cover-subtitle">Organize paciente, profissional, horário e unidade e mantenha o status operacional de cada consulta atualizado.</div>
    <div class="cover-meta"><div><strong>Público</strong>Recepção, Coordenação e Clínicos</div><div><strong>Versão</strong>4.0.0-rc.1</div><div><strong>Revisão</strong>22 de junho de 2026</div></div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 05 • Agenda</div></header>
    <h2>Antes de começar</h2>
    <p class="lead">A Agenda transforma a demanda da Triagem em organização assistencial: define profissional, data, duração e unidade de execução.</p>
    <div class="flow">
      <div class="flow-step"><div class="flow-number">1</div><strong>Visualizar</strong><span>Respeite o escopo.</span></div>
      <div class="flow-step"><div class="flow-number">2</div><strong>Agendar</strong><span>Defina todos os campos.</span></div>
      <div class="flow-step"><div class="flow-number">3</div><strong>Conferir</strong><span>Use semana e filtros.</span></div>
      <div class="flow-step"><div class="flow-number">4</div><strong>Atualizar</strong><span>Registre o desfecho.</span></div>
    </div>
    <div class="check-grid">
      <div class="check-card"><strong>Paciente e demanda</strong><span>Confirme o prontuário e a especialidade.</span></div>
      <div class="check-card"><strong>Profissional disponível</strong><span>Escolha quem realizará o atendimento.</span></div>
      <div class="check-card"><strong>Unidade correta</strong><span>A unidade é definida nesta etapa.</span></div>
      <div class="check-card"><strong>Status fiel</strong><span>O resultado alimenta fila e indicadores.</span></div>
    </div>
    <div class="warning"><strong>Triagem não define unidade</strong>A origem municipal e a especialidade vêm da Triagem. A unidade de execução é escolhida na Agenda.</div>
    <table class="mini-table">
      <tr><th>Perfil</th><th>Escopo da Agenda</th></tr>
      <tr><td>Recepção</td><td>Visualiza e administra todos os profissionais.</td></tr>
      <tr><td>Coordenação</td><td>Visualiza e acompanha toda a operação.</td></tr>
      <tr><td>Clínicos</td><td>Visualiza e administra somente a própria agenda.</td></tr>
      <tr><td>Administrador</td><td>Possui visão completa para suporte e gestão.</td></tr>
    </table>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 05 • Visão semanal</div></header>
    <div class="step-banner"><div class="step-badge">1</div><div class="step-title"><h2>Compreender semana e filtros</h2><p>A Recepção visualiza toda a agenda da clínica.</p></div></div>
    <div class="screen">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Semana de treinamento • visão completa</div>
      <img src="{overview}" alt="Agenda semanal e filtros">
    </div>
    <div class="columns">
      <div>
        <div class="instruction"><strong>Navegue por semana</strong><p>Use as setas ou o botão Hoje para retornar ao período atual.</p></div>
        <div class="instruction"><strong>Combine os filtros</strong><p>Filtre por profissional, status e unidade de execução.</p></div>
      </div>
      <div class="tip"><strong>Cores e cartões</strong>Cada cartão mostra horário, paciente, profissional, unidade e status.</div>
    </div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 05 • Nova consulta</div></header>
    <div class="step-banner"><div class="step-badge">2</div><div class="step-title"><h2>Criar uma consulta</h2><p>Clique em Nova Consulta e complete a organização do atendimento.</p></div></div>
    <div class="screen">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Exemplo fictício • consulta não gravada</div>
      <img src="{new}" alt="Modal de nova consulta">
    </div>
    <div class="password-rules">
      <div class="rule"><b>Quem</b><span>paciente e profissional</span></div>
      <div class="rule"><b>Quando</b><span>data, hora e duração</span></div>
      <div class="rule"><b>Onde</b><span>unidade de execução</span></div>
    </div>
    <div class="warning"><strong>Unidade obrigatória na prática</strong>Confira se o atendimento ocorrerá na Unidade Principal ou na Unidade de Apoio antes de salvar.</div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 05 • Edição e status</div></header>
    <div class="step-banner"><div class="step-badge">3</div><div class="step-title"><h2>Remanejar e atualizar</h2><p>Use Editar para alterar horário, duração, profissional, unidade ou status.</p></div></div>
    <div class="screen">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Edição ilustrativa • nenhuma alteração salva</div>
      <img src="{edit}" alt="Edição de consulta">
    </div>
    <div class="columns">
      <div>
        <div class="instruction"><strong>Remanejamento</strong><p>Revise data, profissional e unidade antes de salvar alterações.</p></div>
        <div class="instruction"><strong>Observações</strong><p>Registre informações operacionais úteis, sem substituir a evolução clínica.</p></div>
      </div>
      <div class="warning"><strong>Faltou não é Cancelado</strong>Use Faltou somente quando o paciente não comparecer. Se houve desmarcação prévia, use Cancelado.</div>
    </div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 05 • Escopo e desfecho</div></header>
    <div class="step-banner"><div class="step-badge">4</div><div class="step-title"><h2>Respeitar o escopo e registrar o desfecho</h2><p>No perfil Clínicos, o profissional fica fixo na própria agenda.</p></div></div>
    <div class="screen screen-compact">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Perfil Clínicos • agenda própria</div>
      <img src="{clinical}" alt="Agenda no escopo do Clínico">
    </div>
    <table class="mini-table">
      <tr><th>Status</th><th>Quando utilizar</th></tr>
      <tr><td>Pendente</td><td>Consulta criada e ainda sem confirmação.</td></tr>
      <tr><td>Confirmado</td><td>Comparecimento confirmado com o paciente.</td></tr>
      <tr><td>Realizado</td><td>Atendimento efetivamente concluído.</td></tr>
      <tr><td>Faltou</td><td>Paciente não compareceu à consulta.</td></tr>
      <tr><td>Cancelado</td><td>Consulta desmarcada antes do horário.</td></tr>
    </table>
    <div class="columns">
      <div class="success"><strong>Resultado esperado</strong>Consulta na unidade correta, visível no escopo adequado e com status fiel ao ocorrido.</div>
      <div class="tip"><strong>Impacto gerencial</strong>Faltas, cancelamentos e realizações alimentam indicadores e organização da fila.</div>
    </div>
    <div class="closing"><h3>Agenda organizada</h3><p>Com o atendimento marcado, o próximo passo documental é o <b>TCLE</b> do paciente.</p></div>
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
