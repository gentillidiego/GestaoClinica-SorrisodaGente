# Auditoria de Prontidão para Produção — 19/06/2026

## Resultado Executivo

Decisão recomendada: **NO-GO para produção plena**.

A versão atual da aplicação está funcional, testada e com mecanismos sólidos
de backup, arquivos assíncronos e auditoria. Entretanto, dois riscos impedem a
ampliação segura da operação com dados reais:

1. uma implantação antiga da própria Gestão Clínica continua publicada na VPS,
   inclusive com PostgreSQL acessível pela interface pública;
2. a matriz de permissões existe, mas ainda não é aplicada em todas as rotas
   clínicas do backend.

Até o fechamento dos P0 deste documento, o ambiente deve ser tratado como
homologação técnica controlada.

## Evidências Coletadas

### Aplicação atual

- Branch: `main`.
- Commit auditado: `dc022e9`.
- Remoto: `origin/main` sincronizado.
- Testes: `239 passed`.
- HTTPS `/health`: HTTP 200 e banco `ok`.
- Containers atuais: web, PostgreSQL, Redis, Celery Worker, Celery Beat,
  Postfix/OpenDKIM e backup em execução.
- Certificado Let's Encrypt válido até 29/07/2026.
- `certbot.timer` ativo.
- Fila Postfix vazia.

### Banco atual

- Pacientes: `1`; dados demo: `0`.
- Usuários ativos: `3`.
- Usuários ativos sem e-mail ou data de nascimento completa: `3`.
- Atendimentos: `2`.
- Senhas de triagem: `1`.
- Arquivos de exame de imagem: `1`, sincronizado.
- Arquivos clínico/laboratoriais: `1`, sincronizado.
- Pendências/falhas de sincronização de exames: `0`.
- Configurações e-SUS: `0`.
- Remessas e-SUS: `0`.
- Competência SIGTAP mais recente carregada: `202603`.
- Referências de custo: `32`, todas com metodologia `draft`.

### Backup e continuidade

- Último backup: `20260619_023015`.
- Dump PostgreSQL, uploads e manifesto SHA-256 presentes.
- Cópia externa marcada como concluída.
- Restore isolado executado durante esta auditoria.
- Resultado: `54` tabelas públicas e `1` paciente restaurado.
- Espaço livre na VPS: aproximadamente `52 GB`.

## P0 — Bloqueadores Críticos

### P0.1 Desativar ou isolar a implantação legada

Achado:

- Projeto antigo em `/home/diego/projetos/GestaoClinica`.
- Aplicação antiga: `0.0.0.0:5002`.
- PostgreSQL antigo: `0.0.0.0:5432`.
- As duas portas responderam pelo endereço público.
- Base antiga: `19` pacientes, `8` usuários e `39` atendimentos.
- Nginx ainda possui proxy `/GestaoClinica/` para a aplicação antiga.
- Uptime Kuma monitora a aplicação antiga, não o domínio atual.

Risco:

- superfície pública duplicada;
- código antigo sem as correções atuais;
- banco clínico diretamente exposto à internet;
- possível confusão operacional entre duas bases.

Ação:

1. gerar backup verificado da base e dos arquivos antigos;
2. decidir formalmente se os dados antigos devem ser migrados, arquivados ou
   eliminados;
3. parar e remover a pilha antiga;
4. remover o proxy `/GestaoClinica/`;
5. confirmar externamente que `5002` e `5432` estão fechadas;
6. inventariar também `3025`, `3333`, `5000`, `8000`, `8080`, `8443` e `9443`,
   que estavam alcançáveis publicamente e pertencem a outros serviços da VPS.

Critério de aceite:

- somente `80/443` públicos para a aplicação; SSH restrito conforme política;
- bancos e painéis administrativos acessíveis apenas por rede privada/VPN.

### P0.2 Aplicar RBAC em todas as rotas clínicas

Achado:

- `ROLE_PERMISSIONS` está definida;
- várias rotas usam somente `@login_required`;
- menu oculto não impede acesso direto por URL.

