#!/usr/bin/env python3
"""Gera o roteiro passo a passo de configuração da WhatsApp Business Cloud API."""

from datetime import date
from html import escape
from pathlib import Path
import sys

from weasyprint import HTML


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
OUTPUT_PATH = PROJECT_ROOT / 'docs' / 'guia_configuracao_whatsapp_business_api.pdf'
LOGO_PATH = PROJECT_ROOT / 'static' / 'logo_sorriso_horizontal.png'


def _format_date(value):
    months = (
        'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
        'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
    )
    return f'{value.day} de {months[value.month - 1]} de {value.year}'


STEPS = [
    {
        'title': 'Criar a conta no Meta Business Suite',
        'detail': (
            'Acesse business.facebook.com e crie (ou utilize) uma conta de '
            'negócio vinculada ao CNPJ da clínica. É essa conta que vai '
            'concentrar o aplicativo, o número de WhatsApp e o faturamento.'
        ),
        'why': 'A Cloud API só pode ser usada a partir de uma conta de negócio Meta.',
    },
    {
        'title': 'Criar o aplicativo e adicionar o produto WhatsApp',
        'detail': (
            'Em developers.facebook.com, crie um novo aplicativo do tipo '
            '"Negócios" e adicione o produto "WhatsApp" na lista de produtos '
            'do aplicativo.'
        ),
        'why': 'O produto WhatsApp habilita o painel de configuração da API e gera os identificadores técnicos.',
    },
    {
        'title': 'Criar a WhatsApp Business Account (WABA) e cadastrar o número',
        'detail': (
            'Ainda no painel do produto WhatsApp, crie a WhatsApp Business '
            'Account e cadastre um número de telefone dedicado. Esse número '
            'não pode estar em uso no WhatsApp comum ou no WhatsApp Business '
            'app — precisa estar livre para a verificação.'
        ),
        'why': 'Cada número só pode estar vinculado a uma conta WhatsApp por vez (Cloud API ou app, nunca os dois).',
    },
    {
        'title': 'Verificar o número',
        'detail': (
            'A Meta envia um código por SMS ou ligação de voz para o número '
            'cadastrado. Informe o código recebido para concluir a verificação.'
        ),
        'why': 'Sem a verificação, o número não pode enviar mensagens pela API.',
    },
    {
        'title': 'Submeter a Verificação de Negócio (recomendado)',
        'detail': (
            'No Business Manager, em "Segurança do centro de negócios", '
            'inicie a Verificação de Negócio enviando os documentos da '
            'clínica solicitados pela Meta.'
        ),
        'why': (
            'Eleva o limite diário de mensagens e libera o nome de exibição '
            'personalizado do remetente. Sem isso, o número fica limitado a '
            'poucos destinatários por dia.'
        ),
    },
    {
        'title': 'Criar um System User e gerar o token de acesso permanente',
        'detail': (
            'Em "Usuários do sistema" do Business Manager, crie um System '
            'User com papel de administrador, atribua o aplicativo criado e '
            'gere um token com as permissões whatsapp_business_messaging e '
            'whatsapp_business_management. Marque o token sem expiração.'
        ),
        'why': (
            'O token temporário gerado automaticamente no painel expira em '
            '24 horas e não serve para produção; o token de System User é '
            'permanente e é o que o sistema vai usar para autenticar os envios.'
        ),
    },
    {
        'title': 'Anotar os identificadores técnicos',
        'detail': (
            'No painel "WhatsApp > Configuração da API", copie o Phone '
            'Number ID e o WhatsApp Business Account ID. Esses dois valores, '
            'junto com o token do passo anterior, são tudo que o sistema '
            'precisa para enviar mensagens.'
        ),
        'why': 'São os identificadores usados em toda chamada à Graph API.',
    },
    {
        'title': 'Configurar o webhook',
        'detail': (
            'No mesmo painel, configure a URL de webhook como '
            'https://sorrisodagentealagoas.com/comunicacao/webhook/whatsapp '
            'e defina um "verify token" de sua escolha (uma string '
            'aleatória). Informe esse mesmo valor à equipe técnica para ser '
            'configurado no sistema.'
        ),
        'why': (
            'O webhook recebe as confirmações de entrega/leitura das '
            'mensagens e as respostas dos pacientes, incluindo a palavra-chave '
            'de descadastro ("PARAR"/"SAIR").'
        ),
    },
    {
        'title': 'Criar e submeter os templates de mensagem',
        'detail': (
            'Em "Gerenciador de templates de mensagem", crie um template '
            'para cada tipo de envio (por exemplo, "lembrete_consulta"), '
            'prefira a categoria UTILITY para lembretes operacionais — é '
            'mais barata e tem aprovação mais rápida que MARKETING — e '
            'envie para aprovação da Meta.'
        ),
        'why': (
            'Toda mensagem iniciada pela clínica fora de uma conversa ativa '
            'precisa usar um template pré-aprovado pela Meta. A aprovação '
            'pode levar de minutos a alguns dias.'
        ),
    },
    {
        'title': 'Configurar a forma de pagamento',
        'detail': (
            'Em "Faturamento" do Business Manager, cadastre um cartão ou '
            'forma de pagamento válida. A cobrança é por conversa iniciada e '
            'varia por categoria de template e país — confira a tabela de '
            'preços atual diretamente no painel da Meta, pois ela é revisada '
            'periodicamente.'
        ),
        'why': 'Sem forma de pagamento ativa, o envio de mensagens é bloqueado mesmo com tudo configurado.',
    },
    {
        'title': 'Entregar as credenciais para ativação no sistema',
        'detail': (
            'Reúna os quatro valores — token de acesso permanente, Phone '
            'Number ID, WhatsApp Business Account ID e verify token do '
            'webhook — e entregue à equipe técnica para configuração das '
            'variáveis de ambiente do sistema.'
        ),
        'why': (
            'O canal WhatsApp do módulo Comunicação fica automaticamente '
            'desabilitado até essas variáveis serem configuradas — nenhuma '
            'campanha ou lembrete por WhatsApp é exibido como opção antes disso.'
        ),
    },
]

