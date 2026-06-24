#!/usr/bin/env python3
"""Gera capturas e o PDF institucional do Manual 02 — Novo usuário."""

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
OUTPUT_PATH = MANUALS_DIR / '02_novo_usuario_v1.0.pdf'
HTML_SOURCE_PATH = MANUALS_DIR / '02_novo_usuario_v1.0.html'

SCREENSHOTS = {
    'users': CAPTURES_DIR / '02_novo_usuario_01_gestao_equipe.png',
    'identification': CAPTURES_DIR / '02_novo_usuario_02_identificacao_acesso.png',
    'professional': CAPTURES_DIR / '02_novo_usuario_03_perfil_profissional.png',
    'result': CAPTURES_DIR / '02_novo_usuario_04_resultado_acoes.png',
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


def _show_container(markup, container_id):
    pattern = rf'(<div\b[^>]*\bid="{re.escape(container_id)}"[^>]*\bstyle=")([^"]*)(")'

    def replace(match):
        style = re.sub(r'display\s*:\s*none\s*;?', 'display:grid;', match.group(2))
        return f'{match.group(1)}{style}{match.group(3)}'

    return re.sub(pattern, replace, markup, count=1)


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


def _authenticated_admin_session():
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
            'username': 'treino.admin',
            'password': password,
        },
        timeout=15,
        allow_redirects=True,
    )
    response.raise_for_status()
    if response.url.rstrip('/').endswith('/login'):
        raise RuntimeError('Não foi possível autenticar o Administrador fictício.')
    return session


def _prepared_user_form(markup):
    values = {
        'full_name': 'Dra. Marina Oliveira Treinamento',
        'username': 'treino.novo.clinico',
        'email': 'marina.treinamento@example.com',
        'celular': '(82) 99999-2026',
        'data_nascimento': '1992-08-17',
        'cns': '700000000000019',
        'cbo': '223208',
        'cnes': '2000001',
        'ine': '0000000001',
        'cro': '98765',
        'cro_uf': 'AL',
    }
    for input_id, value in values.items():
        markup = _set_input_value(markup, input_id, value)
    markup = _select_option(markup, 'is_first_access', '1')
    markup = _select_option(markup, 'role', 'clinicos')
    markup = _select_option(markup, 'active', '1')
    markup = _show_container(markup, 'professional_container')
    markup = _show_container(markup, 'cro_container')
    return markup


def _inject_result_row(markup):
    row = """
    <tr style="border-bottom: 1px solid #dbe5f0; background:#eff6ff;">
      <td style="padding:1.25rem;color:#64748b;">#NOVO</td>
      <td style="padding:1.25rem;font-weight:700;">treino.novo.clinico</td>
      <td style="padding:1.25rem;"><span style="padding:.4rem .8rem;border-radius:20px;font-size:.75rem;font-weight:700;text-transform:uppercase;background:#f1f5f9;color:#475569;">Clínicos</span></td>
      <td style="padding:1.25rem;"><span style="padding:.4rem .8rem;border-radius:20px;font-size:.75rem;font-weight:700;text-transform:uppercase;background:#dcfce7;color:#166534;">Ativo</span><div style="margin-top:.5rem;font-size:.75rem;color:#0f766e;font-weight:700;">Primeiro acesso pendente</div></td>
      <td style="padding:1.25rem;color:#64748b;font-size:.85rem;">Nunca acessou</td>
      <td style="padding:1.25rem;text-align:right;"><span class="btn btn-outline" style="padding:.4rem .8rem;font-size:.8rem;">✏️ Editar</span> <span class="btn btn-outline" style="padding:.4rem .8rem;font-size:.8rem;border-color:#fee2e2;color:#991b1b;">🗑️ Excluir</span></td>
    </tr>
    """
    return markup.replace('<tbody>', f'<tbody>{row}', 1)