Áreas afetadas:

- listagem, visualização, edição e exclusão de pacientes;
- anamnese;
- criação, alteração, upload e exclusão de exames;
- tratamento e atendimento;
- receituários, atestados e PDFs;
- comprovantes de assinatura;
- Endodontia e Prótese.

Riscos concretos:

- perfil sem `patients:view` consegue abrir prontuário por URL;
- perfil sem permissão de escrita pode alterar registros;
- PDFs clínicos possuem nomes previsíveis e a rota genérica precisa validar
  proprietário/tipo/permissão;
- comprovantes de assinatura são consultados apenas pelo ID do evento.

Ação:

- criar guardas de blueprint ou decorators por leitura/escrita;
- aplicar `patients:view`, `patients:write`, `exams:view`, `exams:write`,
  `documents:generate`, `documents:sign`, `estomatologia:*` e permissões
  específicas;
- retornar 403 ou fluxo seguro, sem revelar existência do registro;
- testar cada perfil ativo com acesso permitido e negado;
- adicionar testes de IDOR para paciente, exame, PDF e assinatura.

Critério de aceite:

- nenhuma rota sensível depende apenas de item oculto na interface.

### P0.3 Atualizar dependências vulneráveis

Auditoria:

```text
pip-audit --no-deps --disable-pip -r requirements.txt
15 vulnerabilidades conhecidas em 5 pacotes
```

Pacotes e versões mínimas indicadas:

| Pacote atual | Atualização mínima indicada |
|---|---|
| Flask 3.0.3 | 3.1.3 |
| Pillow 12.1.1 | 12.2.0 |
| python-dotenv 1.0.1 | 1.2.2 |
| Werkzeug 3.0.3 | 3.1.6 |
| lxml 5.3.1 | 6.1.0 |

Após atualizar:

- executar os 239 testes;
- testar PDF/WeasyPrint;
- testar imagens e derivados WebP;
- validar XML e toda a cadeia XSD;
- reconstruir Docker e repetir smoke test.

### P0.4 Endurecer sessão e respostas HTTP

Achados:

- cookie de sessão sem `Secure` e sem `SameSite`;
- ausência de HSTS, CSP, `X-Frame-Options`, `Referrer-Policy` e
  `Permissions-Policy`;
- logout por GET;
- várias exceções internas são exibidas ao usuário com `str(exc)`.

Ações:

- definir `SESSION_COOKIE_SECURE=true`;
- definir `SESSION_COOKIE_HTTPONLY=true`;
- definir `SESSION_COOKIE_SAMESITE=Lax` ou política formal equivalente;
- adicionar cabeçalhos no Flask/Nginx;
- alterar logout para POST com CSRF;
- registrar detalhe técnico somente no log e exibir mensagem neutra ao usuário.

### P0.5 Formalizar segurança dos arquivos e do Google Drive

Achados:

- exames atuais sincronizados e fallback local funcionando;
- staging e cache possuem permissões restritas;
- rclone falha ao salvar a atualização do token porque o arquivo de
  configuração é um bind mount individual e a troca por rename retorna
  `device or resource busy`;
- validação de upload confia em extensão e MIME informado pelo cliente.

Ações:

- montar um diretório OAuth restrito que permita escrita atômica ou copiar a
  configuração inicial para volume gravável protegido;
- validar assinatura real de PDF e imagens;
- abrir imagens com Pillow e executar verificação antes de aceitar;
- limitar pixels/dimensões para evitar decompression bomb;
- avaliar antivírus para anexos;
- revisar compartilhamentos do Drive;
- formalizar conta institucional, 2FA, recuperação, responsáveis e contrato de
  tratamento de dados. A conta proprietária atual é Gmail e deve ser avaliada
  frente à governança institucional e à LGPD.

## P1 — Antes da Operação Assistida

### Monitoramento

- cadastrar `https://sorrisodagentealagoas.com/health` no Uptime Kuma;
- alertar indisponibilidade, certificado, disco, backup vencido, fila Celery,
  falhas de sincronização e fila Postfix;
