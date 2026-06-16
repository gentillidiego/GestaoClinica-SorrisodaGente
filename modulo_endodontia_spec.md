# Gestão Saúde Oral — Programa Sorriso da Gente
## Especificação Técnica: Módulo de Gestão Endodôntica

> **Versão:** 1.0 | **Status:** Em desenvolvimento
> **Referência clínica:** AAE Consensus 2009, CFO Res-91/2009, Critérios de Strindberg
> **Conformidade legal:** LGPD, Lei 13.787/2018, CID-10/TUSS

---

## Índice

1. [Visão Geral do Módulo](#1-visão-geral-do-módulo)
2. [Requisitos Legais e Segurança](#2-requisitos-legais-e-segurança)
3. [Anamnese e Dados Iniciais](#3-anamnese-e-dados-iniciais)
4. [Exame Clínico e Testes Diagnósticos](#4-exame-clínico-e-testes-diagnósticos)
5. [Taxonomia Diagnóstica (AAE)](#5-taxonomia-diagnóstica-aae)
6. [Odontometria — Núcleo Matemático](#6-odontometria--núcleo-matemático)
7. [Protocolo Biomecânico e Irrigação](#7-protocolo-biomecânico-e-irrigação)
8. [Medicação Intracanal e Selamento Provisório](#8-medicação-intracanal-e-selamento-provisório)
9. [Obturação Final](#9-obturação-final)
10. [Gestão Multi-Sessão](#10-gestão-multi-sessão)
11. [Imagens e DICOM](#11-imagens-e-dicom)
12. [Proservação e Critérios de Strindberg](#12-proservação-e-critérios-de-strindberg)
13. [Motor Financeiro](#13-motor-financeiro)
14. [Trilha de Auditoria](#14-trilha-de-auditoria)
15. [Alertas e Regras de Negócio](#15-alertas-e-regras-de-negócio)

---

## 1. Visão Geral do Módulo

O módulo endodôntico gerencia o ciclo completo de tratamento de canais radiculares, desde a anamnese inicial até a proservação longitudinal.

**Entidade central:** `Tratamento Endodontico` vinculada a `Dente` (via odontograma) e `Paciente`.

**Arquitetura de dados:**
- Um paciente pode ter múltiplos dentes em tratamento simultaneamente.
- Cada dente em tratamento gera N `Sessões` sequenciais.
- Cada sessão pertence a um `Operador` (aluno ou CD) e pode ter um `Supervisor` (professor).
- Nenhum registro é deletado fisicamente — apenas `soft delete` com versionamento.

---

## 2. Requisitos Legais e Segurança

### 2.1 Conformidade Obrigatória

| Requisito | Norma | Implementação |
|---|---|---|
| Criptografia em repouso e em trânsito | LGPD / Lei 13.787/2018 | AES-256 no banco + TLS 1.3 |
| Dados sensíveis de saúde | LGPD Art. 11 | RBAC — acesso restrito ao time de saúde |
| Assinatura digital | CFO Res-91/2009 | Suporte a certificado ICP-Brasil |
| Prontuário eletrônico válido | Lei 13.787/2018 | Assinatura digital nativa na UI |
| Consentimento (TCLE) | CFO / CDC | Módulo de TCLE com aceite eletrônico |

### 2.2 Assinatura Digital

```
Fluxo Clínica-Escola:
  1. Aluno preenche evolução da sessão
  2. Submete para aprovação do professor
  3. Professor revisa e assina com certificado ICP-Brasil
  4. Registro travado — nenhuma edição posterior sem novo fluxo de retificação
```

```
Fluxo Clínica Privada:
  1. CD preenche e assina diretamente com certificado ICP-Brasil
  2. Registro travado imediatamente após assinatura
```

### 2.3 TCLE Endodôntico

O sistema deve manter um acervo de modelos de TCLE com cláusulas específicas para:
- Fratura de instrumento dentro do canal
- Calcificações atípicas
- Necessidade de cirurgia parendodôntica (apicectomia)
- Uso de imagens em publicações acadêmicas (conforme LGPD)

**Aceite:** digital via tablet na recepção ou portal do paciente.

---

## 3. Anamnese e Dados Iniciais

### 3.1 Dados Demográficos

```
Campos obrigatórios:
- nome_completo: string
- data_nascimento: date  → idade calculada automaticamente
- sexo_biologico: enum [M, F]
- cpf: string (único)
- rg: string
- estado_civil: enum [solteiro, casado, divorciado, viuvo, outro]
- ocupacao: string
- endereco: object { logradouro, numero, bairro, cidade, uf, cep }
- telefone_principal: string
- email: string
```

### 3.2 Anamnese Sistêmica

Campos boolean + campo de detalhamento quando `true`:

```
Condições sistêmicas:
- diabetes_mellitus: boolean + tipo (I / II) + controle (compensado / descompensado)
- hipertensao_arterial: boolean + medicamento_em_uso
- disturbio_tireoide: boolean + tipo
- discrasias_sanguineas: boolean + qual
- cardiopatia: boolean + tipo
- gestante: boolean + semana_gestacional
- outras_condicoes: text
```

### 3.3 Medicamentos em Uso

```
medicamentos_uso_continuo: array de {
  nome: string,
  principio_ativo: string,
  dose: string,
  frequencia: string
}
```

### 3.4 Alergias — Campo Crítico

> ⚠️ **REGRA DE NEGÓCIO CRÍTICA:** Qualquer alergia marcada abaixo deve gerar alerta persistente em vermelho no cabeçalho fixo do paciente em TODAS as telas do prontuário.

```
Alergias odontológicas (boolean por item):
- alergia_penicilina
- alergia_cefalosporina
- alergia_dipirona
- alergia_aines
- alergia_hipoclorito_sodio    ← bloqueia irrigação com NaOCl
- alergia_eugenol              ← bloqueia cimentos eugenólicos
- alergia_clorexidina
- alergia_latex                ← alerta para uso de lençol sem látex
- outras_alergias: text
```

### 3.5 Queixa Principal (História da Dor)

```
queixa_principal: {
  inicio: enum [espontanea, provocada],
  duracao: enum [fugaz, persistente],
  intensidade: enum [leve, moderada, severa, insuportavel_pulsatil],
  localizacao: enum [localizada, difusa_quadrante, referida],
  fatores_exacerbantes: multiselect [frio, calor, mastigacao, decubito, espontanea],
  fatores_alivio: multiselect [analgesico, antiinflamatorio, frio, calor, nenhum],
  descricao_livre: text
}
```

---

## 4. Exame Clínico e Testes Diagnósticos

### 4.1 Exame Extraoral

```
exame_extraoral: {
  linfadenopatia_cervical: boolean,
  linfadenopatia_submandibular: boolean,
  assimetria_facial: boolean,
  edema_extraoral: boolean,
  observacoes: text
}
```

### 4.2 Exame Intraoral

```
exame_intraoral: {
  edema_submucoso: boolean,
  fistula_trajeto: boolean + localizacao,
  carie_profunda: boolean,
  restauracao_inadequada: boolean,
  faceta_desgaste: boolean,
  observacoes: text
}
```

### 4.3 Parâmetros Periodontais do Dente

```
periodonto: {
  mobilidade: enum [grau_0, grau_I, grau_II, grau_III],
  sondagem_mm: { mesial, distal, vestibular, lingual_palatino },
  tipo_lesao: enum [endodontica, periodontal, endo_perio, inconclusivo]
}
```

### 4.4 Testes de Vitalidade e Provocação

Todos os testes registram: `resultado`, `dente_teste`, `dente_controle`, `data`.

#### Palpação Apical
```
palpacao_apical: enum [positiva, negativa, nao_realizada]
```

#### Percussão
```
percussao_vertical: enum [positiva, negativa, nao_realizada]   // inflamação LPA apical
percussao_horizontal: enum [positiva, negativa, nao_realizada] // envolvimento periodontal lateral
```

#### Teste Térmico Frio (Endo-Ice)
```
teste_frio: {
  resposta: enum [positiva, negativa, nao_realizada],
  declinio_dor: enum [rapido_normal, lento_prolongado, ausente],
  // "lento_prolongado" = sinal patognomônico de Pulpite Irreversível Sintomática
  observacoes: text
}
```

#### Teste Térmico Calor (Guta termoplastificada)
```
teste_calor: {
  resposta: enum [positiva, negativa, nao_realizada],
  intensidade: enum [leve, moderada, intensa],
  observacoes: text
}
```

#### Teste Elétrico (Pulp Tester)
```
teste_eletrico: {
  realizado: boolean,
  valor_dente_teste_microA: decimal,
  valor_dente_controle_microA: decimal,
  interpretacao: enum [vitalidade_normal, vitalidade_reduzida, sem_resposta],
  observacoes: text
}
```

---

## 5. Taxonomia Diagnóstica (AAE)

> ⚠️ **REGRA DE NEGÓCIO:** O sistema deve obrigar a seleção de **diagnóstico pulpar + diagnóstico apical** antes de liberar o planejamento de tratamento e geração de orçamento. Campos de texto livre são proibidos para diagnóstico.

### 5.1 Diagnóstico Pulpar

| Valor (enum) | Label | Comportamento do Sistema |
|---|---|---|
| `polpa_normal` | Polpa Normal | Bloqueia orçamento para tratamento endodôntico neste dente |
| `pulpite_reversivel` | Pulpite Reversível | Sugere controle conservador; alerta se for orçado tratamento radical |
| `pulpite_irreversivel_sintomatic` | Pulpite Irreversível Sintomática | Libera cobrança de urgência (extirpação) |
| `pulpite_irreversivel_assintomatic` | Pulpite Irreversível Assintomática | Indica pulpectomia mesmo sem dor |
| `necrose_pulpar` | Necrose Pulpar | Altera sugestão de CRT (reduz margem para 0.5–1.0 mm) |
| `dente_previamente_tratado` | Dente Previamente Tratado | Muda workflow para **Retratamento** + altera codificação TUSS |
| `terapia_previamente_iniciada` | Terapia Previamente Iniciada | Alerta de quebra de continuidade do cuidado |

### 5.2 Diagnóstico Apical

| Valor (enum) | Label | Comportamento do Sistema |
|---|---|---|
| `tecidos_apicais_normais` | Tecidos Apicais Normais | Sem alertas adicionais |
| `periodontite_apical_sintomatic` | Periodontite Apical Sintomática | Alerta de urgência |
| `periodontite_apical_assintomatic` | Periodontite Apical Assintomática | Indica necessidade de tratamento mesmo sem dor |
| `abscesso_apical_agudo` | Abscesso Apical Agudo | Sugere modelo pré-formatado de receita antimicrobiana + atestado |
| `abscesso_apical_cronico` | Abscesso Apical Crônico | Verifica presença de fístula no exame intraoral |
| `osteite_condensante` | Osteíte Condensante | Nota clínica sobre imagem radiopaca |

### 5.3 Mapeamento CID-10 / TUSS

```
Diagnóstico AAE → CID-10 sugerido:
  pulpite_reversivel              → K04.0
  pulpite_irreversivel_*          → K04.0
  necrose_pulpar                  → K04.1
  abscesso_apical_agudo           → K04.6
  abscesso_apical_cronico         → K04.7 / K04.6
  periodontite_apical_*           → K04.5
  osteite_condensante             → K04.3
  dente_previamente_tratado       → K04.9 + código TUSS de Retratamento
```

---

## 6. Odontometria — Núcleo Matemático

> A odontometria é canal-específica. O sistema deve gerar uma linha de registro por canal do dente selecionado.

### 6.1 Canais por Grupo Dentário (Referência)

| Dente | Canais Típicos | Observação |
|---|---|---|
| Incisivos sup/inf | 1 | Raramente 2 |
| Caninos | 1 | — |
| Pré-molares sup | 1–2 | Alta variação — alerta ao usuário |
| Pré-molares inf | 1–2 | — |
| 1º Molar inferior (46/36) | 3–4 | MV, ML, D, DL (4º canal frequente) |
| 1º Molar superior (16/26) | 3–4 | MV1, MV2, P, D |
| 2º Molares | 2–4 | Alta variação |

### 6.2 Campos por Canal

```
odontometria_canal: {
  identificador_canal: string  // ex: "MV", "ML", "D", "DL"
  ponto_referencia_coronario: string  // obrigatório; persistir em todas as sessões

  // INPUTS
  cad_mm: decimal   // Comprimento Aparente do Dente (da radiografia)
  cri_mm: decimal   // Comprimento Real do Instrumento (batente na lima)
  cai_mm: decimal   // Comprimento Aparente do Instrumento (da radiografia de odontometria)

  // OUTPUTS calculados automaticamente
  crd_mm: decimal   // Comprimento Real do Dente (Técnica de Bregman)
  crt_mm: decimal   // Comprimento Real de Trabalho (baseado no diagnóstico pulpar)

  // Localizador apical eletrônico
  localizador_apical_usado: boolean
  modelo_localizador: string     // ex: "Morita DentaPort ZX", "Novapex", "Finepex"
  leitura_localizador: decimal   // valor no display (tipicamente 0.0 ou 0.5)
  confirmacao_eletronica: boolean

  observacoes: text
}
```

### 6.3 Fórmulas Automáticas do Back-end

#### Técnica de Bregman (CRD)

```
CRD = (CRI × CAD) / CAI
```

#### CRT baseado no Diagnóstico Pulpar

```python
if diagnostico_pulpar in ['pulpite_irreversivel_sintomatic', 'pulpite_irreversivel_assintomatic']:
    # Biopulpectomia — polpa viva
    crt_sugerido = CRD - 1.0  # range: CRD - 1.0 a CRD - 1.5 mm

elif diagnostico_pulpar in ['necrose_pulpar', 'dente_previamente_tratado']:
    # Necropulpectomia — polpa morta / lesão periapical
    crt_sugerido = CRD - 0.5  # range: CRD - 0.5 a CRD - 1.0 mm
```

> ⚠️ O valor sugerido é editável pelo operador. A substituição manual deve ser registrada na trilha de auditoria com o valor original, o valor editado e o operador.

---

## 7. Protocolo Biomecânico e Irrigação

### 7.1 Instrumentação

```
instrumentacao: {
  lai_numero: integer          // Lima Apical Inicial (ex: 15, 20, 25)
  lai_crt_confirmado: boolean

  tecnica: enum [
    crown_down,
    step_back,
    forcas_balanceadas,
    reciprocante,
    rotatoria_continua,
    hibrida_tagger
  ]

  sistema_rotatoria: string    // ex: "WaveOne Gold", "Reciproc Blue", "ProTaper Next"
  liga_instrumento: enum [
    niti_convencional,
    niti_m_wire,
    niti_gold_wire,
    aco_inoxidavel
  ]

  // Rastreabilidade de uso do instrumento
  instrumento_id: string       // código de barras ou ID interno
  numero_uso_atual: integer    // contagem automática
  limite_uso_maximo: integer   // definido por protocolo ou fabricante

  observacoes: text
}
```

> ⚠️ **ALERTA DE DESCARTE:** Quando `numero_uso_atual >= limite_uso_maximo`, o sistema deve bloquear a seleção do instrumento e exibir alerta de descarte obrigatório.

### 7.2 Irrigação

```
irrigacao: {
  solucao_principal: enum [
    hipoclorito_1pct,
    hipoclorito_2_5pct,
    hipoclorito_5_25pct,
    clorexidina_gel_2pct,
    clorexidina_liquida_2pct,
    soro_fisiologico
  ]

  // ALERTA AUTOMÁTICO: se solucao_principal contém hipoclorito
  // E paciente tem alergia_hipoclorito_sodio = true
  // → Modal bloqueante vermelho, impede prosseguimento

  quelante_edta: boolean       // EDTA 17%
  tempo_edta_segundos: integer

  agitacao: enum [nao_realizada, pui_ultrasson, sonico_endoactivator, manual]

  volume_total_ml: decimal
  observacoes: text
}
```

---

## 8. Medicação Intracanal e Selamento Provisório

### 8.1 Medicação Intracanal (MIC)

```
medicacao_intracanal: {
  substancia: enum [
    hidroxido_calcio_aquoso,
    hidroxido_calcio_propilenoglicol,
    hidroxido_calcio_oleoso,
    pmcc_paramonoclorofenol_canforado,
    formocresol,
    clorexidina_gel,
    sem_medicacao
  ]

  veiculo: string              // ex: "Propilenoglicol", "PMCC", "Óleo de silicone"
  quantidade_aproximada: string
  observacoes: text
}
```

### 8.2 Selamento Coronário Provisório

```
selamento_provisorio: {
  material: enum [
    cimento_provisorio_eugenolico,
    resina_fotopolimerizavel_temporaria,
    ionômero_vidro,
    cavit,
    outro
  ]

  espessura_estimada_mm: decimal   // mínimo recomendado: 3.5–4 mm
  data_colocacao: date

  // Gatilho para alerta de abandono (ver seção 15)
  proxima_sessao_prevista: date
}
```

---

## 9. Obturação Final

### 9.1 Cone Principal

```
cone_principal: {
  material: enum [guta_percha, resilon, guta_percha_termoativada],
  calibre_iso: integer,          // ex: 25, 30, 40
  conicidade: enum [c02, c04, c06, c08, c_anatomico],
  prova_cone_realizada: boolean,
  tug_back_presente: boolean,    // resistência tátil = cone adaptado
  crt_cone_confirmado_mm: decimal
}
```

### 9.2 Cimento Obturador

```
cimento_obturador: {
  classe: enum [
    epoxi_ah_plus,
    epoxi_ah_plus_jet,
    epoxi_sealer_plus,
    bioceramic_endosequence,
    bioceramic_bioc_sealer,
    resinoso_lateral,
    ionômero_vidro,
    outro
  ]

  lote: string
  validade: date
}
```

### 9.3 Técnica de Obturação

```
tecnica_obturacao: enum [
  condensacao_lateral_fria,
  onda_continua_calor_tocc,
  hibrida_tagger,
  cone_unico,
  obturacao_termoplatica_injetada,
  bioceramic_cone_unico
]
```

### 9.4 Controle de Qualidade (Gaps e Voids)

```
controle_qualidade: {
  radiografia_final_aprovada: boolean,
  gaps_identificados: boolean,
  voids_identificados: boolean,
  observacoes_qualidade: text
}
```

> ⚠️ **GATILHO DE ENCAMINHAMENTO RESTAURADOR:** Ao salvar a obturação final como concluída, o sistema deve gerar automaticamente um alerta vermelho no dashboard do CD responsável e na recepção indicando necessidade de restauração coronária definitiva.

---

## 10. Gestão Multi-Sessão

### 10.1 Estrutura de Sessão

```
sessao: {
  id: uuid,
  numero_sessao: integer,         // 1, 2, 3...
  total_sessoes_planejadas: integer,
  data_sessao: datetime,
  operador_id: uuid,
  supervisor_id: uuid (nullable), // para clínicas-escola
  status: enum [
    realizada,
    em_andamento,
    cancelada,
    aguardando_retorno
  ],
  etapa_realizada: enum [
    abertura_coronal,
    neutralizacao_septica,
    odontometria,
    preparo_biomecanico_parcial,
    preparo_biomecanico_completo,
    medicacao_intracanal,
    troca_medicacao,
    obturacao,
    controle_proservacao
  ],
  proxima_sessao_prevista: date,
  janela_retorno_dias: integer,   // default: 15 a 30 dias para Ca(OH)2
  assinada_digitalmente: boolean,
  data_assinatura: datetime
}
```

### 10.2 Status do Tratamento

```
status_tratamento: enum [
  aguardando_inicio,
  em_andamento,
  aguardando_retorno_paciente,  // ← gera alerta se expirar janela
  obturado_aguardando_restauracao,
  concluido,
  abandono,
  retratamento_necessario
]
```

---

## 11. Imagens e DICOM

### 11.1 Categorias Obrigatórias de Imagem

```
categoria_imagem: enum [
  periapical_inicial,
  odontometria,
  prova_cone,
  final_qualidade,
  proservacao_6m,
  proservacao_1a,
  proservacao_2a,
  proservacao_4a,
  tomografia_cbct,
  outra
]
```

### 11.2 Metadados da Imagem

```
imagem_clinica: {
  id: uuid,
  sessao_id: uuid,
  categoria: categoria_imagem (obrigatório),
  arquivo_path: string,
  formato: enum [jpeg, png, dicom, tiff],
  data_captura: datetime,
  equipamento: string,          // ex: "Sensor Schick 33", "Placa fósforo Agfa"
  anotacoes_clinicas: text,
  operador_id: uuid
}
```

### 11.3 Visualizador DICOM (CBCT)

Funcionalidades mínimas do visualizador integrado:

- Zoom sem perda de resolução
- Ajuste de brilho e contraste (janela/nível)
- Inversão de polaridade (negativo)
- Filtros de pseudocor
- Medição em milímetros na imagem
- Marcações/anotações sobrepostas salvas no prontuário

---

## 12. Proservação e Critérios de Strindberg

### 12.1 Agendamento Automático de Retornos

Ao registrar a obturação como concluída, o sistema deve criar automaticamente os seguintes retornos:

```
retornos_proservacao = [
  { prazo: "6 meses",  tipo: "proservacao_6m" },
  { prazo: "12 meses", tipo: "proservacao_1a" },
  { prazo: "24 meses", tipo: "proservacao_2a" },
  // Se lesão periapical extensa no diagnóstico inicial:
  { prazo: "48 meses", tipo: "proservacao_4a" }
]
```

Disparar notificações via WhatsApp/API de comunicação X dias antes de cada retorno (configurável, default: 7 dias).

### 12.2 Formulário de Avaliação (Critérios de Strindberg)

#### Critérios Clínicos

```
avaliacao_clinica: {
  dente_em_funcao_mastigatoria: boolean,       // SIM = favorável
  ausencia_dor_percussao: boolean,             // SIM = favorável
  ausencia_dor_palpacao_apical: boolean,       // SIM = favorável
  ausencia_edema_mucosa: boolean,              // SIM = favorável
  ausencia_fistula: boolean,                   // SIM = favorável
  observacoes: text
}
```

#### Critérios Radiográficos

```
avaliacao_radiografica: {
  espaco_periodontal_normal: boolean,          // SIM = favorável
  lamina_dura_integra: boolean,                // SIM = favorável
  ausencia_lesao_radiolucidia: boolean,        // SIM = favorável
  reducao_lesao_preexistente: boolean,         // SIM = favorável (se havia lesão)
  observacoes: text
}
```

#### Resultado Final da Proservação

```python
# Lógica de classificação baseada em Strindberg
if all(criterios_clinicos) and all(criterios_radiograficos):
    resultado = "SUCESSO"

elif any(criterio negativo e instável):
    resultado = "INSUCESSO"  # → Sugerir retratamento ou apicectomia

else:
    resultado = "DUVIDA"     # → Manter acompanhamento, novo retorno em 6 meses
```

### 12.3 Qualidade Restauradora (Check de Fechamento)

```
restauracao_coronaria: {
  tipo: enum [resina_composta, coroa_ceramica, onlay, nenhuma],
  selamento_adequado: boolean,
  data_restauracao: date,
  cd_restaurador_id: uuid,
  observacoes: text
}
```

---

## 13. Motor Financeiro

### 13.1 Complexidade por Grupo Dentário

| Grupo | Canais Típicos | Complexidade | Multiplicador |
|---|---|---|---|
| Incisivos / Caninos | 1 | Baixa | 1.0× |
| Pré-molares | 1–2 | Intermediária | 1.3–1.5× |
| Molares | 3–4+ | Alta | 1.8–2.5× |

### 13.2 Estrutura de Orçamento

O orçamento deve ser gerado **canal a canal**, não por dente, para evitar subcobrança em casos complexos.

```
orcamento_item: {
  dente_numero: integer,
  canal_id: string,
  procedimento: enum [
    tratamento_canal_1_canal,
    tratamento_canal_2_canais,
    tratamento_canal_por_canal_adicional,
    retratamento_1_canal,
    retratamento_por_canal_adicional,
    urgencia_extirpacao_pulpar,
    curativo_demora,
    radiografia_periapical
  ],
  codigo_tuss: string,
  codigo_cid10: string,
  valor_unitario: decimal,
  sessoes_previstas: integer,
  observacoes: text
}
```

### 13.3 Diferenciação Tratamento × Retratamento

```python
if diagnostico_pulpar == 'dente_previamente_tratado':
    tipo_workflow = "RETRATAMENTO"
    # Alterar codificação TUSS
    # Alterar nomenclatura no orçamento
    # Ajustar valor (retratamento tipicamente mais complexo)
else:
    tipo_workflow = "TRATAMENTO"
```

---

## 14. Trilha de Auditoria

Toda alteração no banco de dados deve gerar um registro imutável.

```
audit_log: {
  id: uuid,
  timestamp: datetime (NTP sincronizado),
  usuario_id: uuid,
  perfil_usuario: enum [aluno, cd, professor, admin, recepcao],
  acao: enum [CREATE, READ, UPDATE, DELETE_LOGICO],
  tabela_afetada: string,
  registro_id: uuid,
  valor_anterior: json,
  valor_novo: json,
  ip_origem: string,
  observacao: text (obrigatório em UPDATE e DELETE_LOGICO)
}
```

> ⚠️ Registros de auditoria são somente-leitura. Nenhum perfil pode editá-los ou deletá-los, nem mesmo admin.

---

## 15. Alertas e Regras de Negócio

### 15.1 Mapa de Alertas

| Trigger | Tipo | Ação |
|---|---|---|
| Alergia a NaOCl + seleção de hipoclorito | 🔴 Modal bloqueante | Impede prosseguimento |
| Alergia a eugenol + cimento eugenólico | 🔴 Modal bloqueante | Impede prosseguimento |
| Alergia a látex registrada | 🟡 Banner persistente | Avisa em todas as telas |
| Instrumento no limite de uso | 🔴 Bloqueio logístico | Impede reutilização |
| Sessão sem retorno após janela prevista | 🟡 Dashboard recepção | Aciona contato ativo |
| Obturação concluída sem restauração agendada | 🔴 Dashboard CD + recepção | Alerta encaminhamento |
| Diagnóstico = `polpa_normal` + orçamento endodôntico | 🔴 Bloqueio orçamento | Impede geração |
| `dente_previamente_tratado` selecionado | 🔵 Informativo | Muda workflow para Retratamento |
| `abscesso_apical_agudo` selecionado | 🟡 Sugestão | Abre modelo de receita antimicrobiana |
| Proservação vencida não remarcada | 🟡 Dashboard + notificação WhatsApp | Dispara lembrete automático |
| Tratamento endodôntico sem TCLE assinado | 🔴 Bloqueio | Impede início do tratamento |

### 15.2 Fluxo de Status Resumido

```
[Diagnóstico Pulpar + Apical definidos]
        ↓
[TCLE assinado]
        ↓
[Orçamento gerado e aprovado]
        ↓
[Sessão 1: Abertura + Odontometria]
        ↓
[Sessão N: Preparo biomecânico + Medicação]
        ↓
[Sessão final: Obturação]
        ↓
[ALERTA: Restauração coronária obrigatória]
        ↓
[Restauração realizada]
        ↓
[Proservação 6m → 1a → 2a → 4a (se necessário)]
        ↓
[Critérios de Strindberg → SUCESSO / DÚVIDA / INSUCESSO]
```

---

## Referências Clínicas

- **AAE Consensus 2009** — Taxonomia diagnóstica pulpar e periapical
- **Strindberg (1956)** — Critérios de avaliação de sucesso endodôntico
- **Técnica de Bregman (1950s)** — Correção de magnificação radiográfica
- **CFO Resolução 91/2009** — Prontuário eletrônico e assinatura digital ICP-Brasil
- **LGPD (Lei 13.709/2018)** — Proteção de dados sensíveis de saúde
- **Lei 13.787/2018** — Digitalização de prontuários médicos

---

*Documento gerado para uso interno de desenvolvimento — Programa Sorriso da Gente*