def capture_training_screens():
    health = requests.get(f'{TRAINING_BASE_URL}/health', timeout=10)
    health.raise_for_status()
    session = _authenticated_admin_session()

    users_response = session.get(f'{TRAINING_BASE_URL}/admin/users', timeout=15)
    users_response.raise_for_status()
    list_css = """
    .content-area { padding: 1.25rem 1.5rem !important; }
    .content-area .animate-fade > div:first-child { display:none !important; }
    .content-area .animate-fade > div:nth-child(2) { margin-bottom:1rem !important; }
    table th, table td { padding:.65rem .75rem !important; }
    """
    _render_screen(users_response.text, SCREENSHOTS['users'], list_css)
    _render_screen(
        _inject_result_row(users_response.text),
        SCREENSHOTS['result'],
        list_css,
    )

    form_response = session.get(f'{TRAINING_BASE_URL}/admin/users/add', timeout=15)
    form_response.raise_for_status()
    prepared_form = _prepared_user_form(form_response.text)

    identification_css = """
    .content-area { padding:0 !important; }
    .content-area > div { margin:1rem auto !important; }
    .content-area > div > div:first-child { display:none !important; }
    .content-area .card { padding:1.25rem 2rem !important; }
    .content-area .card > div:first-child { margin-bottom:1rem !important; }
    #professional_container, #cro_container { display:none !important; }
    #role, #active, label[for="role"], label[for="active"] { }
    """
    _render_screen(prepared_form, SCREENSHOTS['identification'], identification_css)

    professional_css = """
    .content-area { padding:0 !important; }
    .content-area > div { margin:-520px auto 0 !important; }
    .content-area > div > div:first-child { display:none !important; }
    .content-area .card { padding:1.25rem 2rem !important; }
    .content-area .card > div:first-child { display:none !important; }
    """
    _render_screen(prepared_form, SCREENSHOTS['professional'], professional_css)


def image_uri(path):
    return path.resolve().as_uri()


def _approved_css():
    if not APPROVED_HTML.exists():
        raise RuntimeError('Gere e aprove primeiro o Manual 01.')
    source = APPROVED_HTML.read_text(encoding='utf-8')
    match = re.search(r'<style>(.*?)</style>', source, re.S)
    if not match:
        raise RuntimeError('CSS do modelo aprovado não encontrado.')
    css = match.group(1).replace('Manual 01', 'Manual 02')
    return css


def build_manual_html():
    logo = image_uri(LOGO_PATH)
    users = image_uri(SCREENSHOTS['users'])
    identification = image_uri(SCREENSHOTS['identification'])
    professional = image_uri(SCREENSHOTS['professional'])
    result = image_uri(SCREENSHOTS['result'])
    css = _approved_css()

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>Manual 02 — Novo usuário</title>
  <style>{css}</style>
