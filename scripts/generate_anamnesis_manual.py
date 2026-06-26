#!/usr/bin/env python3
"""Gera capturas e o PDF institucional do Manual 07 — Anamnese."""

import html
import re
import sys

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
    _set_textarea,
)
from generate_tcle_manual import _signature_markup


OUTPUT_PATH = MANUALS_DIR / '07_anamnese_v1.0.pdf'
HTML_SOURCE_PATH = MANUALS_DIR / '07_anamnese_v1.0.html'
SCREENSHOTS = {
    'start': CAPTURES_DIR / '07_anamnese_01_queixa_historia.png',
    'medical': CAPTURES_DIR / '07_anamnese_02_historico_medico.png',
    'dental': CAPTURES_DIR / '07_anamnese_03_odontologico_habitos.png',
    'canvas': CAPTURES_DIR / '07_anamnese_04_assinatura_em_tela.png',
    'proxy': CAPTURES_DIR / '07_anamnese_05_assinatura_a_rogo.png',
    'result': CAPTURES_DIR / '07_anamnese_06_ficha_concluida.png',
}


def _set_radio(markup, name, value):
    markup = re.sub(
        rf'(<input\b[^>]*\bname="{re.escape(name)}"[^>]*)(>)',
        lambda m: re.sub(r'\schecked(?=[\s>])', '', m.group(1)) + m.group(2),
        markup,
    )
    pattern = rf'(<input\b(?=[^>]*\bname="{re.escape(name)}")(?=[^>]*\bvalue="{re.escape(value)}")[^>]*)(>)'
    return re.sub(pattern, r'\1 checked\2', markup, count=1)


def _set_select(markup, name, value):
    pattern = rf'(<select\b[^>]*\bname="{re.escape(name)}"[^>]*>)(.*?)(</select>)'

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


def _prepare_form(markup):
    markup = _set_textarea(markup, 'queixa_principal', 'Sensibilidade ao frio no dente posterior superior.')
    markup = _set_textarea(
        markup,
        'historia_doenca_atual',
        'Sintoma iniciado há duas semanas, de curta duração e sem dor espontânea.',
    )
    for name in (
        'sofre_doenca', 'tratamento_medico', 'desmaios_convulsoes', 'tem_cancer',
        'radioterapia_quimioterapia', 'falta_ar', 'fez_cirurgia', 'foi_hospitalizado',
        'reacao_anestesia', 'fuma', 'ingere_alcool',
    ):
        markup = _set_radio(markup, name, 'Não')
    markup = _set_radio(markup, 'tomando_medicamento', 'Sim')
    markup = _set_input_by_name(markup, 'tomando_medicamento_explica', 'Losartana 50 mg — relato fictício.')
    markup = _set_radio(markup, 'tem_alergia', 'Sim')
    markup = _set_input_by_name(markup, 'tem_alergia_explica', 'Dipirona — relato fictício.')
    markup = _set_input_by_name(markup, 'alergia_medicamento_alimento', 'Dipirona — relato fictício.')
    markup = _set_select(markup, 'pressao_arterial', 'Controlada com medicamento')
    markup = _set_select(markup, 'gengiva_sangra', 'Durante a higiene')
    markup = _set_select(markup, 'fio_dental', 'Às vezes')
    markup = _set_input_by_name(markup, 'ultimo_tratamento_dentario', 'Há aproximadamente 1 ano.')
    markup = _set_input_by_name(markup, 'dor_dentes_gengiva', 'Sensibilidade ao frio no elemento 16.')
    markup = _set_input_by_name(markup, 'range_dentes', 'Nega apertamento ou bruxismo.')
    markup = _set_input_by_name(markup, 'antecedentes_familiares', 'Hipertensão — relato fictício.')
    markup = _set_radio(markup, 'exercicios_fisicos', 'Sim')
    return _set_input_by_name(markup, 'exercicios_fisicos_frequencia', 'Caminhada, 3 vezes por semana.')


def _prepare_proxy(markup):
    proxy_box = """
    <div class="training-proxy-box">
      <label><span class="training-check">✓</span> Paciente não alfabetizado</label>
      <p>Declaração registrada: li em voz alta, expliquei este documento em linguagem
      acessível, esclareci dúvidas e o paciente manifestou consentimento livre e informado.</p>
      <div class="training-proxy-fields">
        <div><b>Usuário do CD responsável</b><span>treino.clinico</span></div>
        <div><b>Senha do CD responsável</b><span>••••••••••••</span></div>
      </div>
    </div>
    """
    pattern = r'(<p[^>]*>\s*"Declaro para fins de direito.*?</p>)'
    return re.sub(pattern, rf'\1{proxy_box}', markup, count=1, flags=re.S)


