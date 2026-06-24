#!/usr/bin/env python3
"""Gera capturas e o PDF institucional do Manual 06 — TCLE."""

import html
import re
import sys
from pathlib import Path

from weasyprint import HTML

from generate_agenda_manual import (
    APPROVED_HTML,
    CAPTURES_DIR,
    LOGO_PATH,
    MANUALS_DIR,
    PROJECT_ROOT,
    TRAINING_BASE_URL,
    _authenticated_session,
    _render_screen,
    _set_input_by_name,
)


OUTPUT_PATH = MANUALS_DIR / '06_tcle_v1.0.pdf'
HTML_SOURCE_PATH = MANUALS_DIR / '06_tcle_v1.0.html'

SCREENSHOTS = {
    'locked': CAPTURES_DIR / '06_tcle_01_prontuario_bloqueado.png',
    'review': CAPTURES_DIR / '06_tcle_02_leitura_termo.png',
    'canvas': CAPTURES_DIR / '06_tcle_03_assinatura_em_tela.png',
    'proxy': CAPTURES_DIR / '06_tcle_04_assinatura_a_rogo.png',
    'result': CAPTURES_DIR / '06_tcle_05_prontuario_liberado.png',
}


def _checked(markup, name):
    pattern = rf'(<input\b[^>]*\bname="{re.escape(name)}"[^>]*)(>)'
    return re.sub(pattern, r'\1 checked\2', markup, count=1)


def _signature_markup(markup):
    drawing = """
    <div class="training-signature">
      <svg viewBox="0 0 760 180" role="img" aria-label="Assinatura fictícia">
        <path d="M75 116 C155 23, 155 161, 245 85 S338 150, 417 84
                 C452 55, 450 137, 505 101 S594 60, 673 111"
              fill="none" stroke="#172033" stroke-width="5"
              stroke-linecap="round"/>
        <path d="M205 128 C320 147, 462 142, 625 126"
              fill="none" stroke="#172033" stroke-width="3"
              stroke-linecap="round"/>
      </svg>
    </div>
    """
    return re.sub(
        r'<canvas\b[^>]*\bid="signature-pad"[^>]*>\s*</canvas>',
        drawing,
        markup,
        count=1,
        flags=re.S,
    )


def _prepare_locked(markup):
    alert = """
    <div class="tcle-training-alert">
      <div class="tcle-training-icon">🔒</div>
      <div><strong>Acesso clínico bloqueado</strong>
      <span>Este prontuário será liberado após o registro do TCLE.</span></div>
    </div>
    """
    return markup.replace('<div class="tabs-container">', f'{alert}<div class="tabs-container">', 1)


def _prepare_proxy(markup):
    markup = _checked(markup, 'patient_not_literate')
    markup = _set_input_by_name(markup, 'rogo_validator_username', 'treino.clinico')
    markup = _set_input_by_name(markup, 'rogo_validator_password', '••••••••••••')
    return markup.replace(
        'id="a-rogo-fields" style="display: none;',
        'id="a-rogo-fields" style="display: block;',
        1,
    )


