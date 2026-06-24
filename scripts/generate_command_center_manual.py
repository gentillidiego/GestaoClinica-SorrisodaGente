#!/usr/bin/env python3
"""Gera capturas e o PDF institucional do Manual 09 — Central de Comando."""

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
)


OUTPUT_PATH = MANUALS_DIR / '09_central_de_comando_v1.0.pdf'
HTML_SOURCE_PATH = MANUALS_DIR / '09_central_de_comando_v1.0.html'
SCREENSHOTS = {
    'overview': CAPTURES_DIR / '09_central_01_filtros_visao_geral.png',
    'indicators': CAPTURES_DIR / '09_central_02_indicadores_metas.png',
    'queue': CAPTURES_DIR / '09_central_03_fila_inteligente.png',
    'alerts': CAPTURES_DIR / '09_central_04_gargalos_alertas.png',
    'summary': CAPTURES_DIR / '09_central_05_resumo_diario.png',
}


# ---------------------------------------------------------------------------
# CSS de base para captura de tela da Central de Comando
# ---------------------------------------------------------------------------

BASE_PAGE_CSS = """
.content-area { padding:.5rem 1rem !important; }
.sidebar, .top-bar, .notification-bell { display:none !important; }
.main-content { margin-left:0 !important; padding-top:0 !important; }
.animate-fade { animation:none !important; }
"""


def _section_css(section_id):
    """Exibe apenas a seção indicada dentro da Central de Comando."""
    return BASE_PAGE_CSS + f"""
    .command-section {{ display:none !important; }}
    #{section_id} {{ display:block !important; }}
    """


# ---------------------------------------------------------------------------
# Captura de telas do ambiente de treinamento
# ---------------------------------------------------------------------------

def capture_training_screens():
    coord = _authenticated_session('treino.coordenacao', '198.51.100.60')

    # 1. Visão geral com filtros
    page = coord.get(f'{TRAINING_BASE_URL}/command-center', timeout=15)
    page.raise_for_status()
    overview_css = BASE_PAGE_CSS + """
    .command-header { margin-bottom:.5rem !important; }
    .filters-bar { margin-bottom:.5rem !important; }
    .kpi-grid { margin-top:0 !important; max-height:220px !important; overflow:hidden !important; }
    .command-section { display:none !important; }
    .kpi-grid, .filters-bar { display:block !important; }
    """
    _render_screen(page.text, SCREENSHOTS['overview'], overview_css)

    # 2. Cards de indicadores e metas
    indicators_css = BASE_PAGE_CSS + """
    .filters-bar { display:none !important; }
    .kpi-grid { margin:0 !important; }
    .goals-section { margin-top:.5rem !important; }
    .command-section:not(.goals-section):not(.kpi-section) { display:none !important; }
    """
    _render_screen(page.text, SCREENSHOTS['indicators'], indicators_css)

    # 3. Fila inteligente
    queue_css = BASE_PAGE_CSS + """
    .filters-bar, .kpi-grid, .goals-section { display:none !important; }
    .queue-section { display:block !important; max-height:480px !important; overflow:hidden !important; }
    .command-section:not(.queue-section) { display:none !important; }
    """
    _render_screen(page.text, SCREENSHOTS['queue'], queue_css)

    # 4. Gargalos e alertas
    alerts_css = BASE_PAGE_CSS + """
    .filters-bar, .kpi-grid, .goals-section, .queue-section { display:none !important; }
    .alerts-section, .bottleneck-section, .pending-section { display:block !important; }
    .command-section:not(.alerts-section):not(.bottleneck-section):not(.pending-section) { display:none !important; }
    """
    _render_screen(page.text, SCREENSHOTS['alerts'], alerts_css)

    # 5. Resumo diário — abre o endpoint de impressão
    summary_page = coord.get(f'{TRAINING_BASE_URL}/command-center/daily-summary', timeout=15)
    summary_page.raise_for_status()
    summary_css = """
    @media print { body { -webkit-print-color-adjust:exact; } }
    .no-print, .print-hide { display:none !important; }
    body { padding:1rem !important; }
    """
    _render_screen(summary_page.text, SCREENSHOTS['summary'], summary_css)


