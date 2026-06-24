#!/usr/bin/env python3
"""Gera a referência clínica de especialidades e procedimentos SUS/SIGTAP."""

from datetime import date
from html import escape
from pathlib import Path
import sys

from weasyprint import HTML


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
OUTPUT_PATH = PROJECT_ROOT / 'docs' / 'referencia_clinica_especialidades_procedimentos_sigtap.pdf'
LOGO_PATH = PROJECT_ROOT / 'static' / 'logo_sorriso_horizontal.png'


def _format_date(value):
    months = (
        'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
        'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
    )
    return f'{value.day} de {months[value.month - 1]} de {value.year}'


def _specialty_summary(groups):
    cards = []
    for index, group in enumerate(groups, start=1):
        cards.append(
            f"""
            <div class="summary-card">
              <span class="summary-number">{index:02d}</span>
              <div>
                <strong>{escape(group['label'])}</strong>
                <span>{len(group['procedures'])} procedimento(s)</span>
              </div>
            </div>
            """
        )
    return ''.join(cards)


def _specialty_pages(groups, format_sigtap_code):
    pages = []
    for index, group in enumerate(groups, start=1):
        procedures = group['procedures']
        chunks = [procedures[offset:offset + 19] for offset in range(0, len(procedures), 19)]
        for chunk_index, chunk in enumerate(chunks):
            first_sequence = chunk_index * 19 + 1
            rows = []
            for sequence, (code, name) in enumerate(chunk, start=first_sequence):
                rows.append(
                    f"""
                    <tr>
                      <td class="sequence">{sequence:02d}</td>
                      <td class="code">{escape(format_sigtap_code(code))}</td>
                      <td class="procedure">{escape(name)}</td>
                    </tr>
                    """
                )

            continuation = ' • continuação' if chunk_index else ''
            pages.append(
                f"""
                <section class="specialty-page">
                  <header class="page-header">
                    <div><img src="{LOGO_PATH.resolve().as_uri()}" alt="Sorriso da Gente"></div>
                    <div class="page-label">Referência clínica • SUS/SIGTAP</div>
                  </header>

                  <div class="specialty-heading">
                    <div class="specialty-index">{index:02d}</div>
                    <div>
                      <div class="eyebrow">Especialidade{continuation}</div>
                      <h2>{escape(group['label'])}</h2>
                      <p>{len(group['procedures'])} procedimento(s) disponíveis no Plano de Tratamento.</p>
                    </div>
                  </div>

                  <table>
                    <thead>
                      <tr>
                        <th class="sequence">Nº</th>
                        <th class="code">Código oficial</th>
                        <th>Procedimento</th>
                      </tr>
                    </thead>
                    <tbody>{''.join(rows)}</tbody>
                  </table>
                </section>
                """
            )
    return ''.join(pages)