ENV_VARS = [
    ('WHATSAPP_ACCESS_TOKEN', 'Token permanente do System User (passo 6).'),
    ('WHATSAPP_PHONE_NUMBER_ID', 'Phone Number ID do número cadastrado (passo 7).'),
    ('WHATSAPP_BUSINESS_ACCOUNT_ID', 'WhatsApp Business Account ID (passo 7).'),
    ('WHATSAPP_WEBHOOK_VERIFY_TOKEN', 'Verify token escolhido para o webhook (passo 8).'),
]


def _step_sections():
    sections = []
    for index, step in enumerate(STEPS, start=1):
        sections.append(
            f"""
            <section class="step-page">
              <header class="page-header">
                <div><img src="{LOGO_PATH.resolve().as_uri()}" alt="Sorriso da Gente"></div>
                <div class="page-label">Configuração WhatsApp Business Cloud API</div>
              </header>
              <div class="step-heading">
                <div class="step-index">{index:02d}</div>
                <div>
                  <div class="eyebrow">Passo {index} de {len(STEPS)}</div>
                  <h2>{escape(step['title'])}</h2>
                </div>
              </div>
              <p class="detail">{escape(step['detail'])}</p>
              <div class="why"><strong>Por que esse passo é necessário</strong><p>{escape(step['why'])}</p></div>
            </section>
            """
        )
    return ''.join(sections)


def _env_table_rows():
    return ''.join(
        f"<tr><td class='code'>{escape(name)}</td><td>{escape(desc)}</td></tr>"
        for name, desc in ENV_VARS
    )


