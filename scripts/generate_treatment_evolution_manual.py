#!/usr/bin/env python3
"""Gera capturas e o PDF institucional do Manual 08."""

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


OUTPUT_PATH = MANUALS_DIR / '08_plano_tratamento_e_evolucao_v1.0.pdf'
HTML_SOURCE_PATH = MANUALS_DIR / '08_plano_tratamento_e_evolucao_v1.0.html'
SCREENSHOTS = {
    'plan': CAPTURES_DIR / '08_plano_01_novo_procedimento.png',
    'validation': CAPTURES_DIR / '08_plano_02_validacao_procedimento.png',
    'evolution': CAPTURES_DIR / '08_plano_03_nova_evolucao.png',
    'confirmations': CAPTURES_DIR / '08_plano_04_tres_confirmacoes.png',
    'timeline': CAPTURES_DIR / '08_plano_05_linha_do_tempo.png',
}


def _select(markup, name, value):
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


def _inject_tab(page, tab_name, partial):
    pattern = rf'(<div\b[^>]*\bid="{re.escape(tab_name)}"[^>]*>)(.*?)(</div>)'
    return re.sub(pattern, rf'\1{partial}\3', page, count=1, flags=re.S)


def _show_sign_modal(markup, title='Validação do Dentista Responsável'):
    markup = markup.replace('id="signModal" class="modal"', 'id="signModal" class="modal" style="display:flex;"', 1)
    markup = re.sub(
        r'(<div id="signModal".*?<h3\b[^>]*>)(.*?)(</h3>)',
        rf'\1{title}\3',
        markup,
        count=1,
        flags=re.S,
    )
    markup = _set_input_by_name(markup, 'validator_username', 'treino.clinico')
    return _set_input_by_name(markup, 'validator_password', '••••••••••••')


def _prepare_plan(partial):
    partial = _set_input_by_name(partial, 'dente', '16')
    partial = _select(partial, 'especialidade_sigtap', 'atencao_primaria')
    partial = _select(partial, 'sigtap_code', '0307010040')
    return _set_input_by_name(
        partial,
        'descricao',
        'Restauração de dente permanente posterior — exemplo fictício.',
    )


def _prepare_evolution(partial):
    partial = _set_input_by_name(partial, 'data', '2026-06-22')
    return _set_textarea(
        partial,
        'observacoes',
        'Realizada restauração no elemento 16, sem intercorrências. '
        'Orientações de higiene reforçadas — exemplo fictício.',
    )


BASE_PAGE_CSS = """
.content-area { padding:.5rem 1rem !important; }
.content-area > .animate-fade > :not(.tabs-container) { display:none !important; }
.tabs-container { margin:0 !important; }
.tabs-header { display:none !important; }
.tab-content { display:none !important; }
.tab-content.training-active { display:block !important; }
.tab-content.training-active > .card { margin:.5rem 0 !important; padding:1.1rem !important; }
.modal { background:rgba(15,23,42,.58) !important; z-index:5000 !important; }
"""