BASE_FORM_CSS = """
.content-area { padding:.5rem 1rem !important; }
.document-container { max-width:1100px !important; margin:.5rem auto !important; padding:1.2rem 2rem !important; }
.document-container > div:first-child { display:none !important; }
.document-header { margin-bottom:1rem !important; }
.document-header h1 { font-size:1.25rem !important; }
.document-header h2 { font-size:1.05rem !important; }
.document-container form > * { display:none !important; }
"""


def capture_training_screens():
    clinical = _authenticated_session('treino.clinico', '198.51.100.54')
    response = clinical.get(f'{TRAINING_BASE_URL}/anamnesis/form/4', timeout=15)
    response.raise_for_status()
    form = _prepare_form(response.text)

    start_css = BASE_FORM_CSS + """
    .document-container form > :nth-child(2), .document-container form > :nth-child(3),
    .document-container form > :nth-child(4) { display:block !important; }
    .document-container form textarea { min-height:95px !important; }
    """
    _render_screen(form, SCREENSHOTS['start'], start_css)

    medical_css = BASE_FORM_CSS + """
    .document-container form > :nth-child(5), .document-container form > :nth-child(6) { display:block !important; }
    .document-container form > :nth-child(6) { max-height:560px !important; overflow:hidden !important; gap:2rem !important; }
    .document-container form > :nth-child(6) > div > div { margin-bottom:.6rem !important; padding-bottom:.45rem !important; }
    """
    _render_screen(form, SCREENSHOTS['medical'], medical_css)

    dental_css = BASE_FORM_CSS + """
    .document-container form > :nth-child(7), .document-container form > :nth-child(8),
    .document-container form > :nth-child(9), .document-container form > :nth-child(10) { display:block !important; }
    .document-container form > :nth-child(9) { margin-top:1.4rem !important; }
    .document-container form > :nth-child(8), .document-container form > :nth-child(10) { gap:2rem !important; }
    """
    _render_screen(form, SCREENSHOTS['dental'], dental_css)

    signature_css = BASE_FORM_CSS + """
    .document-container form > :nth-child(11), .document-container form > :nth-child(12) { display:block !important; }
    .document-container form > :nth-child(11) { margin-top:0 !important; }
    .document-container form > :nth-child(12) { padding:1.1rem !important; }
    .document-container form > :nth-child(12) > p { margin-bottom:1rem !important; }
    .document-container form > :nth-child(12) > div { gap:.7rem !important; }
    .training-signature { width:500px; height:180px; background:#fff; }
    .training-signature svg { width:100%; height:100%; }
    """
    _render_screen(_signature_markup(form), SCREENSHOTS['canvas'], signature_css)

    proxy_css = BASE_FORM_CSS + """
    .document-container form > :nth-child(11), .document-container form > :nth-child(12) { display:block !important; }
    .document-container form > :nth-child(11) { margin-top:0 !important; }
    .document-container form > :nth-child(12) { padding:1rem !important; }
    .document-container form > :nth-child(12) > p { margin-bottom:.8rem !important; }
    .document-container form > :nth-child(12) > div { gap:.7rem !important; }
    .document-container form > :nth-child(12) > div { display:none !important; }
    .document-container form > :nth-child(12) > .training-proxy-box {
      display:block !important; width:82%; margin:0 auto; padding:1rem 1.2rem;
      background:#fff; border:1px solid #d9e2ef; border-radius:10px; text-align:left;
    }
    .training-proxy-box label { font-weight:800; font-size:1rem; }
    .training-check {
      display:inline-block; width:20px; height:20px; margin-right:.5rem;
      background:#0d47a1; color:#fff; text-align:center; line-height:20px; border-radius:3px;
    }
    .training-proxy-box p { margin:.7rem 0; font-weight:700; font-size:.88rem; }
    .training-proxy-fields { display:grid !important; grid-template-columns:1fr 1fr; gap:1rem; }
    .training-proxy-fields div { display:block !important; }
    .training-proxy-fields b { display:block; margin-bottom:.3rem; font-size:.82rem; }
    .training-proxy-fields span {
      display:block; padding:.65rem .8rem; border:1px solid #d9e2ef;
      border-radius:8px; background:#f8fafc;
    }
    """
    _render_screen(_prepare_proxy(form), SCREENSHOTS['proxy'], proxy_css)

    completed = clinical.get(f'{TRAINING_BASE_URL}/anamnesis/view/1', timeout=15)
    completed.raise_for_status()
    result_css = """
    .content-area { padding:.5rem 1rem !important; }
    .document-container { max-width:1100px !important; margin:.5rem auto !important; padding:1.2rem 2rem !important; }
    .document-container > div:first-child { display:none !important; }
    .document-header { margin-bottom:1rem !important; }
    .document-header h1 { font-size:1.25rem !important; }
    .document-header h2 { font-size:1rem !important; }
    .card { margin-bottom:1rem !important; padding:1rem !important; }
    .anamnese-content { gap:1rem !important; max-height:500px !important; overflow:hidden !important; }
    .anamnese-content section { margin:0 !important; }
    """
    _render_screen(completed.text, SCREENSHOTS['result'], result_css)