def build_html():
    generated_at = _format_date(date.today())
    logo_uri = LOGO_PATH.resolve().as_uri()

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>Configuração da WhatsApp Business Cloud API — Sorriso da Gente</title>
  <style>
    @page {{
      size: A4 portrait;
      margin: 16mm 16mm 18mm;
      @bottom-left {{
        content: "Gestão Saúde Oral • Guia de configuração WhatsApp Business API";
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
      font-size: 9.6pt;
      line-height: 1.48;
    }}
    .cover {{
      page: cover;
      height: 297mm;
      position: relative;
      overflow: hidden;
      padding: 23mm 20mm;
      color: white;
      background: linear-gradient(145deg, #0b367c 0%, #0d47a1 58%, #25d366 130%);
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
      color: #d9fdd3;
      font-size: 10pt;
      font-weight: 800;
      letter-spacing: .18em;
      text-transform: uppercase;
    }}
    .cover h1 {{
      max-width: 155mm;
      margin: 6mm 0 4mm;
      font-size: 28pt;
      line-height: 1.08;
      letter-spacing: -.03em;
    }}
    .cover-subtitle {{
      max-width: 140mm;
      color: #dbeafe;
      font-size: 12pt;
      line-height: 1.5;
    }}
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
    .intro-page, .step-page, .closing-page {{ page-break-before: always; }}
    .page-header {{
      display: table;
      width: 100%;
      margin-bottom: 7mm;
      padding-bottom: 4mm;
      border-bottom: 2px solid #dbe7f6;
    }}
    .page-header > div {{ display: table-cell; vertical-align: middle; }}
    .page-header img {{ width: 40mm; }}
    .page-label {{
      text-align: right;
      color: #0d47a1;
      font-size: 8pt;
      font-weight: 800;
      letter-spacing: .06em;
      text-transform: uppercase;
    }}
    h2 {{ margin: 0; color: #0d47a1; font-size: 18pt; line-height: 1.15; letter-spacing: -.02em; }}
    .lead {{ margin: 0 0 6mm; color: #526279; font-size: 10.5pt; line-height: 1.55; }}
    .eyebrow {{ color: #0fa968; font-size: 8pt; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; margin-bottom: 1.5mm; }}
    .step-heading {{ display: table; width: 100%; margin-bottom: 5mm; }}
    .step-heading > div {{ display: table-cell; vertical-align: middle; }}
    .step-index {{
      width: 14mm; height: 14mm; margin-right: 5mm;
      display: table-cell; text-align: center; vertical-align: middle;
      background: #0d47a1; color: white; border-radius: 10px;
      font-size: 13pt; font-weight: 800;
    }}
    .detail {{ font-size: 10.2pt; line-height: 1.6; color: #1f2937; }}
    .why {{
      margin-top: 6mm; padding: 4mm 5mm;
      border-left: 3mm solid #0fa968;
      background: #f0fdf6;
      border-radius: 2mm;
    }}
    .why strong {{ display: block; color: #0d6b40; font-size: 8.6pt; text-transform: uppercase; letter-spacing: .04em; margin-bottom: 1.5mm; }}
    .why p {{ margin: 0; font-size: 9.6pt; color: #1f2937; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 4mm; font-size: 9pt; }}
    table th, table td {{ padding: 2.6mm 3mm; border-bottom: 1px solid #e2e8f0; text-align: left; vertical-align: top; }}
    table th {{ background: #eef4fb; color: #0d47a1; font-size: 8.2pt; text-transform: uppercase; letter-spacing: .03em; }}
    td.code {{ font-family: "Courier New", monospace; font-weight: 700; color: #0d47a1; white-space: nowrap; }}
    .notice {{
      margin: 5mm 0; padding: 4mm 5mm;
      border: 1px solid #fed7a0; background: #fff7ed; border-radius: 2mm;
      font-size: 9.4pt; color: #7c4a03;
    }}
    .closing-page h2 {{ margin-bottom: 4mm; }}
    .check-list {{ margin-top: 4mm; }}
    .check-item {{ display: table; width: 100%; margin-bottom: 3mm; }}
    .check-item .box {{ display: table-cell; width: 6mm; vertical-align: top; }}
    .check-item .box span {{
      display: inline-block; width: 4.2mm; height: 4.2mm;
      border: 1.4pt solid #0d47a1; border-radius: 1mm;
    }}
    .check-item .label {{ display: table-cell; padding-left: 2mm; font-size: 9.6pt; }}
  </style>
</head>
<body>

<section class="cover">
  <div class="cover-logo"><img src="{logo_uri}"></div>
  <div class="cover-kicker">Guia de configuração • WhatsApp Business Cloud API</div>
  <h1>Comunicação por WhatsApp — passo a passo de ativação</h1>
  <div class="cover-subtitle">
    Roteiro para configurar a conta oficial da Meta (WhatsApp Business Cloud API)
    e liberar o canal WhatsApp no módulo Comunicação do sistema. Os 11 passos
    abaixo são feitos fora do sistema, diretamente nos painéis da Meta.
  </div>
  <div class="cover-meta">
    <div><strong>Responsável</strong>Gestão da clínica</div>
    <div><strong>Sistema</strong>Programa Sorriso da Gente</div>
    <div><strong>Atualizado em</strong>{generated_at}</div>
  </div>
</section>

<section class="intro-page">
  <header class="page-header">
    <div><img src="{logo_uri}"></div>
    <div class="page-label">Antes de começar</div>
  </header>
  <h2>O que você vai precisar</h2>
  <p class="lead">
    Esta etapa é feita fora do sistema, diretamente nos painéis da Meta
    (Facebook/Instagram). Tenha em mãos antes de começar:
  </p>
  <table>
    <tr><th>Item</th><th>Para quê</th></tr>
    <tr><td>CNPJ da clínica</td><td>Vinculação da conta de negócio na Meta.</td></tr>
    <tr><td>Um número de telefone livre</td><td>Será o remetente oficial das mensagens; não pode estar em uso em outro WhatsApp.</td></tr>
    <tr><td>Acesso a SMS ou chamada nesse número</td><td>Verificação obrigatória do número.</td></tr>
    <tr><td>Cartão ou forma de pagamento</td><td>Cobrança por conversa iniciada (varia por categoria e país).</td></tr>
    <tr><td>Documentos da clínica</td><td>Verificação de Negócio (recomendado, eleva limites de envio).</td></tr>
  </table>
  <div class="notice">
    <strong>Importante:</strong> nenhum desses passos é executado automaticamente
    pelo sistema — todos exigem acesso às suas próprias contas Meta. O canal de
    e-mail do módulo Comunicação já funciona normalmente e não depende deste
    roteiro.
  </div>
</section>

{_step_sections()}

<section class="closing-page">
  <header class="page-header">
    <div><img src="{logo_uri}"></div>
    <div class="page-label">Variáveis de ambiente</div>
  </header>
  <h2>O que entregar à equipe técnica</h2>
  <p class="lead">
    Ao concluir os passos acima, você terá os quatro valores abaixo. Eles são
    configurados como variáveis de ambiente do sistema — nenhum dado de
    paciente ou conteúdo de mensagem passa pela Meta antes disso.
  </p>
  <table>
    <tr><th>Variável</th><th>Onde encontrar</th></tr>
    {_env_table_rows()}
  </table>
  <div class="check-list">
    <div class="check-item"><div class="box"><span></span></div><div class="label">Conta de negócio Meta criada e vinculada ao CNPJ</div></div>
    <div class="check-item"><div class="box"><span></span></div><div class="label">Número de telefone verificado</div></div>
    <div class="check-item"><div class="box"><span></span></div><div class="label">Token permanente de System User gerado</div></div>
    <div class="check-item"><div class="box"><span></span></div><div class="label">Webhook configurado com o verify token</div></div>
    <div class="check-item"><div class="box"><span></span></div><div class="label">Template "lembrete_consulta" (categoria UTILITY) submetido</div></div>
    <div class="check-item"><div class="box"><span></span></div><div class="label">Forma de pagamento ativa no Business Manager</div></div>
    <div class="check-item"><div class="box"><span></span></div><div class="label">Quatro variáveis entregues à equipe técnica</div></div>
  </div>
  <div class="notice">
    Os preços por conversa e os limites de mensagens diárias são definidos e
    atualizados pela própria Meta — consulte sempre o painel oficial antes de
    decidir o volume de campanhas.
  </div>
</section>

</body>
</html>"""


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    document = build_html()
    HTML(string=document, base_url=str(PROJECT_ROOT)).write_pdf(OUTPUT_PATH)
    print(OUTPUT_PATH.relative_to(PROJECT_ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