def capture_training_screens():
    clinical = _authenticated_session('treino.clinico', '198.51.100.56')

    page5 = clinical.get(f'{TRAINING_BASE_URL}/patients/view/5', timeout=15)
    page5.raise_for_status()
    treatment5 = clinical.get(f'{TRAINING_BASE_URL}/patients/view/5/tab/tab-tratamento', timeout=15)
    treatment5.raise_for_status()
    markup = _inject_tab(page5.text, 'tab-tratamento', _prepare_plan(treatment5.text))
    markup = markup.replace('id="tab-tratamento" class="tab-content"', 'id="tab-tratamento" class="tab-content training-active"', 1)
    plan_css = BASE_PAGE_CSS + """
    #tab-tratamento > .card { max-height:700px !important; overflow:hidden !important; }
    #tab-tratamento .table-container { margin-top:1rem !important; }
    """
    _render_screen(markup, SCREENSHOTS['plan'], plan_css)

    page6 = clinical.get(f'{TRAINING_BASE_URL}/patients/view/6', timeout=15)
    page6.raise_for_status()
    treatment6 = clinical.get(f'{TRAINING_BASE_URL}/patients/view/6/tab/tab-tratamento', timeout=15)
    treatment6.raise_for_status()
    validation = _inject_tab(page6.text, 'tab-tratamento', treatment6.text)
    validation = validation.replace('id="tab-tratamento" class="tab-content"', 'id="tab-tratamento" class="tab-content training-active"', 1)
    validation = _show_sign_modal(validation)
    validation_css = BASE_PAGE_CSS + """
    #tab-tratamento > .card { max-height:700px !important; overflow:hidden !important; }
    #signModal .modal-content { padding:2rem !important; }
    """
    _render_screen(validation, SCREENSHOTS['validation'], validation_css)

    attendance5 = clinical.get(f'{TRAINING_BASE_URL}/patients/view/5/tab/tab-atendimento', timeout=15)
    attendance5.raise_for_status()
    evolution = _inject_tab(page5.text, 'tab-atendimento', _prepare_evolution(attendance5.text))
    evolution = evolution.replace('id="tab-atendimento" class="tab-content"', 'id="tab-atendimento" class="tab-content training-active"', 1)
    evolution_css = BASE_PAGE_CSS + """
    #tab-atendimento > .card { max-height:700px !important; overflow:hidden !important; }
    #tab-atendimento textarea { min-height:115px !important; }
    """
    _render_screen(evolution, SCREENSHOTS['evolution'], evolution_css)

    attendance6 = clinical.get(f'{TRAINING_BASE_URL}/patients/view/6/tab/tab-atendimento', timeout=15)
    attendance6.raise_for_status()
    confirmations = _inject_tab(page6.text, 'tab-atendimento', attendance6.text)
    confirmations = confirmations.replace('id="tab-atendimento" class="tab-content"', 'id="tab-atendimento" class="tab-content training-active"', 1)
    confirmations_css = BASE_PAGE_CSS + """
    #tab-atendimento > .card > div:nth-of-type(-n+3) { display:none !important; }
    #tab-atendimento > .card { padding-top:1.5rem !important; }
    #tab-atendimento .table-container { margin-top:1rem !important; }
    """
    _render_screen(confirmations, SCREENSHOTS['confirmations'], confirmations_css)

    timeline6 = clinical.get(f'{TRAINING_BASE_URL}/patients/view/6/tab/tab-linha-tempo', timeout=15)
    timeline6.raise_for_status()
    timeline = _inject_tab(page6.text, 'tab-linha-tempo', timeline6.text)
    timeline = timeline.replace('id="tab-linha-tempo" class="tab-content"', 'id="tab-linha-tempo" class="tab-content training-active"', 1)
    timeline_css = BASE_PAGE_CSS + """
    #tab-linha-tempo { max-height:740px !important; overflow:hidden !important; padding:1rem !important; }
    #tab-linha-tempo .trace-timeline { gap:.55rem !important; }
    #tab-linha-tempo .trace-card { padding:.65rem .8rem !important; }
    """
    _render_screen(timeline, SCREENSHOTS['timeline'], timeline_css)


def image_uri(path):
    return path.resolve().as_uri()


def _approved_css():
    source = APPROVED_HTML.read_text(encoding='utf-8')
    match = re.search(r'<style>(.*?)</style>', source, re.S)
    if not match:
        raise RuntimeError('CSS do modelo aprovado não encontrado.')
    return match.group(1).replace('Manual 01', 'Manual 08')


def build_manual_html():
    logo = image_uri(LOGO_PATH)
    images = {key: image_uri(path) for key, path in SCREENSHOTS.items()}
    css = _approved_css() + """
    .screen-short img { height:54mm; object-fit:cover; object-position:top; }
    .screen-pair { display:grid; grid-template-columns:1fr 1fr; gap:4mm; margin:3mm 0 4mm; }
    .screen-pair .screen { margin:0; }
    .screen-pair .screen img { height:42mm; object-fit:cover; object-position:top; }
    .screen-pair .screen-bar { font-size:6.5pt; }
    """
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Manual 08 — Plano de Tratamento e Evolução</title><style>{css}</style></head><body>
<section class="cover"><div class="cover-logo"><img src="{logo}"></div><div class="cover-kicker">Manual de operação • 08</div><h1>Plano de Tratamento e Evolução</h1><div class="cover-subtitle">Planeje procedimentos, associe o código SUS/SIGTAP e registre a execução com confirmações rastreáveis.</div><div class="cover-meta"><div><strong>Público</strong>Clínicos</div><div><strong>Versão</strong>4.0.0-rc.1</div><div><strong>Revisão</strong>22 de junho de 2026</div></div></section>

<section class="page"><header class="page-header"><div><img src="{logo}"></div><div class="page-label">Manual 08 • Plano e evolução</div></header><h2>Antes de começar</h2><p class="lead">O plano descreve o cuidado proposto; a evolução registra o que efetivamente ocorreu em cada atendimento.</p>
<div class="flow"><div class="flow-step"><div class="flow-number">1</div><strong>Planejar</strong><span>Dente, especialidade e SIGTAP.</span></div><div class="flow-step"><div class="flow-number">2</div><strong>Validar</strong><span>Responsável confirma a conclusão.</span></div><div class="flow-step"><div class="flow-number">3</div><strong>Evoluir</strong><span>Registre conduta e resultado.</span></div><div class="flow-step"><div class="flow-number">4</div><strong>Confirmar</strong><span>Executor, paciente e dentista.</span></div></div>
<div class="check-grid"><div class="check-card"><strong>TCLE e Anamnese</strong><span>Confira os pré-requisitos clínicos.</span></div><div class="check-card"><strong>Dente correto</strong><span>Valide elemento e indicação.</span></div><div class="check-card"><strong>Código compatível</strong><span>Selecione especialidade antes do SIGTAP.</span></div><div class="check-card"><strong>Credenciais pessoais</strong><span>Nunca compartilhe usuário ou senha.</span></div></div>
<div class="warning"><strong>Planejado não significa realizado</strong>O item permanece pendente até a validação profissional. A evolução deve refletir o atendimento efetivamente executado.</div>
<table class="mini-table"><tr><th>Registro</th><th>Finalidade</th></tr><tr><td>Plano</td><td>Define procedimento proposto, dente, especialidade e código.</td></tr><tr><td>Evolução</td><td>Documenta conduta, intercorrências, orientações e resultado.</td></tr><tr><td>Confirmações</td><td>Identificam executor, paciente e dentista responsável.</td></tr></table></section>