</head>
<body>
  <section class="cover">
    <div class="cover-logo"><img src="{logo}" alt="Sorriso da Gente"></div>
    <div class="cover-kicker">Manual de operação • 02</div>
    <h1>Novo usuário</h1>
    <div class="cover-subtitle">Cadastre a equipe, aplique o perfil correto e encaminhe cada profissional ao primeiro acesso com segurança.</div>
    <div class="cover-meta">
      <div><strong>Público</strong>Administrador</div>
      <div><strong>Versão</strong>4.0.0-rc.1</div>
      <div><strong>Revisão</strong>22 de junho de 2026</div>
    </div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 02 • Novo usuário</div></header>
    <h2>Antes de começar</h2>
    <p class="lead">O perfil selecionado define os menus, informações e operações disponíveis. Confirme a função real antes de criar a credencial.</p>
    <div class="flow">
      <div class="flow-step"><div class="flow-number">1</div><strong>Abrir</strong><span>Acesse Usuários.</span></div>
      <div class="flow-step"><div class="flow-number">2</div><strong>Identificar</strong><span>Preencha dados pessoais.</span></div>
      <div class="flow-step"><div class="flow-number">3</div><strong>Autorizar</strong><span>Escolha perfil e status.</span></div>
      <div class="flow-step"><div class="flow-number">4</div><strong>Conferir</strong><span>Revise o registro criado.</span></div>
    </div>
    <div class="check-grid">
      <div class="check-card"><strong>Função confirmada</strong><span>O perfil deve corresponder ao trabalho realizado.</span></div>
      <div class="check-card"><strong>Login único</strong><span>Prefira um padrão institucional fácil de identificar.</span></div>
      <div class="check-card"><strong>Nascimento conferido</strong><span>Esse dado valida o primeiro acesso.</span></div>
      <div class="check-card"><strong>Registro profissional</strong><span>Separe CNS, CBO e CRO quando exigidos.</span></div>
    </div>
    <table class="mini-table">
      <tr><th>Perfil</th><th>Uso principal</th></tr>
      <tr><td>Administrador</td><td>Configuração, usuários, auditoria e gestão completa.</td></tr>
      <tr><td>Coordenação</td><td>Central de Comando, indicadores e acompanhamento clínico.</td></tr>
      <tr><td>Clínicos</td><td>Prontuário, exames, plano, evolução e assinaturas.</td></tr>
      <tr><td>Recepção</td><td>Cadastro de pacientes, triagem e agenda.</td></tr>
      <tr><td>Demais perfis</td><td>CME, Radiologia, Comunicação, SSA/SMS e Auditoria têm escopos próprios.</td></tr>
    </table>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 02 • Gestão da equipe</div></header>
    <div class="step-banner"><div class="step-badge">1</div><div class="step-title"><h2>Abrir a gestão da equipe</h2><p>No menu Administração, escolha Usuários.</p></div></div>
    <div class="screen">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Gestão de Equipe • ambiente de treinamento</div>
      <img src="{users}" alt="Lista de usuários">
    </div>
    <div class="columns">
      <div>
        <div class="instruction"><strong>Observe os acessos</strong><p>A lista informa perfil, situação, primeiro acesso e último login.</p></div>
        <div class="instruction"><strong>Inicie o cadastro</strong><p>Clique em <b>Novo Usuário</b>, no canto superior direito.</p></div>
      </div>
      <div class="tip"><strong>Acesso restrito</strong>A criação e alteração de credenciais exige perfil Administrador.</div>
    </div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 02 • Identificação</div></header>
    <div class="step-banner"><div class="step-badge">2</div><div class="step-title"><h2>Identificar e preparar o acesso</h2><p>Use somente informações conferidas e autorizadas.</p></div></div>
    <div class="screen">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Exemplo fictício • nenhuma senha exibida</div>
      <img src="{identification}" alt="Identificação do novo usuário">
    </div>
    <div class="columns">
      <div>
        <div class="instruction"><strong>Nome, login e contatos</strong><p>O login deve ser único. E-mail e celular apoiam comunicação e recuperação.</p></div>
        <div class="instruction"><strong>Data de nascimento</strong><p>É obrigatória quando o primeiro acesso estiver pendente.</p></div>
      </div>
      <div class="warning"><strong>Não crie senha para o usuário</strong>Mantenha <b>Primeiro acesso pendente</b> e deixe a senha inicial em branco. O profissional criará a própria senha.</div>
    </div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 02 • Perfil profissional</div></header>
    <div class="step-banner"><div class="step-badge">3</div><div class="step-title"><h2>Definir perfil e registros</h2><p>O exemplo usa o perfil Clínicos para mostrar todos os campos.</p></div></div>
    <div class="screen">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Dados profissionais fictícios</div>
      <img src="{professional}" alt="Perfil e dados profissionais">
    </div>
    <div class="password-rules">
      <div class="rule"><b>CNS</b><span>identificação nacional do profissional</span></div>
      <div class="rule"><b>CBO</b><span>ocupação exercida no serviço</span></div>
      <div class="rule"><b>CRO</b><span>obrigatório para o perfil Clínicos</span></div>
    </div>
    <div class="columns">
      <div class="instruction"><strong>CNES e INE</strong><p>Identificam estabelecimento e equipe quando aplicáveis às integrações assistenciais.</p></div>
      <div class="warning"><strong>Princípio do menor acesso</strong>Conceda somente as permissões necessárias para a função real.</div>
    </div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 02 • Conferência e ciclo de vida</div></header>
    <div class="step-banner"><div class="step-badge">4</div><div class="step-title"><h2>Salvar, conferir e administrar</h2><p>O cadastro deve aparecer ativo e aguardando primeiro acesso.</p></div></div>
    <div class="screen screen-compact">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Resultado ilustrativo • registro não gravado</div>
      <img src="{result}" alt="Resultado do cadastro">
    </div>
    <div class="columns">
      <div class="success"><strong>Resultado esperado</strong>Usuário ativo, perfil correto, último login como “Nunca acessou” e indicação “Primeiro acesso pendente”.</div>
      <div class="warning"><strong>Excluir ou inativar?</strong>Exclua somente quem não possui histórico. Havendo acesso ou vínculo operacional, use <b>Inativar acesso</b>.</div>
    </div>
    <table class="mini-table">
      <tr><th>Se acontecer</th><th>O que fazer</th></tr>
      <tr><td>Login já utilizado</td><td>Escolha outro login no padrão institucional.</td></tr>
      <tr><td>Nascimento ausente</td><td>Preencha-o para liberar o primeiro acesso.</td></tr>
      <tr><td>Dados profissionais incompletos</td><td>Confira CNS, CBO e, para Clínicos, CRO e UF.</td></tr>
      <tr><td>Usuário saiu da equipe</td><td>Inative o acesso para preservar o histórico.</td></tr>
    </table>
    <div class="closing"><h3>Credencial pronta</h3><p>Oriente o profissional a usar o fluxo <b>Primeiro acesso</b> com seu login e data de nascimento cadastrada.</p></div>
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
