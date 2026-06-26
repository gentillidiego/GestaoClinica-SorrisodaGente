#!/usr/bin/env python3
"""Converte os roteiros Markdown de treinamento em PDFs institucionais."""

import html
import re
import sys
from pathlib import Path

from weasyprint import HTML


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROTEIROS_DIR = PROJECT_ROOT / 'docs' / 'manuais_e_treinamentos' / 'roteiros'
LOGO_PATH = PROJECT_ROOT / 'static' / 'logo_sorriso_horizontal.png'


CSS = """
@page {
    size: A4 portrait;
    margin: 18mm 17mm 18mm;
    @bottom-left {
        content: "Gestão Saúde Oral — Material de treinamento";
        font-family: Arial, sans-serif;
        font-size: 7.5pt;
        color: #64748b;
    }
    @bottom-right {
        content: "Página " counter(page) " de " counter(pages);
        font-family: Arial, sans-serif;
        font-size: 7.5pt;
        color: #64748b;
    }
}
body {
    margin: 0;
    color: #172033;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 10pt;
    line-height: 1.52;
}
.header {
    display: table;
    width: 100%;
    border-bottom: 3px solid #0d47a1;
    padding-bottom: 10px;
    margin-bottom: 18px;
}
.header-logo, .header-meta {
    display: table-cell;
    vertical-align: middle;
}
.header-logo img {
    width: 185px;
    height: auto;
}
.header-meta {
    text-align: right;
    color: #64748b;
    font-size: 8pt;
}
h1 {
    color: #0d47a1;
    font-size: 22pt;
    line-height: 1.15;
    margin: 0 0 14px;
}
h2 {
    color: #0d47a1;
    font-size: 14pt;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 4px;
    margin: 20px 0 9px;
    page-break-after: avoid;
}
h3 {
    color: #0f766e;
    font-size: 11.5pt;
    margin: 15px 0 6px;
    page-break-after: avoid;
}
p {
    margin: 5px 0 8px;
}
ul, ol {
    margin: 5px 0 10px 21px;
    padding: 0;
}
li {
    margin: 3px 0;
}
.metadata {
    background: #f1f5f9;
    border: 1px solid #dbe4f0;
    border-left: 4px solid #0d47a1;
    padding: 9px 11px;
    margin-bottom: 16px;
}
.narracao, .tela, .alerta {
    padding: 8px 10px;
    margin: 7px 0;
    page-break-inside: avoid;
}
.narracao {
    background: #eff6ff;
    border-left: 4px solid #2563eb;
}
.tela {
    background: #f0fdfa;
    border-left: 4px solid #0f766e;
}
.alerta {
    background: #fff7ed;
    border-left: 4px solid #f97316;
}
.label {
    font-weight: bold;
    text-transform: uppercase;
    font-size: 8pt;
    letter-spacing: .04em;
}
.checklist {
    list-style: none;
    margin-left: 0;
}
.checklist li {
    border-bottom: 1px solid #e2e8f0;
    padding: 4px 0;
}
code {
    background: #eef2f7;
    border-radius: 3px;
    padding: 1px 4px;
    font-family: "DejaVu Sans Mono", monospace;
    font-size: 8.7pt;
}
strong {
    color: #0f274d;
}
"""


def inline_markup(value):
    escaped = html.escape(value.strip())
    escaped = re.sub(r'`([^`]+)`', r'<code>\1</code>', escaped)
    escaped = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', escaped)
    return escaped


def markdown_to_html(markdown):
    lines = markdown.splitlines()
    output = []
    paragraph = []
    list_type = None
    list_items = []
    metadata = []
    title_seen = False

    def flush_paragraph():
        if paragraph:
            text = ' '.join(part.strip() for part in paragraph)
            output.append(f'<p>{inline_markup(text)}</p>')
            paragraph.clear()

    def flush_list():
        nonlocal list_type
        if not list_items:
            return
        css_class = ' class="checklist"' if any(
            item.startswith('[ ] ') or item.startswith('[x] ')
            for item in list_items
        ) else ''
        output.append(f'<{list_type}{css_class}>')
        for item in list_items:
            if item.startswith('[ ] '):
                item = '☐ ' + item[4:]
            elif item.startswith('[x] '):
                item = '☑ ' + item[4:]
            output.append(f'<li>{inline_markup(item)}</li>')
        output.append(f'</{list_type}>')
        list_items.clear()
        list_type = None

    def flush_metadata():
        if metadata:
            output.append('<div class="metadata">')
            output.extend(f'<div>{inline_markup(item)}</div>' for item in metadata)
            output.append('</div>')
            metadata.clear()

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            flush_list()
            if title_seen:
                flush_metadata()
            continue

        heading = re.match(r'^(#{1,3})\s+(.+)$', stripped)
        if heading:
            flush_paragraph()
            flush_list()
            flush_metadata()
            level = len(heading.group(1))
            output.append(f'<h{level}>{inline_markup(heading.group(2))}</h{level}>')
            title_seen = True
            continue

        if title_seen and not output[-1].startswith('<h2') and re.match(
            r'^(Status|Versão de referência|Público|Duração estimada):',
            stripped,
        ):
            metadata.append(stripped.rstrip('  '))
            continue

        list_match = re.match(r'^[-*]\s+(.+)$', stripped)
        ordered_match = re.match(r'^\d+\.\s+(.+)$', stripped)
        if list_match or ordered_match:
            flush_paragraph()
            desired_type = 'ul' if list_match else 'ol'
            if list_type and list_type != desired_type:
                flush_list()
            list_type = desired_type
            list_items.append((list_match or ordered_match).group(1))
            continue

        callout = re.match(r'^\*\*(Narração|Tela|Alerta falado):\*\*\s*(.*)$', stripped)
        if callout:
            flush_paragraph()
            flush_list()
            kind = callout.group(1)
            css_class = {
                'Narração': 'narracao',
                'Tela': 'tela',
                'Alerta falado': 'alerta',
            }[kind]
            output.append(
                f'<div class="{css_class}">'
                f'<span class="label">{html.escape(kind)}</span><br>'
                f'{inline_markup(callout.group(2))}</div>'
            )
            continue

        paragraph.append(stripped)

    flush_paragraph()
    flush_list()
    flush_metadata()
    return '\n'.join(output)


def generate_pdf(markdown_path):
    body = markdown_to_html(markdown_path.read_text(encoding='utf-8'))
    document = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <style>{CSS}</style>
</head>
<body>
  <div class="header">
    <div class="header-logo"><img src="{LOGO_PATH.as_uri()}" alt="Sorriso da Gente"></div>
    <div class="header-meta">Roteiro de videoaula<br>Programa Sorriso da Gente</div>
  </div>
  {body}
</body>
</html>"""
    output_path = markdown_path.with_suffix('.pdf')
    HTML(string=document, base_url=str(PROJECT_ROOT)).write_pdf(output_path)
    return output_path


def main():
    paths = sorted(ROTEIROS_DIR.glob('[0-9][0-9]_*.md'))
    if len(paths) != 9:
        raise RuntimeError(f'Esperados 9 roteiros; encontrados {len(paths)}.')
    generated = [generate_pdf(path) for path in paths]
    for path in generated:
        print(path.relative_to(PROJECT_ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
