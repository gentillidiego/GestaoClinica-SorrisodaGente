# Manual rápido - Endodontia E10

Data: 14/06/2026

Status: versão de aceite clínico-operacional do módulo ampliado de Endodontia.

## Objetivo

Orientar o uso do fluxo endodôntico desde a abertura do caso até proservação e orçamento gerencial, mantendo a anamnese vinculada ao prontuário, as assinaturas clínicas e os alertas da Central de Comando.

## Fluxo completo

1. Abrir o prontuário do paciente e acessar a aba Endodontia.
2. Adicionar o elemento dentário em acompanhamento.
3. Conferir o resumo da anamnese vinculada e os alertas sistêmicos.
4. Registrar queixa, exame extraoral/intraoral, periodonto do elemento e diagnóstico AAE.
5. Registrar odontometria canal a canal com CRI, CAI, CRD calculado e CRT sugerido/final.
6. Registrar sessões numeradas com etapa, status, procedimento executado, protocolo biomecânico, irrigação, EDTA, medicação e selamento.
7. Registrar obturação final, controle radiográfico, restauração definitiva e selamento coronário quando aplicável.
8. Vincular imagens endodônticas por etapa clínica, sessão e canal.
9. Acompanhar proservações planejadas de 6, 12, 24 e, quando houver lesão periapical extensa, 48 meses.
10. Registrar avaliação de Strindberg e qualidade restauradora no retorno.
11. Gerar orçamento gerencial por canal quando o diagnóstico liberar tratamento endodôntico.

## Clínicos

Rotina diária:

- Conferir alertas da anamnese antes de registrar protocolo.
- Não avançar sem diagnóstico pulpar e apical estruturados.
- Em `polpa_normal`, registrar justificativa clínica apenas quando houver motivo real para avançar; orçamento endodôntico permanece bloqueado.
- Registrar cada canal separadamente, incluindo justificativa quando o CRT final divergir do CRT sugerido.
- Assinar/validar a sessão conforme fluxo institucional.
- Usar imagens E7 para periapical inicial, odontometria, prova de cone, final de qualidade e proservação.

Campos críticos:

- Diagnóstico pulpar e apical.
- CID-10 sugerido.
- CRI, CAI, CRD, CRT sugerido e CRT final por canal.
- Etapa/status da sessão.
- Solução irrigadora, EDTA, volume, agitação e medicação intracanal.
- Cone principal, cimento, técnica obturadora e radiografia final.
- Restauração definitiva e selamento coronário.
- Critérios de Strindberg na proservação.

Erros comuns:

- Lançar evolução em texto livre sem etapa/status estruturados.
- Usar hipoclorito quando a anamnese indicar alergia compatível com hipoclorito/cloro.
- Usar material eugenólico quando houver alergia a eugenol.
- Registrar CRT final diferente do sugerido sem justificativa.
- Concluir obturação sem registrar restauração definitiva ou plano de restauração.

Checklist de fechamento clínico:

- Diagnóstico AAE completo.
- Odontometria por canal revisada.
- Sessões assinadas/validadas.
- Obturação com controle radiográfico.
- Restauração definitiva registrada ou pendência restauradora visível.
- Imagens essenciais vinculadas.
- Proservações geradas e acompanhadas.
- Orçamento gerencial gerado quando aplicável.

## Recepção

Rotina diária:

- Acompanhar a Central de Comando.
- Identificar retornos endodônticos vencidos.
- Identificar proservações endodônticas vencidas.
- Acionar paciente conforme protocolo operacional da clínica.
- Confirmar se casos obturados sem restauração definitiva precisam de agendamento restaurador.

Alertas que a recepção resolve:

- Retorno endodôntico vencido.
- Proservação endodôntica vencida.
- Caso obturado aguardando restauração definitiva.
- Pendência de assinatura do paciente, quando o fluxo institucional exigir coleta.

Erros comuns:

- Confundir retorno de sessão com proservação longitudinal.
- Encerrar acompanhamento só porque a obturação foi feita, sem conferir restauração definitiva.
- Não priorizar casos com proservação vencida e resultado anterior em dúvida/insucesso.

Checklist de fechamento operacional:

- Retornos vencidos revisados.
- Proservações vencidas revisadas.
- Pacientes acionados ou reagendados.
- Pendências restauradoras encaminhadas para agenda.
- Pendências sem resolução reportadas à Coordenação.

## Coordenação

Rotina diária:

- Revisar pendências clínicas da Central.
- Conferir gargalos de Endodontia: retornos vencidos, restauração pendente, proservação vencida e retratamento necessário.
- Validar se o orçamento gerencial está sendo usado como estimativa, sem substituir faturamento oficial homologado.
- Monitorar adesão ao preenchimento estruturado pelos profissionais.

Indicadores úteis:

- Casos em andamento.
- Casos aguardando retorno.
- Casos obturados aguardando restauração.
- Proservações vencidas.
- Resultados de Strindberg: sucesso, dúvida e insucesso.
- Retratamentos.
- Orçamentos por canal e complexidade.

Erros comuns:

- Tratar valores TUSS/SIGTAP como faturamento homologado sem validação institucional.
- Ignorar proservação após resolução restauradora.
- Não auditar justificativas de `polpa_normal` ou override de CRT.

Checklist de aceite clínico-operacional:

- Caso novo abre sem quebrar casos antigos.
- Diagnóstico estruturado bloqueia/permite avanço corretamente.
- Alergias críticas bloqueiam escolhas incompatíveis.
- Odontometria calcula Bregman e registra override.
- Sessões alimentam status e Central.
- Obturação sem restauração gera pendência restauradora.
- Imagens ficam na ficha e na Biblioteca Visual.
- Proservações aparecem no tempo correto.
- Strindberg altera status para retratamento necessário quando há insucesso.
- Orçamento por canal diferencia tratamento e retratamento.

## Pendências fora do MVP

- TCLE endodôntico específico.
- Assinatura digital ICP-Brasil/Gov.br.
- WhatsApp/API real para lembretes.
- Integração automática com agenda.
- Visualizador DICOM avançado com medição/anotação.
- Homologação oficial de faturamento TUSS/SIGTAP/e-SUS.