<section class="page"><header class="page-header"><div><img src="{logo}"></div><div class="page-label">Manual 08 • Planejamento</div></header><div class="step-banner"><div class="step-badge">1</div><div class="step-title"><h2>Criar o plano de tratamento</h2><p>Preencha os campos na ordem e revise antes de adicionar.</p></div></div>
<div class="screen screen-short"><div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Exemplo fictício • procedimento não gravado</div><img src="{images['plan']}"></div>
<div class="password-rules"><div class="rule"><b>Dente</b><span>elemento ou região</span></div><div class="rule"><b>Especialidade</b><span>filtra o catálogo</span></div><div class="rule"><b>SIGTAP</b><span>código correspondente</span></div></div>
<div class="tip"><strong>Enquanto estiver pendente</strong>É possível editar dados ou excluir um lançamento indevido antes da conclusão.</div></section>

<section class="page"><header class="page-header"><div><img src="{logo}"></div><div class="page-label">Manual 08 • Validação</div></header><div class="step-banner"><div class="step-badge">2</div><div class="step-title"><h2>Validar o procedimento</h2><p>Após a execução, clique em Assinar e confirme as credenciais do responsável.</p></div></div>
<div class="screen screen-short"><div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Validação ilustrativa • senha protegida</div><img src="{images['validation']}"></div>
<div class="columns"><div><div class="instruction"><strong>Confirme antes de assinar</strong><p>Revise dente, descrição e código SUS/SIGTAP.</p></div><div class="instruction"><strong>Importação automática</strong><p>O procedimento concluído é levado para a Evolução Clínica.</p></div></div><div class="warning"><strong>Assinatura profissional</strong>Use somente suas próprias credenciais e mantenha a senha oculta durante treinamentos.</div></div></section>

<section class="page"><header class="page-header"><div><img src="{logo}"></div><div class="page-label">Manual 08 • Evolução clínica</div></header><div class="step-banner"><div class="step-badge">3</div><div class="step-title"><h2>Registrar a evolução</h2><p>Descreva de forma suficiente o atendimento efetivamente realizado.</p></div></div>
<div class="screen screen-short"><div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Evolução fictícia • registro não salvo</div><img src="{images['evolution']}"></div>
<div class="columns"><div><div class="instruction"><strong>Conteúdo mínimo</strong><p>Conduta, elemento, intercorrências, orientações e resultado.</p></div><div class="instruction"><strong>Linguagem clínica</strong><p>Seja objetivo e permita a continuidade segura do cuidado.</p></div></div><div class="tip"><strong>Data e autoria</strong>Confira a data do atendimento e quem está registrando a evolução.</div></div></section>

<section class="page"><header class="page-header"><div><img src="{logo}"></div><div class="page-label">Manual 08 • Confirmações e rastreabilidade</div></header><div class="step-banner"><div class="step-badge">4</div><div class="step-title"><h2>Concluir e conferir</h2><p>A evolução exige três confirmações e permanece destacada enquanto houver pendência.</p></div></div>
<div class="screen-pair"><div class="screen"><div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Executor, paciente e responsável</div><img src="{images['confirmations']}"></div><div class="screen"><div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Linha do Tempo</div><img src="{images['timeline']}"></div></div>
<table class="mini-table"><tr><th>Confirmação</th><th>Como é registrada</th></tr><tr><td>Executor</td><td>Profissional autentica sua participação com credenciais.</td></tr><tr><td>Paciente</td><td>Assina em tela ou a rogo quando não alfabetizado.</td></tr><tr><td>Responsável</td><td>Dentista valida clinicamente com suas credenciais.</td></tr></table>
<div class="columns"><div class="success"><strong>Resultado esperado</strong>Procedimento concluído, evolução completa e confirmações vinculadas.</div><div class="tip"><strong>Rastreabilidade</strong>Consulte os eventos na Linha do Tempo do paciente.</div></div>
<div class="closing"><h3>Ciclo clínico documentado</h3><p>Com plano e evolução registrados, o acompanhamento também fica disponível para a <b>Central de Comando</b>.</p></div></section>
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