# ---------------------------------------------------------------------------
# Construção do HTML final
# ---------------------------------------------------------------------------

def image_uri(path):
    return path.resolve().as_uri()


def _approved_css():
    source = APPROVED_HTML.read_text(encoding='utf-8')
    match = re.search(r'<style>(.*?)</style>', source, re.S)
    if not match:
        raise RuntimeError('CSS do modelo aprovado não encontrado.')
    return match.group(1).replace('Manual 01', 'Manual 09')


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
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Manual 09 — Central de Comando</title><style>{css}</style></head><body>

<section class="cover"><div class="cover-logo"><img src="{logo}"></div><div class="cover-kicker">Manual de operação • 09</div><h1>Central de Comando</h1><div class="cover-subtitle">Monitore a operação em tempo real, interprete indicadores, priorize a fila e gere o resumo diário com agilidade.</div><div class="cover-meta"><div><strong>Público</strong>Coordenação</div><div><strong>Versão</strong>4.0.0-rc.1</div><div><strong>Revisão</strong>23 de junho de 2026</div></div></section>

<section class="page"><header class="page-header"><div><img src="{logo}"></div><div class="page-label">Manual 09 • Central de Comando</div></header><h2>Antes de começar</h2><p class="lead">A Central de Comando reúne a situação operacional em uma única tela e ajuda a coordenação a identificar prioridades, gargalos e pendências.</p>
<div class="flow"><div class="flow-step"><div class="flow-number">1</div><strong>Filtrar</strong><span>Período e recorte desejado.</span></div><div class="flow-step"><div class="flow-number">2</div><strong>Interpretar</strong><span>Indicadores, metas e fila.</span></div><div class="flow-step"><div class="flow-number">3</div><strong>Agir</strong><span>Alertas e pendências resolvidas.</span></div><div class="flow-step"><div class="flow-number">4</div><strong>Resumir</strong><span>Relatório diário ou CSV.</span></div></div>
<div class="check-grid"><div class="check-card"><strong>Perfil Coordenação</strong><span>Acesse com a conta de Coordenação ou gestão operacional equivalente.</span></div><div class="check-card"><strong>Período definido</strong><span>Escolha o intervalo antes de aplicar os filtros para obter dados precisos.</span></div><div class="check-card"><strong>Dados em tempo real</strong><span>Recarregue a página sempre que precisar atualizar os números exibidos.</span></div><div class="check-card"><strong>Valores estimados</strong><span>Economia e metas são referenciais internos; não os anuncie como homologados.</span></div></div>
<div class="tip"><strong>Este manual acompanha você do início ao fim</strong>Siga as quatro etapas na ordem. Cada seção descreve uma ação e o resultado esperado na tela.</div></section>

<section class="page"><header class="page-header"><div><img src="{logo}"></div><div class="page-label">Manual 09 • Filtros</div></header><div class="step-banner"><div class="step-badge">1</div><div class="step-title"><h2>Abrir e filtrar</h2><p>Defina o recorte antes de analisar os indicadores.</p></div></div>
<div class="screen screen-short"><div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Central de Comando • filtros aplicados — dados fictícios</div><img src="{images['overview']}"></div>
<div class="columns"><div><div class="instruction"><strong>Abrir a Central</strong><p>No menu lateral, clique em <b>Central de Comando</b>.</p></div><div class="instruction"><strong>Aplicar filtros</strong><p>Selecione município, especialidade, profissional, unidade e período. Clique em <b>Filtrar</b>.</p></div><div class="instruction"><strong>Voltar à visão geral</strong><p>Clique em <b>Limpar</b> para remover os filtros e exibir todos os dados.</p></div></div><div class="tip"><strong>Filtros combinados</strong>Quanto mais específica a combinação, mais preciso o recorte. Comece pelo período para orientar os demais campos.</div></div></section>