- manter histórico fora do próprio servidor quando possível.

### Banco e migrações

- substituir migrações executadas implicitamente no boot por migrações
  versionadas e reversíveis;
- revisar os `39` relacionamentos sem índice de suporte e priorizar os usados
  em consultas frequentes;
- habilitar observação de queries lentas;
- reduzir o risco de conexões: cinco workers, pool mínimo 2 e máximo 20 por
  processo podem alcançar o limite de 100 conexões do PostgreSQL;
- considerar pool menor por worker ou PgBouncer.

### Containers

- executar aplicação com usuário não-root;
- adicionar limites/reservas de CPU e memória;
- aplicar `cap_drop`, `no-new-privileges` e filesystem somente leitura onde
  possível;
- fixar imagens por digest ou rotina de atualização controlada.

### Carga

O teste Locust disponível registrou:

- `2333` requisições;
- `476` falhas;
- todas as falhas observadas foram HTTP 429.

Esse teste demonstra atuação do rate limit, mas não capacidade do fluxo.
Executar novo cenário autenticado com limites de teste adequados, concorrência
esperada, upload, PDF e percentis p95/p99.

### e-SUS, SIGTAP e custos

- preencher identificadores oficiais da instalação;
- confirmar versão LEDI aceita pelo PEC;
- importar XML assistido;
- revisar a competência SIGTAP `202603`;
- homologar ou remover do uso oficial as 32 referências financeiras `draft`.

### Usuários e operação

- completar e-mail e data de nascimento dos três usuários ativos;
- validar recuperação de senha;
- criar usuários reais por perfil;
- executar treinamento e checklist ponta a ponta;
- registrar aceite de Recepção, Clínico, Coordenação e responsável LGPD.

### E-mail

Confirmado:

- SPF publicado;
- DKIM válido;
- PTR aponta para `mail.sorrisodagentealagoas.com`;
- fila Postfix vazia.

Pendente:

- comprovar recebimento em Gmail e Outlook;
- conferir headers SPF/DKIM/DMARC;
- depois de período de observação, avaliar evolução do DMARC de `p=none` para
  `quarantine` e `reject`.

## P2 — Evolução Pós-Entrada

- ambiente de staging separado;
- CI/CD com testes e auditoria de dependências;
- observabilidade centralizada;
- criptografia em repouso;
- Google Workspace ou storage institucional com contrato e governança;
- retificação formal de documentos clínicos;
- visualizador DICOM avançado;
- Portal do Paciente;
- melhorias de BI somente após homologação.

## Sequência Recomendada

1. Backupar e desligar a pilha antiga.
2. Fechar portas públicas não autorizadas.
3. Corrigir autorização backend e IDOR.
4. Atualizar dependências.
5. Endurecer sessão, headers, logout e erros.
6. Corrigir OAuth/rclone e validação de arquivos.
7. Configurar monitoramento.
8. Completar usuários e governança LGPD.
9. Homologar e-SUS/SIGTAP/custos.
10. Rodar carga, QA, treinamento e Go/No-Go.

## Referências Institucionais

- ANPD — Guia de Segurança da Informação:
  https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia-orientativo-sobre-seguranca-da-informacao-para-agentes-de-tratamento-de-pequeno-porte
- ANPD — Dados de saúde como dados pessoais sensíveis:
  https://www.gov.br/anpd/pt-br/assuntos/noticias/diretora-da-anpd-destaca-importancia-da-lgpd-e-o-papel-da-autoridade-na-protecao-de-dados-pessoais-na-saude
- Google Workspace — Data Processing Amendment:
  https://workspace.google.com/terms/09242021/dpa_terms/
- NVD — Flask CVE-2026-27205:
  https://nvd.nist.gov/vuln/detail/CVE-2026-27205
- NVD — python-dotenv CVE-2026-28684:
  https://nvd.nist.gov/vuln/detail/CVE-2026-28684