def image_uri(path):
    return path.resolve().as_uri()


def _approved_css():
    source = APPROVED_HTML.read_text(encoding='utf-8')
    match = re.search(r'<style>(.*?)</style>', source, re.S)
    if not match:
        raise RuntimeError('CSS do modelo aprovado não encontrado.')
    return match.group(1).replace('Manual 01', 'Manual 07')


def build_manual_html():
    logo = image_uri(LOGO_PATH)
    images = {key: image_uri(path) for key, path in SCREENSHOTS.items()}
    css = _approved_css() + """
    .screen-short img { height:55mm; object-fit:cover; object-position:top; }
    .screen-pair { display:grid; grid-template-columns:1fr 1fr; gap:4mm; margin:3mm 0 4mm; }
    .screen-pair .screen { margin:0; }
    .screen-pair .screen img { height:43mm; object-fit:cover; object-position:top; }
    .screen-pair .screen-bar { font-size:6.6pt; }
    """
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Manual 07 — Anamnese</title><style>{css}</style></head><body>
<section class="cover"><div class="cover-logo"><img src="{logo}" alt="Sorriso da Gente"></div><div class="cover-kicker">Manual de operação • 07</div><h1>Anamnese</h1><div class="cover-subtitle">Registre riscos médicos, histórico odontológico e hábitos com clareza, revisão e evidência de assinatura.</div><div class="cover-meta"><div><strong>Público</strong>Clínicos</div><div><strong>Versão</strong>4.0.0-rc.1</div><div><strong>Revisão</strong>22 de junho de 2026</div></div></section>

<section class="page"><header class="page-header"><div><img src="{logo}"></div><div class="page-label">Manual 07 • Anamnese</div></header><h2>Antes de começar</h2><p class="lead">A Anamnese reúne informações que orientam decisões e alertas de segurança durante todo o cuidado odontológico.</p>
<div class="flow"><div class="flow-step"><div class="flow-number">1</div><strong>Entrevistar</strong><span>Ouça paciente ou responsável.</span></div><div class="flow-step"><div class="flow-number">2</div><strong>Detalhar</strong><span>Explique respostas positivas.</span></div><div class="flow-step"><div class="flow-number">3</div><strong>Revisar</strong><span>Confirme todas as respostas.</span></div><div class="flow-step"><div class="flow-number">4</div><strong>Assinar</strong><span>Em tela ou a rogo.</span></div></div>
<div class="check-grid"><div class="check-card"><strong>TCLE assinado</strong><span>É pré-requisito para abrir o fluxo clínico.</span></div><div class="check-card"><strong>Entrevista direta</strong><span>Não presuma respostas clínicas.</span></div><div class="check-card"><strong>Alergias e medicamentos</strong><span>Confirme nomes e detalhes relatados.</span></div><div class="check-card"><strong>Atualização contínua</strong><span>Revise quando a condição clínica mudar.</span></div></div>
<div class="warning"><strong>Informação positiva exige contexto</strong>Use o campo explicativo para registrar doença, medicamento, alergia, cirurgia ou hospitalização relatada.</div>
<table class="mini-table"><tr><th>Etapa</th><th>Conteúdo</th></tr><tr><td>Saúde geral</td><td>Doenças, tratamentos, medicamentos, alergias e condições sistêmicas.</td></tr><tr><td>Odontologia</td><td>Dor, anestesia, gengiva, higiene e hábitos parafuncionais.</td></tr><tr><td>Hábitos</td><td>Tabagismo, álcool, exercícios e antecedentes familiares.</td></tr></table></section>

