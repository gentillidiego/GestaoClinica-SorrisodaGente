# Matriz RBAC de Rotas — 20/06/2026

Esta matriz registra a autorização efetiva no backend. Botões e abas ocultos
são apenas uma ajuda visual e nunca substituem a validação da rota.

Perfis:

- `ADM`: Administrador
- `COO`: Coordenação
- `CLI`: Clínicos
- `REC`: Recepção
- `CME`: CME / Estoque
- `RAD`: Radiologia
- `ANC`: Análises Clínicas
- `COM`: Comunicação
- `SSA`: SSA/SMS
- `AUD`: Auditoria

## Matriz por grupo de rota

| Grupo / operação | Permissão exigida | Perfis autorizados |
|---|---|---|
| Dashboard e Central de Comando | `dashboard:view`, `command_center:view` | Todos os dez perfis |
| Paciente — listar e abrir cadastro básico | `patients:view` | ADM, COO, CLI, REC, CME, RAD, ANC, AUD |
| Paciente — criar e editar | `patients:write` | ADM, CLI, REC |
| Paciente — excluir | `patients:delete` | ADM |
| Anamnese — consultar | `patients:view` + `anamnesis:view` | ADM, COO, CLI, AUD |
| Anamnese — criar e editar | `patients:view` + `anamnesis:write` | ADM, CLI |
| Plano de tratamento — consultar | `patients:view` + `treatment:view` | ADM, COO, CLI, AUD |
| Plano de tratamento — criar, editar e excluir | `patients:view` + `treatment:write` | ADM, CLI |
| Plano de tratamento — assinar/concluir | anteriores + `documents:sign` | ADM, CLI |
| Atendimento/evolução — consultar | `patients:view` + `attendance:view` | ADM, COO, CLI, AUD |
| Atendimento/evolução — criar, editar e excluir | `patients:view` + `attendance:write` | ADM, CLI |
| Atendimento — assinaturas do paciente, executor e CD | anteriores + `documents:sign` | ADM, CLI |
| Exames odontológicos e de imagem — consultar | `patients:view` + `exams:view` | ADM, CLI, RAD |
| Exames odontológicos e de imagem — criar/alterar/upload | `patients:view` + `exams:write` | ADM, CLI, RAD |
| Exames — excluir | `patients:view` + `exams:delete` | ADM, CLI |
| Exames clínico/laboratoriais — consultar | `patients:view` + `laboratorio:view` | ADM, CLI, CME, ANC |
| Exames clínico/laboratoriais — criar/alterar/upload | `patients:view` + `laboratorio:write` | ADM, CLI, CME, ANC |
| Solicitação de exame de imagem | `patients:view` + `exams:write` | ADM, CLI, RAD |
| Solicitação de exame clínico/laboratorial | `patients:view` + `laboratorio:write` | ADM, CLI, CME, ANC |
| Fila de solicitações de exame de Imagem (Radiologia) | `radiologia:view`/`radiologia:write` | ADM, RAD |
| Fila de solicitações de exame Clínico/Laboratorial (Análises Clínicas) | `analises_clinicas:view`/`analises_clinicas:write` | ADM, ANC |
| Estomatologia — consultar | `patients:view` + `estomatologia:view` | ADM, CLI |
| Estomatologia — alterar e anexar fotos | `patients:view` + `estomatologia:write` | ADM, CLI |
| Receituário e atestado — gerar/excluir/baixar | `patients:view` + `documents:generate` | ADM, CLI, REC |
| Encaminhamento de Estomatologia em PDF | anteriores + `estomatologia:view` | ADM, CLI |
| Comprovante de assinatura | `patients:view` + `documents:sign` | ADM, CLI |
| Biblioteca Visual | filtrada por `exams:view`, `estomatologia:view` e `endodontia:view` | ADM e CLI veem todas as origens; RAD vê somente exames |
| Linha do Tempo clínica | `clinical_timeline:view` | ADM, COO, CLI, AUD |
| Materiais no prontuário | `patients:view` + `inventory:view/write` | ADM, COO, CME |
| Endodontia — leitura e escrita | `patients:view` + `endodontia:view/write` | ADM, CLI |
| Prótese — leitura e escrita | `patients:view` + `prosthesis:view/write` | ADM, CLI |
| Endodontia/Prótese — assinaturas e pagamentos | permissão de escrita + `documents:sign` | ADM, CLI |
| Agenda | `agenda:view/write` | ADM, COO, CLI, REC; CLI limitado à própria agenda |
| Triagem | `triage:write` | ADM, CLI, REC |
| Estoque administrativo | `inventory:view/write` | ADM, COO, CME |
| Relatórios institucionais | `reports:view` + tipo permitido | ADM, COO, COM, SSA, AUD |
| BI | `bi:view` | ADM, COO, COM, SSA |
| Epidemiologia | `epidemiologia:view` | ADM, COO, SSA |
| Custos financeiros/SIGTAP | `financeiro:view/write` | ADM, COO |
| Integrações | `integrations:view/write` | ADM e COO escrevem; AUD somente consulta |
| Usuários, unidades e pré-cadastros | `users:view/write` ou administrador | ADM |
| Auditoria | `audit:view` | ADM, AUD |

## Escopo de registro e proteção contra IDOR

- Exames editados por URL precisam pertencer simultaneamente ao ID da
  anamnese e ao tipo de exame esperados.
- Procedimentos e atendimentos são consultados e alterados com
  `id + patient_id`; IDs pertencentes a outro paciente são rejeitados.
- Etapas, pagamentos e assinaturas de Prótese derivam o paciente do caso
  persistido e rejeitam `patient_id` divergente enviado pelo formulário.
- Sessões e assinaturas de Endodontia exigem vínculo entre
  `followup_id + endodontia_id`; o cancelamento deriva o paciente do caso.
- Receituários, atestados e encaminhamentos usam nomes previsíveis somente
  depois de confirmar no banco o par documento/paciente.
- PDFs de relatório exigem o tipo autorizado; o relatório gerencial legado
  exige o próprio usuário ou administrador.
- Arquivos de exame são entregues somente depois de consultar o registro pai e
  aplicar a permissão específica da origem.

## Resposta negada

Uma política central é executada antes das rotas clínicas. Negação autenticada:

- responde HTTP `403`;
- retorna JSON genérico para chamadas AJAX/JSON;
- não revela regra interna ou existência de outro registro;
- grava `access_denied` em `audit_logs`, com endpoint, perfil, regra e contexto.

Usuário não autenticado continua sendo encaminhado ao login.

## Cobertura automatizada

`tests/test_rbac_idor.py`:

- verifica acessos permitidos e negados para os dez perfis ativos;
- garante que todas as rotas dos blueprints clínicos possuem política backend;
- valida as regras das abas do prontuário;
- testa escopo de exame, PDF e Prótese;
- testa a resposta `403` e a auditoria de negação.

Os testes existentes de Agenda, Endodontia, exames, arquivos protegidos e
assinaturas complementam a cobertura de escopo.