def capture_training_screens():
    clinical = _authenticated_session('treino.clinico', '198.51.100.53')

    locked = clinical.get(f'{TRAINING_BASE_URL}/patients/view/3', timeout=15)
    locked.raise_for_status()
    locked_css = """
    .content-area { padding:1rem 1.5rem !important; }
    .content-area > .animate-fade { margin-bottom:.75rem !important; }
    .tabs-container { margin-top:.75rem !important; }
    .tabs-header { margin-bottom:0 !important; }
    .tab-content { display:none !important; }
    .tcle-training-alert {
      display:flex; align-items:center; gap:1rem; margin:.75rem 0;
      padding:1rem 1.25rem; border:1px solid #fed7a0; border-radius:12px;
      background:#fff7e8; color:#7c3d00;
    }
    .tcle-training-icon { font-size:2rem; }
    .tcle-training-alert strong { display:block; font-size:1.05rem; margin-bottom:.2rem; }
    .tcle-training-alert span { color:#7b5b35; }
    """
    _render_screen(_prepare_locked(locked.text), SCREENSHOTS['locked'], locked_css)

    term = clinical.get(f'{TRAINING_BASE_URL}/patients/tcle/3', timeout=15)
    term.raise_for_status()
    review_css = """
    .content-area { padding:.5rem 1rem !important; }
    .animate-fade {
      max-width:1040px !important; margin:.5rem auto !important;
      padding:1.25rem 2rem !important;
    }
    .animate-fade > div:first-child { margin-bottom:1rem !important; }
    .animate-fade > div:first-child h2 { font-size:1.35rem !important; }
    #tcle-form > div:first-of-type {
      max-height:510px !important; overflow:hidden !important;
      margin-bottom:0 !important; font-size:.9rem !important;
    }
    #tcle-form > div:not(:first-of-type) { display:none !important; }
    """
    _render_screen(term.text, SCREENSHOTS['review'], review_css)

    signature_css = """
    .content-area { padding:.5rem 1rem !important; }
    .animate-fade {
      max-width:1040px !important; margin:.5rem auto !important;
      padding:1.25rem 2rem !important;
    }
    .animate-fade > div:first-child { margin-bottom:1rem !important; }
    .animate-fade > div:first-child h2 { font-size:1.3rem !important; }
    #tcle-form > div { display:none !important; }
    #tcle-form > div:nth-of-type(3) { display:grid !important; gap:1rem !important; margin-bottom:0 !important; }
    #tcle-form > div:nth-of-type(3) > div:first-child { display:none !important; }
    .signature-section { display:block !important; }
    .signature-container { height:260px !important; }
    .training-signature { height:220px; background:#fff; }
    .training-signature svg { width:100%; height:100%; }
    """
    _render_screen(_signature_markup(term.text), SCREENSHOTS['canvas'], signature_css)

    proxy_css = """
    .content-area { padding:.5rem 1rem !important; }
    .animate-fade {
      max-width:1040px !important; margin:.5rem auto !important;
      padding:1.25rem 2rem !important;
    }
    .animate-fade > div:first-child { margin-bottom:1rem !important; }
    .animate-fade > div:first-child h2 { font-size:1.3rem !important; }
    #tcle-form > div { display:none !important; }
    #tcle-form > div:nth-of-type(3) { display:grid !important; gap:1rem !important; margin-bottom:0 !important; }
    #tcle-form > div:nth-of-type(3) > div:first-child { display:block !important; }
    .signature-section { display:none !important; }
    """
    _render_screen(_prepare_proxy(term.text), SCREENSHOTS['proxy'], proxy_css)

    result = clinical.get(f'{TRAINING_BASE_URL}/patients/view/4', timeout=15)
    result.raise_for_status()
    result_css = """
    .content-area { padding:1rem 1.5rem !important; }
    .content-area > .animate-fade { margin-bottom:.75rem !important; }
    .tabs-container { margin-top:.75rem !important; }
    .tabs-header { margin-bottom:0 !important; }
    .tab-content { display:none !important; }
    """
    _render_screen(result.text, SCREENSHOTS['result'], result_css)


def image_uri(path):
    return path.resolve().as_uri()


def _approved_css():
    source = APPROVED_HTML.read_text(encoding='utf-8')
    match = re.search(r'<style>(.*?)</style>', source, re.S)
    if not match:
        raise RuntimeError('CSS do modelo aprovado não encontrado.')
    return match.group(1).replace('Manual 01', 'Manual 06')


def build_manual_html():
    logo = image_uri(LOGO_PATH)
    locked = image_uri(SCREENSHOTS['locked'])
    review = image_uri(SCREENSHOTS['review'])
    canvas = image_uri(SCREENSHOTS['canvas'])
    proxy = image_uri(SCREENSHOTS['proxy'])
    result = image_uri(SCREENSHOTS['result'])
    css = _approved_css() + """
    .screen-short img { height:58mm; object-fit:cover; object-position:top; }
    .screen-pair { display:grid; grid-template-columns:1.25fr .75fr; gap:4mm; margin:3mm 0 4mm; }
    .screen-pair .screen { margin:0; }
    .screen-pair .screen img { height:45mm; object-fit:cover; object-position:top; }
    .screen-pair .screen-bar { font-size:6.8pt; }
    """

    return f"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>Manual 06 — TCLE</title><style>{css}</style></head>