<section class="page"><header class="page-header"><div><img src="{logo}"></div><div class="page-label">Manual 09 • Indicadores e metas</div></header><div class="step-banner"><div class="step-badge">2</div><div class="step-title"><h2>Ler indicadores e metas</h2><p>Produção, fila, espera e condutas recomendadas em uma única visualização.</p></div></div>
<div class="screen screen-short"><div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Cards de indicadores e metas — dados fictícios</div><img src="{images['indicators']}"></div>
<table class="mini-table"><tr><th>Indicador</th><th>O que representa</th></tr><tr><td>Produção</td><td>Atendimentos realizados no período filtrado.</td></tr><tr><td>Fila</td><td>Pacientes aguardando agendamento ou retorno.</td></tr><tr><td>Espera média</td><td>Tempo médio entre triagem e atendimento.</td></tr><tr><td>Situação da agenda</td><td>Consultas confirmadas, pendentes e canceladas.</td></tr><tr><td>Meta</td><td>Valor atual comparado ao alvo; conduta exibida quando abaixo.</td></tr></table>
<div class="tip"><strong>Metas são referenciais internos</strong>Os valores são estimativas operacionais. Não os apresente como homologados pelo município ou pelo SUS.</div></section>

<section class="page"><header class="page-header"><div><img src="{logo}"></div><div class="page-label">Manual 09 • Fila e alertas</div></header><div class="step-banner"><div class="step-badge">3</div><div class="step-title"><h2>Interpretar a fila inteligente</h2><p>A pontuação apoia a decisão, mas não substitui a avaliação da equipe.</p></div></div>
<div class="screen screen-short"><div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Fila inteligente — pacientes fictícios</div><img src="{images['queue']}"></div>
<div class="columns"><div><div class="instruction"><strong>Critérios de prioridade</strong><p>Suspeita oncológica, dor aguda, idade, vulnerabilidade, faltas recorrentes, tratamento pendente e tempo de espera.</p></div><div class="instruction"><strong>Pacientes sem retorno</strong><p>Identifique casos com longa ausência e acione o fluxo de busca ativa da unidade.</p></div></div><div class="warning"><strong>Decisão clínica é da equipe</strong>A pontuação é um apoio à triagem. O agendamento final cabe à equipe de saúde.</div></div></section>

<section class="page"><header class="page-header"><div><img src="{logo}"></div><div class="page-label">Manual 09 • Resumo diário e resultados</div></header><div class="step-banner"><div class="step-badge">4</div><div class="step-title"><h2>Gargalos, alertas e resumo</h2><p>Aja sobre as pendências e registre o resumo operacional do dia.</p></div></div>
<div class="screen-pair"><div class="screen"><div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Gargalos e alertas — fictício</div><img src="{images['alerts']}"></div><div class="screen"><div class="screen-bar"><span class="screen-dot"></span><span class="screen-dot"></span><span class="screen-dot"></span> Resumo Diário — fictício</div><img src="{images['summary']}"></div></div>
<div class="columns"><div><div class="instruction"><strong>Gargalos e pendências</strong><p>Observe falta de estoque, materiais vencendo e assinaturas pendentes. Cada alerta deve ter um responsável designado.</p></div><div class="instruction"><strong>Resumo Diário</strong><p>Clique em <b>Resumo Diário</b> para a versão imprimível. Use <b>Exportar CSV</b> para planilha.</p></div></div><div class="success"><strong>Resultado esperado</strong>Coordenação capaz de identificar prioridades, interpretar indicadores e gerar o resumo operacional do período.</div></div>
<table class="mini-table"><tr><th>Se acontecer</th><th>O que fazer</th></tr><tr><td>Dados desatualizados</td><td>Recarregue a página para atualizar os números.</td></tr><tr><td>Filtro sem resultado</td><td>Verifique o período e a combinação de filtros.</td></tr><tr><td>Indicador inesperado</td><td>Confirme se há lançamentos pendentes ou em revisão.</td></tr><tr><td>Exportação vazia</td><td>Selecione um período com registros antes de exportar.</td></tr></table>
<div class="closing"><h3>Operação monitorada e documentada</h3><p>Com o resumo gerado, a coordenação mantém o controle do ciclo e orienta as ações para o próximo período.</p></div></section>

</body></html>"""


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

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
