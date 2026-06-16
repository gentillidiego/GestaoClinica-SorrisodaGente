# Hardening LGPD - 08/06/2026

Documento de evidência técnica da etapa inicial de hardening LGPD do sistema Gestão Saúde Oral / Programa Sorriso da Gente.

## Resultado Executivo

Status: aprovado com pendências de produção.

Foram reforçadas as rotas que entregam arquivos sensíveis, especialmente PDFs, radiografias e fotos clínicas. A mudança reduz risco de cache indevido, acesso inseguro por nome de arquivo e ausência de auditoria em downloads de PDF.

## Escopo Executado

- Mapeamento de rotas que servem arquivos sensíveis.
- Centralização do envio de arquivos sensíveis.
- Cabeçalhos de privacidade para arquivos clínicos/PDFs.
- Validação segura de arquivos em `pdf_temp`.
- Auditoria de download e tentativa bloqueada de PDF.
- Permissão explícita `patients:view` nas rotas de imagem clínica.
- Testes automatizados para proteção de caminho e cabeçalhos anti-cache.

## Arquivos Ajustados

- `services/sensitive_file_service.py`
- `blueprints/documents.py`
- `blueprints/exams.py`
- `blueprints/patients.py`
- `tests/test_phase1_security.py`

## Proteções Adicionadas

### Arquivos sensíveis sem cache

Downloads de PDFs, fotos clínicas e radiografias agora usam cabeçalhos:

```text
Cache-Control: no-store, no-cache, must-revalidate, private, max-age=0
Pragma: no-cache
Expires: 0
X-Content-Type-Options: nosniff
```

### Caminho seguro para PDFs

O download genérico de PDFs passou a validar o nome do arquivo e bloquear nomes com caminho relativo ou arquivo inexistente antes de servir conteúdo.

### Auditoria de PDF

O sistema agora registra:

- `pdf_downloaded`
- `pdf_download_blocked`

### Imagens clínicas

As rotas de imagem clínica agora exigem, além de login, permissão explícita:

```text
patients:view
```

## Validação Técnica

Testes automatizados:

```text
114 passed
```

Checagem de diff:

```text
git diff --check: sem erros
```

Docker:

```text
docker compose up -d --build: concluído
/health: status=healthy, database=ok
```

Rotas autenticadas verificadas após rebuild:

```text
/dashboard: 200
/patients/list: 200
/reports/institutional: 200
/admin/audit: 200
```

Validação prática de PDF sensível no container:

```text
status 200
Cache-Control no-store, no-cache, must-revalidate, private, max-age=0
Pragma no-cache
Expires 0
X-Content-Type-Options nosniff
Content-Type application/pdf
```

## Pendências de Produção

- Definir política formal de retenção e descarte de arquivos clínicos.
- Definir criptografia em repouso para volume de uploads.
- Avaliar armazenamento externo seguro, se a infraestrutura final exigir.
- Auditar visualização de todos os documentos clínicos gerados, além do download genérico.
- Revisar Nginx/proxy para garantir que `uploads`, `pdf_temp`, `.env` e arquivos internos não sejam servidos diretamente.
- Definir rotina de revisão de logs sensíveis.

## Conclusão

A etapa inicial de hardening LGPD está aprovada. O sistema agora tem uma camada comum para envio de arquivos sensíveis, cabeçalhos de privacidade e proteção básica contra caminhos inseguros no download de PDFs.

Próxima etapa sugerida: Auditoria administrativa.