<body>
  <section class="cover">
    <div class="cover-logo"><img src="{logo}" alt="Sorriso da Gente"></div>
    <div class="cover-kicker">Manual de operação • 06</div>
    <h1>Termo de Consentimento — TCLE</h1>
    <div class="cover-subtitle">Registre consentimento livre e esclarecido com assinatura em tela ou assinatura a rogo, preservando segurança e rastreabilidade.</div>
    <div class="cover-meta"><div><strong>Público</strong>Clínicos</div><div><strong>Versão</strong>4.0.0-rc.1</div><div><strong>Revisão</strong>22 de junho de 2026</div></div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 06 • TCLE</div></header>
    <h2>Antes de começar</h2>
    <p class="lead">O TCLE é uma etapa de informação e decisão. O registro eletrônico vem depois da leitura, da compreensão e do consentimento.</p>
    <div class="flow">
      <div class="flow-step"><div class="flow-number">1</div><strong>Identificar</strong><span>Confirme paciente ou responsável.</span></div>
      <div class="flow-step"><div class="flow-number">2</div><strong>Explicar</strong><span>Leia e esclareça dúvidas.</span></div>
      <div class="flow-step"><div class="flow-number">3</div><strong>Assinar</strong><span>Em tela ou a rogo.</span></div>
      <div class="flow-step"><div class="flow-number">4</div><strong>Conferir</strong><span>Verifique a liberação.</span></div>
    </div>
    <div class="check-grid">
      <div class="check-card"><strong>Identidade correta</strong><span>Confira nome, CPF e responsável antes do termo.</span></div>
      <div class="check-card"><strong>Linguagem acessível</strong><span>Adapte a explicação à compreensão do paciente.</span></div>
      <div class="check-card"><strong>Decisão livre</strong><span>Não registre sob pressão ou com dúvidas pendentes.</span></div>
      <div class="check-card"><strong>Credenciais pessoais</strong><span>O CD nunca deve compartilhar sua senha.</span></div>
    </div>
    <div class="warning"><strong>Assinatura a rogo tem uso específico</strong>Utilize somente para paciente não alfabetizado, após leitura em voz alta, explicação e consentimento verbal. Não são exigidas testemunhas.</div>
    <table class="mini-table">
      <tr><th>Modo</th><th>Quando utilizar</th></tr>
      <tr><td>Assinatura em tela</td><td>Paciente alfabetizado ou responsável assina diretamente no quadro.</td></tr>
      <tr><td>Assinatura a rogo</td><td>Paciente não alfabetizado; o CD autentica a declaração com login e senha.</td></tr>
    </table>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 06 • Bloqueio clínico</div></header>
    <div class="step-banner"><div class="step-badge">1</div><div class="step-title"><h2>Reconhecer o bloqueio</h2><p>Sem TCLE, as abas clínicas permanecem indisponíveis.</p></div></div>
    <div class="screen">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Paciente fictício • prontuário sem TCLE</div>
      <img src="{locked}" alt="Prontuário com abas clínicas bloqueadas">
    </div>
    <div class="columns">
      <div>
        <div class="instruction"><strong>Localize o botão</strong><p>No cabeçalho do prontuário, clique em <b>Termo Consentimento</b>.</p></div>
        <div class="instruction"><strong>Observe as abas</strong><p>Anamnese, exames, tratamento e atendimento ficam bloqueados até o registro.</p></div>
      </div>
      <div class="tip"><strong>Proteção assistencial</strong>O bloqueio evita atos clínicos antes da formalização do consentimento.</div>
    </div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 06 • Leitura e esclarecimento</div></header>
    <div class="step-banner"><div class="step-badge">2</div><div class="step-title"><h2>Ler e explicar o termo</h2><p>Confira as partes e percorra todo o documento antes da assinatura.</p></div></div>
    <div class="screen screen-short">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Termo do paciente fictício • início do documento</div>
      <img src="{review}" alt="Conteúdo do TCLE">
    </div>
    <div class="columns">
      <div>
        <div class="instruction"><strong>Confirme os dados</strong><p>Confira paciente, responsável e profissional identificado.</p></div>
        <div class="instruction"><strong>Percorra as seções</strong><p>Explique riscos, benefícios, alternativas, deveres, LGPD e revogação.</p></div>
      </div>
      <div class="warning"><strong>Dúvida interrompe a assinatura</strong>Se algo não estiver compreendido, explique novamente antes de continuar.</div>
    </div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 06 • Assinatura em tela</div></header>
    <div class="step-banner"><div class="step-badge">3</div><div class="step-title"><h2>Registrar a assinatura comum</h2><p>Para paciente alfabetizado, utilize o quadro de assinatura.</p></div></div>
    <div class="screen screen-short">
      <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Assinatura ilustrativa • nenhum termo gravado</div>
      <img src="{canvas}" alt="Quadro de assinatura em tela">
    </div>
    <div class="password-rules">
      <div class="rule"><b>1</b><span>solicite a assinatura</span></div>
      <div class="rule"><b>2</b><span>use Limpar se necessário</span></div>
      <div class="rule"><b>3</b><span>salve somente após conferir</span></div>
    </div>
    <div class="warning"><strong>Assinatura obrigatória</strong>O sistema não conclui o modo comum quando o quadro está vazio.</div>
  </section>

  <section class="page">
    <header class="page-header"><div><img src="{logo}" alt="Sorriso da Gente"></div><div class="page-label">Manual 06 • A rogo e resultado</div></header>
    <div class="step-banner"><div class="step-badge">4</div><div class="step-title"><h2>Registrar a rogo e conferir</h2><p>O CD autentica a declaração; depois, o prontuário clínico é liberado.</p></div></div>
    <div class="screen-pair">
      <div class="screen">
        <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> A rogo • senha protegida</div>
        <img src="{proxy}" alt="Campos de assinatura a rogo">
      </div>
      <div class="screen">
        <div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Exemplo já assinado • abas liberadas</div>
        <img src="{result}" alt="Prontuário com TCLE assinado">
      </div>
    </div>
    <div class="columns">
      <div>
        <div class="instruction"><strong>Declare e autentique</strong><p>Marque paciente não alfabetizado e informe as credenciais do CD responsável.</p></div>
        <div class="instruction"><strong>Confira o resultado</strong><p>O botão muda para <b>Termo Assinado</b> e as abas deixam de estar bloqueadas.</p></div>
      </div>
      <div class="success"><strong>Evidência rastreável</strong>Data, responsável, modo, autenticação, evento e hash de integridade ficam vinculados ao termo.</div>
    </div>
    <div class="closing"><h3>Consentimento registrado</h3><p>Com o TCLE válido, o fluxo clínico pode seguir para a <b>Anamnese</b>.</p></div>
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
