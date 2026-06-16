# QA e aceite - Endodontia E10

Data: 14/06/2026

Status: aprovado tecnicamente para aceite clínico-operacional.

## Escopo validado

- Diagnóstico endodôntico estruturado AAE.
- Odontometria canal a canal com Bregman e CRT sugerido/final.
- Bloqueios por alergia a hipoclorito/cloro e eugenol.
- Sessões estruturadas, status do tratamento e retornos vencidos.
- Protocolo biomecânico, irrigação, EDTA e medicação intracanal.
- Obturação final, restauração definitiva e pendência restauradora.
- Upload protegido de imagens endodônticas e integração com Biblioteca Visual.
- Proservação 6/12/24/48 meses e critérios de Strindberg.
- Orçamento gerencial por canal com TUSS/SIGTAP de referência.
- Central de Comando com retornos, proservações e pendências restauradoras.

## Evidências automatizadas

Comandos executados:

```bash
.venv/bin/pytest -q tests/test_phase4_endodontia.py tests/test_phase2_command_center.py
.venv/bin/pytest -q
python3 -m compileall blueprints/endodontia.py blueprints/patients.py services/endodontia_service.py services/visual_media_service.py services/command_center_service.py database.py
git diff --check
docker compose up -d --build
curl -s http://localhost:5003/health
docker compose ps
```

Resultados:

- Testes focados E8/E9/E10/Central: `75 passed`.
- Suíte completa: `168 passed`.
- `compileall`: sem erros.
- `git diff --check`: sem erros.
- Docker: web, PostgreSQL, Redis, Celery Worker e Celery Beat em execução.
- `/health`: `status=healthy`, `database=ok`.

## Templates carregados no container

- `endodontia/followup.html`
- `patients/includes/_tab_endodontia.html`
- `patients/includes/_tab_visual.html`
- `command_center.html`

## Rotas críticas resolvidas no container

- `/endodontia/followup/1`
- `/endodontia/followup/save_details/1`
- `/endodontia/followup/add/1`
- `/endodontia/proservation/1/evaluate`
- `/endodontia/followup/1/budget/generate`
- `/endodontia/followup/1/images/upload`
- `/endodontia/image/1`
- `/agenda/`

## Testes E10 adicionados

- Mapa de rotas críticas do blueprint de Endodontia.
- Fluxo clínico em nível de serviço:
  - diagnóstico estruturado;
  - odontometria;
  - preparo completo;
  - medicação intracanal;
  - obturação;
  - proservação;
  - Strindberg;
  - orçamento por canal.

## Checklist para aceite clínico humano

- [ ] Clínico responsável revisou diagnóstico AAE, campos obrigatórios e nomenclatura.
- [ ] Clínico responsável executou um caso sintético no navegador em Docker.
- [ ] Recepção validou leitura das pendências na Central.
- [ ] Coordenação validou indicadores e limites do orçamento gerencial.
- [ ] Equipe confirmou que TUSS/SIGTAP está marcado como referência/estimativa, não faturamento homologado.
- [ ] Equipe confirmou pendências institucionais antes de implantação oficial.

## Pendências institucionais fora do MVP

- TCLE endodôntico específico.
- Assinatura digital ICP-Brasil/Gov.br.
- WhatsApp/API real para lembretes.
- Integração automática com agenda.
- Visualizador DICOM avançado.
- Homologação oficial de faturamento TUSS/SIGTAP/e-SUS.
- Retificação formal pós-assinatura com cadeia completa de versões.