def build_html():
    from services.sigtap_service import (
        DEFAULT_COMPETENCE,
        SIGTAP_SPECIALTY_GROUPS,
        format_sigtap_code,
    )

    total_procedures = sum(len(group['procedures']) for group in SIGTAP_SPECIALTY_GROUPS)
    generated_at = _format_date(date.today())
    logo_uri = LOGO_PATH.resolve().as_uri()

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>Referência Clínica — Especialidades e Procedimentos SUS/SIGTAP</title>
  <style>
    @page {{
      size: A4 portrait;
      margin: 14mm 14mm 17mm;
      @bottom-left {{
        content: "Gestão Saúde Oral • Referência clínica SUS/SIGTAP";
        font-family: Arial, sans-serif;
        font-size: 7.4pt;
        color: #64748b;
      }}
      @bottom-right {{
        content: counter(page) " / " counter(pages);
        font-family: Arial, sans-serif;
        font-size: 7.4pt;
        color: #64748b;
      }}
    }}
    @page cover {{ margin: 0; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: #172033;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 9.2pt;
      line-height: 1.42;
    }}
    .cover {{
      page: cover;
      height: 297mm;
      position: relative;
      overflow: hidden;
      padding: 23mm 20mm;
      color: white;
      background: linear-gradient(145deg, #0b367c 0%, #0d47a1 58%, #0879bd 100%);
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
      padding: 10px 18px;
      background: white;
      border-radius: 16px;
      box-shadow: 0 16px 38px rgba(0,0,0,.18);
    }}
    .cover-logo img {{ display: block; width: 61mm; }}
    .cover-kicker {{
      margin-top: 34mm;
      color: #f7941e;
      font-size: 10pt;
      font-weight: 800;
      letter-spacing: .18em;
      text-transform: uppercase;
    }}
    .cover h1 {{
      max-width: 155mm;
      margin: 6mm 0 4mm;
      font-size: 31pt;
      line-height: 1.03;
      letter-spacing: -.035em;
    }}
    .cover-subtitle {{
      max-width: 137mm;
      color: #dbeafe;
      font-size: 12.5pt;
      line-height: 1.45;
    }}
    .cover-stats {{
      display: table;
      width: 135mm;
      margin-top: 14mm;
      table-layout: fixed;
    }}
    .cover-stat {{
      display: table-cell;
      padding: 5mm;
      border-right: 3mm solid transparent;
      background: rgba(255,255,255,.11);
      background-clip: padding-box;
      border-radius: 10px;
    }}
    .cover-stat strong {{ display: block; font-size: 20pt; color: white; }}
    .cover-stat span {{ color: #dbeafe; font-size: 8.5pt; }}
    .cover-meta {{
      position: absolute;
      left: 20mm;
      right: 20mm;
      bottom: 20mm;
      display: table;
      width: calc(100% - 40mm);
      padding-top: 7mm;
      border-top: 1px solid rgba(255,255,255,.3);
      color: #dbeafe;
      font-size: 8.7pt;
    }}
    .cover-meta > div {{ display: table-cell; width: 33.333%; }}
    .cover-meta strong {{ display: block; margin-bottom: 1mm; color: white; }}
    .intro-page, .specialty-page {{ page-break-before: always; }}
    .page-header {{
      display: table;
      width: 100%;
      margin-bottom: 7mm;
      padding-bottom: 4mm;
      border-bottom: 2px solid #dbe7f6;
    }}
    .page-header > div {{ display: table-cell; vertical-align: middle; }}
    .page-header img {{ width: 43mm; }}
    .page-label {{
      text-align: right;
      color: #0d47a1;
      font-size: 8pt;
      font-weight: 800;
      letter-spacing: .08em;
      text-transform: uppercase;
    }}
    h2 {{
      margin: 0;
      color: #0d47a1;
      font-size: 21pt;
      line-height: 1.1;
      letter-spacing: -.025em;
    }}
    .lead {{
      margin: 0 0 6mm;
      color: #526279;
      font-size: 11pt;
      line-height: 1.55;
    }}
    .notice {{
      margin: 5mm 0 7mm;
      padding: 4mm 5mm;
      border: 1px solid #fed7a0;
      border-radius: 10px;
      background: #fff7e8;
      color: #7c3f00;
    }}
    .notice strong {{ display: block; margin-bottom: 1mm; color: #a65300; }}
    .summary-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 3.5mm;
    }}
    .summary-card {{
      display: table;
      width: 100%;
      min-height: 22mm;
      padding: 3.5mm;
      border: 1px solid #dbe7f6;
      border-radius: 10px;
      background: #f8fbff;
      page-break-inside: avoid;
    }}
    .summary-card > * {{ display: table-cell; vertical-align: middle; }}
    .summary-number {{
      width: 13mm;
      color: #f7941e;
      font-size: 16pt;
      font-weight: 800;
    }}
    .summary-card strong {{ display: block; color: #0d47a1; font-size: 9.5pt; }}
    .summary-card span {{ display: block; margin-top: 1mm; color: #64748b; font-size: 8.2pt; }}
    .specialty-heading {{
      display: table;
      width: 100%;
      margin-bottom: 5mm;
      page-break-after: avoid;
    }}
    .specialty-heading > div {{ display: table-cell; vertical-align: middle; }}
    .specialty-index {{
      width: 18mm;
      height: 18mm;
      border-radius: 50%;
      background: #f7941e;
      color: white;
      text-align: center;
      font-size: 17pt;
      font-weight: 800;
      line-height: 18mm;
    }}
    .specialty-heading > div:last-child {{ padding-left: 4mm; }}
    .specialty-heading .eyebrow {{
      color: #64748b;
      font-size: 7.5pt;
      font-weight: 800;
      letter-spacing: .12em;
      text-transform: uppercase;
    }}
    .specialty-heading p {{ margin: 1mm 0 0; color: #64748b; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 8.6pt;
    }}
    thead {{ display: table-header-group; }}
    tr {{ page-break-inside: avoid; }}
    th {{
      padding: 3mm 2.5mm;
      background: #0d47a1;
      color: white;
      text-align: left;
      font-size: 7.6pt;
      letter-spacing: .04em;
      text-transform: uppercase;
    }}
    th:first-child {{ border-radius: 7px 0 0 0; }}
    th:last-child {{ border-radius: 0 7px 0 0; }}
    td {{
      padding: 2.6mm 2.5mm;
      border-bottom: 1px solid #dbe7f6;
      vertical-align: top;
    }}
    tbody tr:nth-child(even) td {{ background: #f7faff; }}
    .sequence {{ width: 12mm; text-align: center; color: #64748b; }}
    .code {{
      width: 38mm;
      white-space: nowrap;
      color: #0d47a1;
      font-family: "Courier New", monospace;
      font-size: 9pt;
      font-weight: 700;
    }}
    .procedure {{ color: #26364f; }}
  </style>
</head>
<body>
  <section class="cover">
    <div class="cover-logo"><img src="{logo_uri}" alt="Sorriso da Gente"></div>
    <div class="cover-kicker">Referência clínica institucional</div>
    <h1>Especialidades e Procedimentos SUS/SIGTAP</h1>
    <div class="cover-subtitle">
      Guia rápido para seleção de especialidades e códigos no Plano de Tratamento.
    </div>
    <div class="cover-stats">
      <div class="cover-stat"><strong>{len(SIGTAP_SPECIALTY_GROUPS)}</strong><span>especialidades</span></div>
      <div class="cover-stat"><strong>{total_procedures}</strong><span>procedimentos</span></div>
      <div class="cover-stat"><strong>{DEFAULT_COMPETENCE}</strong><span>competência configurada</span></div>
    </div>
    <div class="cover-meta">
      <div><strong>Público</strong>Clínicos</div>
      <div><strong>Aplicação</strong>Gestão Saúde Oral</div>
      <div><strong>Revisão</strong>{generated_at}</div>
    </div>
  </section>

  <section class="intro-page">
    <header class="page-header">
      <div><img src="{logo_uri}" alt="Sorriso da Gente"></div>
      <div class="page-label">Referência clínica • SUS/SIGTAP</div>
    </header>
    <h2>Como usar esta referência</h2>
    <p class="lead">
      Localize a especialidade, confira o procedimento e selecione no sistema o código
      correspondente. Os códigos estão apresentados com a máscara oficial do SIGTAP.
    </p>
    <div class="notice">
      <strong>Atenção à competência vigente</strong>
      Este material reproduz exclusivamente o catálogo configurado na aplicação para a
      competência {DEFAULT_COMPETENCE}. Antes de faturamento, exportação ou homologação,
      confirme regras, vigência e compatibilidade no SIGTAP oficial.
    </div>
    <div class="summary-grid">{_specialty_summary(SIGTAP_SPECIALTY_GROUPS)}</div>
  </section>

  {_specialty_pages(SIGTAP_SPECIALTY_GROUPS, format_sigtap_code)}
</body>
</html>
"""


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=build_html(), base_url=str(PROJECT_ROOT)).write_pdf(OUTPUT_PATH)
    print(OUTPUT_PATH)


if __name__ == '__main__':
    main()