<section class="page"><header class="page-header"><div><img src="{logo}"></div><div class="page-label">Manual 07 • Queixa e história</div></header><div class="step-banner"><div class="step-badge">1</div><div class="step-title"><h2>Iniciar a entrevista</h2><p>Na aba Anamnese, clique em Nova Anamnese e registre o motivo da procura.</p></div></div>
<div class="screen screen-short"><div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Paciente fictício • respostas não gravadas</div><img src="{images['start']}"></div>
<div class="columns"><div><div class="instruction"><strong>Queixa principal</strong><p>Registre de forma curta o motivo apresentado pelo paciente.</p></div><div class="instruction"><strong>História atual</strong><p>Descreva início, evolução, duração e fatores associados.</p></div></div><div class="tip"><strong>Texto objetivo</strong>Registre o relato clínico sem julgamentos ou informações irrelevantes.</div></div></section>

<section class="page"><header class="page-header"><div><img src="{logo}"></div><div class="page-label">Manual 07 • Segurança e histórico</div></header><div class="step-banner"><div class="step-badge">2</div><div class="step-title"><h2>Completar os riscos e hábitos</h2><p>Percorra saúde geral, histórico odontológico e antecedentes.</p></div></div>
<div class="screen-pair"><div class="screen"><div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Alergia e medicamento</div><img src="{images['medical']}"></div><div class="screen"><div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Odontologia e hábitos</div><img src="{images['dental']}"></div></div>
<div class="columns"><div><div class="instruction"><strong>Alergias e medicamentos</strong><p>Registre substância, nome, dose quando conhecida e contexto relatado.</p></div><div class="instruction"><strong>Histórico e hábitos</strong><p>Complete dor, anestesia, higiene, fumo, álcool e antecedentes familiares.</p></div></div><div class="warning"><strong>Não deixe lacunas</strong>Detalhe respostas positivas e revise em voz alta antes da assinatura.</div></div></section>

<section class="page"><header class="page-header"><div><img src="{logo}"></div><div class="page-label">Manual 07 • Assinaturas</div></header><div class="step-banner"><div class="step-badge">3</div><div class="step-title"><h2>Assinar e finalizar</h2><p>Escolha o modo adequado somente após a revisão das respostas.</p></div></div>
<div class="screen-pair"><div class="screen"><div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Assinatura em tela • ilustrativa</div><img src="{images['canvas']}"></div><div class="screen"><div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> A rogo • senha protegida</div><img src="{images['proxy']}"></div></div>
<div class="columns"><div><div class="instruction"><strong>Paciente alfabetizado</strong><p>Solicite a assinatura no quadro e use Limpar se precisar repetir.</p></div><div class="instruction"><strong>Paciente não alfabetizado</strong><p>Leia e explique; obtenha consentimento verbal e autentique com as credenciais do CD.</p></div></div><div class="warning"><strong>A rogo não é conveniência</strong>É exclusiva para paciente não alfabetizado. Não são exigidas testemunhas.</div></div></section>

<section class="page"><header class="page-header"><div><img src="{logo}"></div><div class="page-label">Manual 07 • Consulta e atualização</div></header><div class="step-banner"><div class="step-badge">4</div><div class="step-title"><h2>Consultar a ficha concluída</h2><p>A Anamnese fica disponível no prontuário para orientar o cuidado.</p></div></div>
<div class="screen screen-short"><div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Ficha fictícia previamente registrada</div><img src="{images['result']}"></div>
<div class="columns"><div><div class="instruction"><strong>Consulte antes da conduta</strong><p>Verifique alergias, medicamentos e riscos sistêmicos relevantes.</p></div><div class="instruction"><strong>Atualize quando necessário</strong><p>Mudanças clínicas exigem revisão, nova confirmação e nova evidência de assinatura.</p></div></div><div class="success"><strong>Resultado esperado</strong>Ficha completa, assinada e disponível para apoiar os atos clínicos subsequentes.</div></div>
<div class="closing"><h3>Anamnese concluída</h3><p>Com os riscos registrados, o fluxo segue para o <b>Plano de Tratamento e Evolução</b>.</p></div></section>
</body></html>"""


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
