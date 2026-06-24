#!/usr/bin/env python3
"""Gera capturas reais e o PDF institucional do Manual 01."""

import html
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import requests
from dotenv import dotenv_values
from flask import Flask, render_template
from flask_login import LoginManager
from weasyprint import HTML


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAINING_BASE_URL = os.getenv('TRAINING_BASE_URL', 'http://127.0.0.1:5103').rstrip('/')
CAPTURES_DIR = PROJECT_ROOT / 'docs' / 'manuais_e_treinamentos' / 'capturas'
MANUALS_DIR = PROJECT_ROOT / 'docs' / 'manuais_e_treinamentos' / 'manuais_pdf'
LOGO_PATH = PROJECT_ROOT / 'static' / 'logo_sorriso_horizontal.png'
INSTITUTIONAL_PATH = PROJECT_ROOT / 'static' / 'logo_sorriso_institucional.png'
OUTPUT_PATH = MANUALS_DIR / '01_primeiro_acesso_v1.0.pdf'
HTML_SOURCE_PATH = MANUALS_DIR / '01_primeiro_acesso_v1.0.html'

SCREENSHOTS = {
    'login': CAPTURES_DIR / '01_primeiro_acesso_01_login.png',
    'identity': CAPTURES_DIR / '01_primeiro_acesso_02_validar_identidade.png',
    'password': CAPTURES_DIR / '01_primeiro_acesso_03_definir_senha.png',
    'dashboard': CAPTURES_DIR / '01_primeiro_acesso_04_dashboard_saida.png',
}

SCREEN_CSS = """
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
        raise RuntimeError('Token CSRF não encontrado no ambiente de treinamento.')
    return html.unescape(match.group(1))


def _inject_screen_css(markup):
    return markup.replace('</head>', f'{SCREEN_CSS}</head>', 1)


def _set_input_value(markup, input_id, value):
    pattern = rf'(<input\b[^>]*\bid="{re.escape(input_id)}"[^>]*)(>)'
    replacement = rf'\1 value="{html.escape(value, quote=True)}"\2'
    return re.sub(pattern, replacement, markup, count=1)


def _render_screen(markup, output_path):
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            'PyMuPDF é necessário apenas para gerar as capturas. '
            'Instale-o em um ambiente de ferramentas e execute novamente.'
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    screen_pdf = Path('/tmp') / f'{output_path.stem}.pdf'
    HTML(
        string=_inject_screen_css(markup),
        base_url=f'{TRAINING_BASE_URL}/',
    ).write_pdf(screen_pdf)
    document = fitz.open(screen_pdf)
    page = document[0]
    pixmap = page.get_pixmap(matrix=fitz.Matrix(1.35, 1.35), alpha=False)
    pixmap.save(output_path)
    document.close()
    screen_pdf.unlink(missing_ok=True)


def _render_password_screen_from_template():
    app = Flask(
        'manual_capture',
        template_folder=str(PROJECT_ROOT / 'templates'),
        static_folder=str(PROJECT_ROOT / 'static'),
    )
    app.secret_key = 'manual-capture-only'
    login_manager = LoginManager(app)

    @login_manager.user_loader
    def _load_user(_user_id):
        return None

    app.jinja_env.globals['csrf_token'] = lambda: 'manual-capture'
    user = SimpleNamespace(
        full_name='Primeiro Acesso Treinamento',
        username='treino.primeiro',
    )
    with app.test_request_context('/primeiro-acesso/definir-senha'):
        return render_template(
            'auth/first_access_set_password.html',
            user=user,
            current_email='treino.primeiro@example.com',
        )


def capture_training_screens():
    health = requests.get(f'{TRAINING_BASE_URL}/health', timeout=10)
    health.raise_for_status()

    public_session = requests.Session()
    login_response = public_session.get(f'{TRAINING_BASE_URL}/login', timeout=15)
    login_response.raise_for_status()
    _render_screen(login_response.text, SCREENSHOTS['login'])

    first_access_response = public_session.get(
        f'{TRAINING_BASE_URL}/primeiro-acesso',
        timeout=15,
    )
    first_access_response.raise_for_status()
    identity_markup = _set_input_value(
        first_access_response.text,
        'username',
        'treino.primeiro',
    )
    identity_markup = _set_input_value(identity_markup, 'birthdate', '1990-01-15')
    _render_screen(identity_markup, SCREENSHOTS['identity'])

    _render_screen(
        _render_password_screen_from_template(),
        SCREENSHOTS['password'],
    )

    training_env = dotenv_values(PROJECT_ROOT / '.env.training')
    default_password = training_env.get('TRAINING_DEFAULT_PASSWORD')
    if not default_password:
        raise RuntimeError('TRAINING_DEFAULT_PASSWORD não está configurada.')

    authenticated_session = requests.Session()
    login_page = authenticated_session.get(f'{TRAINING_BASE_URL}/login', timeout=15)
    login_page.raise_for_status()
    dashboard_response = authenticated_session.post(
        f'{TRAINING_BASE_URL}/login',
        data={
            'csrf_token': _csrf_token(login_page.text),
            'username': 'treino.recepcao',
            'password': default_password,
        },
        timeout=15,
        allow_redirects=True,
    )
    dashboard_response.raise_for_status()
    if dashboard_response.url.rstrip('/').endswith('/login'):
        raise RuntimeError('Não foi possível autenticar o usuário fictício.')
    _render_screen(dashboard_response.text, SCREENSHOTS['dashboard'])


def image_uri(path):
    return path.resolve().as_uri()


def build_manual_html():
    logo = image_uri(LOGO_PATH)
    institutional = image_uri(INSTITUTIONAL_PATH)
    login = image_uri(SCREENSHOTS['login'])
    identity = image_uri(SCREENSHOTS['identity'])
    password = image_uri(SCREENSHOTS['password'])
    dashboard = image_uri(SCREENSHOTS['dashboard'])

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>Manual 01 — Primeiro acesso</title>
  <style>
    @page {{
      size: A4 portrait;
      margin: 15mm 15mm 17mm;
      @bottom-left {{
        content: "Gestão Saúde Oral • Manual 01";
        font-family: Arial, sans-serif;
        font-size: 7.5pt;
        color: #64748b;
      }}
      @bottom-right {{
        content: counter(page) " / " counter(pages);
        font-family: Arial, sans-serif;
        font-size: 7.5pt;
        color: #64748b;
      }}
    }}
    @page cover {{ margin: 0; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: #172033;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 9.6pt;
      line-height: 1.48;
    }}
    .cover {{
      page: cover;
      height: 297mm;
      position: relative;
      overflow: hidden;
      background: linear-gradient(145deg, #0b367c 0%, #0d47a1 58%, #0879bd 100%);
      color: white;
      padding: 24mm 20mm;
    }}
    .cover:before {{
      content: "";
      position: absolute;
      width: 170mm;
      height: 170mm;
      right: -78mm;
      top: -55mm;
      border: 22mm solid rgba(255,255,255,.07);
      border-radius: 50%;
    }}
    .cover:after {{
      content: "";
      position: absolute;
      width: 120mm;
      height: 120mm;
      left: -72mm;
      bottom: -65mm;
      border: 16mm solid rgba(247,148,30,.28);
      border-radius: 50%;
    }}
    .cover-logo {{
      display: inline-block;
      background: white;
      border-radius: 16px;
      padding: 10px 18px;
      box-shadow: 0 16px 38px rgba(0,0,0,.18);
    }}
    .cover-logo img {{ width: 61mm; display: block; }}
    .cover-kicker {{
      margin-top: 44mm;
      color: #f7941e;
      font-size: 10pt;
      font-weight: 800;
      letter-spacing: .18em;
      text-transform: uppercase;
    }}
    .cover h1 {{
      margin: 6mm 0 4mm;
      max-width: 145mm;
      font-size: 34pt;
      line-height: 1.02;
      letter-spacing: -.035em;
    }}
    .cover-subtitle {{
      max-width: 130mm;
      color: #dbeafe;
      font-size: 13pt;
      line-height: 1.45;
    }}
    .cover-meta {{
      position: absolute;
      left: 20mm;
      right: 20mm;
      bottom: 20mm;
      display: table;
      width: calc(100% - 40mm);
      border-top: 1px solid rgba(255,255,255,.3);
      padding-top: 7mm;
      font-size: 9pt;
      color: #dbeafe;
    }}
    .cover-meta > div {{ display: table-cell; width: 33.333%; }}
    .cover-meta strong {{ display: block; color: white; margin-bottom: 1mm; }}
    .page {{ page-break-before: always; }}
    .page-header {{
      display: table;
      width: 100%;
      border-bottom: 2px solid #dbe7f6;
      padding-bottom: 4mm;
      margin-bottom: 7mm;
    }}
    .page-header > div {{ display: table-cell; vertical-align: middle; }}
    .page-header img {{ width: 43mm; }}
    .page-label {{
      text-align: right;
      color: #0d47a1;
      font-weight: 800;
      font-size: 8pt;
      letter-spacing: .08em;
      text-transform: uppercase;
    }}
    h2 {{
      margin: 0 0 2.5mm;
      color: #0d47a1;
      font-size: 22pt;
      line-height: 1.12;
      letter-spacing: -.025em;
    }}
    .lead {{
      margin: 0 0 7mm;
      color: #526279;
      font-size: 11pt;
      line-height: 1.55;
    }}
    .flow {{
      display: table;
      width: 100%;
      table-layout: fixed;
      margin: 6mm 0 8mm;
    }}
    .flow-step {{
      display: table-cell;
      position: relative;
      padding-right: 4mm;
      vertical-align: top;
    }}
    .flow-step:last-child {{ padding-right: 0; }}
    .flow-number {{
      width: 9mm;
      height: 9mm;
      border-radius: 50%;
      background: #0d47a1;
      color: white;
      text-align: center;
      line-height: 9mm;
      font-weight: 800;
      margin-bottom: 2mm;
    }}
    .flow-step strong {{ color: #163f75; font-size: 9.2pt; }}
    .flow-step span {{ display: block; color: #64748b; font-size: 8.2pt; margin-top: 1mm; }}
    .check-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 4mm;
      margin: 5mm 0 8mm;
    }}
    .check-card {{
      border: 1px solid #dbe7f6;
      border-radius: 10px;
      padding: 4mm;
      background: #f8fbff;
    }}
    .check-card strong {{ display: block; color: #0d47a1; margin-bottom: 1.2mm; }}
    .check-card span {{ color: #526279; font-size: 8.6pt; }}
    .step-banner {{
      display: table;
      width: 100%;
      margin-bottom: 6mm;
    }}
    .step-badge, .step-title {{ display: table-cell; vertical-align: middle; }}
    .step-badge {{
      width: 15mm;
      height: 15mm;
      border-radius: 50%;
      text-align: center;
      background: #f7941e;
      color: white;
      font-size: 17pt;
      line-height: 15mm;
      font-weight: 800;
    }}
    .step-title {{ padding-left: 4mm; }}
    .step-title h2 {{ margin: 0; }}
    .step-title p {{ margin: 1mm 0 0; color: #64748b; }}
    .screen {{
      border: 1px solid #cdd9e8;
      border-radius: 11px;
      background: #eaf0f7;
      padding: 3mm;
      box-shadow: 0 9px 24px rgba(15, 52, 96, .12);
      margin: 4mm 0 6mm;
      page-break-inside: avoid;
    }}
    .screen-bar {{
      height: 6mm;
      padding: 0 1mm 2mm;
      color: #7b8798;
      font-size: 8pt;
    }}
    .screen-dot {{
      display: inline-block;
      width: 2.5mm;
      height: 2.5mm;
      border-radius: 50%;
      margin-right: 1.2mm;
      background: #f87171;
    }}
    .screen-dot:nth-child(2) {{ background: #fbbf24; }}
    .screen-dot:nth-child(3) {{ background: #34d399; }}
    .screen img {{
      display: block;
      width: 100%;
      border-radius: 7px;
      background: white;
    }}
    .screen-compact {{
      width: 74%;
      margin-left: auto;
      margin-right: auto;
    }}
    .columns {{
      display: grid;
      grid-template-columns: 1.25fr .75fr;
      gap: 6mm;
      align-items: start;
    }}
    .instruction {{
      border-left: 4px solid #0d47a1;
      padding: 3mm 4mm;
      margin-bottom: 3mm;
      background: #f3f7fd;
      border-radius: 0 8px 8px 0;
    }}
    .instruction strong {{ color: #0d47a1; }}
    .instruction p {{ margin: 1.4mm 0 0; color: #475569; }}
    .tip, .warning, .success {{
      border-radius: 10px;
      padding: 4mm;
      margin: 4mm 0;
      page-break-inside: avoid;
    }}
    .tip {{ background: #eef7ff; border: 1px solid #cfe7fb; }}
    .warning {{ background: #fff7e8; border: 1px solid #fed7a0; }}
    .success {{ background: #edfdf5; border: 1px solid #b7efd1; }}
    .tip strong, .warning strong, .success strong {{ display: block; margin-bottom: 1mm; }}
    .tip strong {{ color: #075985; }}
    .warning strong {{ color: #a65300; }}
    .success strong {{ color: #087443; }}
    .bullet-list {{ margin: 2mm 0 0; padding-left: 5mm; }}
    .bullet-list li {{ margin: 1.5mm 0; color: #475569; }}
    .password-rules {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 3mm;
      margin: 5mm 0;
    }}
    .rule {{
      text-align: center;
      padding: 4mm 2mm;
      border-radius: 9px;
      background: #f5f8fc;
      border: 1px solid #dbe5f0;
    }}
    .rule b {{ display: block; color: #0d47a1; font-size: 15pt; margin-bottom: 1mm; }}
    .rule span {{ color: #64748b; font-size: 8pt; }}
    .closing {{
      margin-top: 3mm;
      padding: 4mm;
      background: linear-gradient(135deg, #0d47a1, #0879bd);
      color: white;
      border-radius: 12px;
    }}
    .closing h3 {{ margin: 0 0 2mm; font-size: 15pt; }}
    .closing p {{ margin: 0; color: #dbeafe; }}
    .mini-table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 3mm;
      font-size: 8.2pt;
    }}
    .mini-table th {{
      text-align: left;
      background: #0d47a1;
      color: white;
      padding: 2mm 3mm;
    }}
    .mini-table td {{
      border-bottom: 1px solid #e2e8f0;
      padding: 1.8mm 3mm;
      vertical-align: top;
    }}
    .mini-table td:first-child {{ color: #0d47a1; font-weight: 700; width: 34%; }}
  </style>
</head>
<body>
  <section class="cover">
    <div class="cover-logo"><img src="{logo}" alt="Sorriso da Gente"></div>
    <div class="cover-kicker">Manual de operação • 01</div>
    <h1>Primeiro acesso</h1>
    <div class="cover-subtitle">
      Valide sua identidade, crie a senha definitiva e entre no Gestão Saúde
      Oral com segurança.
    </div>
    <div class="cover-meta">
      <div><strong>Público</strong>Todos os perfis</div>
      <div><strong>Versão</strong>4.0.0-rc.1</div>
      <div><strong>Revisão</strong>22 de junho de 2026</div>
    </div>
  </section>

  <section class="page">
    <header class="page-header">
      <div><img src="{logo}" alt="Sorriso da Gente"></div>
      <div class="page-label">Manual 01 • Primeiro acesso</div>
    </header>
    <h2>Antes de começar</h2>
    <p class="lead">
      O primeiro acesso é realizado uma única vez, depois que o cadastro do
      profissional é aprovado pela administração.
    </p>
    <div class="flow">
      <div class="flow-step"><div class="flow-number">1</div><strong>Abrir</strong><span>Escolha Primeiro acesso.</span></div>
      <div class="flow-step"><div class="flow-number">2</div><strong>Validar</strong><span>Informe login e nascimento.</span></div>
      <div class="flow-step"><div class="flow-number">3</div><strong>Proteger</strong><span>Cadastre e-mail e senha.</span></div>
      <div class="flow-step"><div class="flow-number">4</div><strong>Confirmar</strong><span>Confira nome e perfil.</span></div>
    </div>
    <div class="check-grid">
      <div class="check-card"><strong>Login liberado</strong><span>Use exatamente o identificador informado pela administração.</span></div>
      <div class="check-card"><strong>Data cadastrada</strong><span>A data de nascimento deve coincidir com o cadastro aprovado.</span></div>
      <div class="check-card"><strong>E-mail válido</strong><span>Ele será necessário para recuperar a senha futuramente.</span></div>
      <div class="check-card"><strong>Dispositivo confiável</strong><span>Evite concluir o acesso em equipamentos desconhecidos.</span></div>
    </div>
    <div class="tip"><strong>Este manual acompanha você do início ao fim</strong>Siga as quatro etapas na ordem. O sistema libera a página inicial somente depois da criação da senha definitiva.</div>
  </section>

  <section class="page">
    <header class="page-header">
      <div><img src="{logo}" alt="Sorriso da Gente"></div>
      <div class="page-label">Manual 01 • Entrada</div>
    </header>
    <div class="step-banner">
      <div class="step-badge">1</div>
      <div class="step-title"><h2>Abrir o primeiro acesso</h2><p>Comece pela página de entrada do sistema.</p></div>
    </div>
    <div class="screen">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Gestão Saúde Oral</div>
      <img src="{login}" alt="Tela de login">
    </div>
    <div class="tip"><strong>Qual botão usar?</strong>Na primeira entrada, escolha <b>Primeiro acesso</b>. O botão <b>Entrar</b> será utilizado depois da criação da senha definitiva.</div>
  </section>

  <section class="page">
    <header class="page-header">
      <div><img src="{logo}" alt="Sorriso da Gente"></div>
      <div class="page-label">Manual 01 • Validação</div>
    </header>
    <div class="step-banner">
      <div class="step-badge">2</div>
      <div class="step-title"><h2>Validar sua identidade</h2><p>O sistema compara os dados com o cadastro aprovado.</p></div>
    </div>
    <div class="screen">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Exemplo com dados fictícios</div>
      <img src="{identity}" alt="Tela de validação do primeiro acesso">
    </div>
    <div class="columns">
      <div>
        <div class="instruction"><strong>1. Informe o login</strong><p>Digite o login exatamente como foi fornecido. Observe pontos, hífens e demais caracteres.</p></div>
        <div class="instruction"><strong>2. Informe o nascimento</strong><p>Selecione a mesma data registrada no cadastro profissional.</p></div>
        <div class="instruction"><strong>3. Valide</strong><p>Clique em <b>Validar primeiro acesso</b> para seguir.</p></div>
      </div>
      <div class="warning">
        <strong>Dados não reconhecidos?</strong>
        Não crie outro cadastro. Confirme o login e a data com a administração.
        Por segurança, tentativas repetidas podem ser temporariamente limitadas.
      </div>
    </div>
    <div class="tip"><strong>Sobre a captura</strong>O login e a data exibidos são exclusivamente fictícios e pertencem ao ambiente isolado de treinamento.</div>
  </section>

  <section class="page">
    <header class="page-header">
      <div><img src="{logo}" alt="Sorriso da Gente"></div>
      <div class="page-label">Manual 01 • Senha definitiva</div>
    </header>
    <div class="step-banner">
      <div class="step-badge">3</div>
      <div class="step-title"><h2>Criar a senha definitiva</h2><p>Confirme o e-mail de recuperação e proteja sua conta.</p></div>
    </div>
    <div class="screen">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Definir senha definitiva</div>
      <img src="{password}" alt="Tela para definir e-mail e senha">
    </div>
    <div class="password-rules">
      <div class="rule"><b>8+</b><span>pelo menos oito caracteres</span></div>
      <div class="rule"><b>A</b><span>pelo menos uma letra</span></div>
      <div class="rule"><b>1</b><span>pelo menos um número</span></div>
    </div>
    <div class="columns">
      <div>
        <div class="instruction"><strong>Confirme o e-mail</strong><p>Use um endereço válido, acessível e de uso pessoal ou institucional autorizado.</p></div>
        <div class="instruction"><strong>Digite duas vezes</strong><p>A nova senha e a confirmação precisam ser idênticas.</p></div>
      </div>
      <div class="warning"><strong>Evite senhas previsíveis</strong>Não utilize CPF, data de nascimento, telefone ou uma senha já usada em outro serviço.</div>
    </div>
  </section>

  <section class="page">
    <header class="page-header">
      <div><img src="{logo}" alt="Sorriso da Gente"></div>
      <div class="page-label">Manual 01 • Confirmação</div>
    </header>
    <div class="step-banner">
      <div class="step-badge">4</div>
      <div class="step-title"><h2>Confirmar o acesso</h2><p>A página inicial indica que o procedimento foi concluído.</p></div>
    </div>
    <div class="screen screen-compact">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Página inicial • perfil fictício de Recepção</div>
      <img src="{dashboard}" alt="Página inicial após autenticação">
    </div>
    <div class="columns">
      <div class="success">
        <strong>Confira antes de trabalhar</strong>
        Verifique seu nome, o perfil exibido no menu lateral e as funções
        disponíveis. Se algo estiver incorreto, informe a administração.
      </div>
      <div class="warning">
        <strong>Saída segura</strong>
        Em computador compartilhado, clique sempre em <b>Sair</b>. Fechar
        apenas a aba não substitui o encerramento da sessão.
      </div>
    </div>
    <table class="mini-table">
      <tr><th>Se acontecer</th><th>O que fazer</th></tr>
      <tr><td>Login ou nascimento inválidos</td><td>Confirme os dados com a administração.</td></tr>
      <tr><td>As senhas não conferem</td><td>Digite novamente os dois campos.</td></tr>
      <tr><td>Senha recusada</td><td>Use ao menos oito caracteres, uma letra e um número.</td></tr>
      <tr><td>Primeiro acesso já concluído</td><td>Volte ao login e use a senha definitiva.</td></tr>
    </table>
    <div class="closing">
      <h3>Primeiro acesso concluído</h3>
      <p>Nos próximos acessos, utilize o botão <b>Entrar</b> com seu login e sua senha definitiva.</p>
    </div>
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
