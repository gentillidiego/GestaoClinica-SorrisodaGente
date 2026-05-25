# Nova Análise Geral do Sistema (Rev 3)

Após a última rodada de implementações, realizei uma **auditoria profunda** em toda a base de código do sistema *Gestão Clínica*. Abaixo, consolido o que foi finalizado e os **novos pontos de atenção** identificados, com foco na estabilidade, segurança e manutenbilidade a longo prazo.

---

## ✅ Resumo do que foi 100% resolvido nas sessões anteriores

1. **Atômico/Integridade Relacional**: `PRAGMA foreign_keys = ON` está ativo. As remoções de pacientes ("DELETE FROM patients") engatilham `ON DELETE CASCADE` corretamente.
2. **Performance de Concorrência SQLite**: O banco agora roda com `PRAGMA journal_mode = WAL` e `PRAGMA synchronous = NORMAL`, suportando múltiplos workers no Gunicorn sem `database is locked`.
3. **Limpeza de Escopo (Imports)**: `import json`, `import re`, `import datetime` passados para o topo global, impedindo overhead contínuo no call stack.
4. **Isolamento de Negócios (SRP)**: Toda a lógica do periodontal (cálculos massivos de Estágio/Grau) agora isolada em `services/periodontal_diagnosis.py`.
5. **Dry / DRY Principle (Don't Repeat Yourself)**: Formulário de "exame_fisico" de > 25 campos parametrizado com a tupla `_get_fisico_data()`. Otimizou linhas de `INSERT` e `UPDATE`.
6. **Rate Limiting**: Aplicado no `/login` (`auth.py`). Força-bruta mitigada a nível de app.
7. **Melhorias de Busca**: Cadastro localiza pacientes por CNS, Data de Nascimento e Celular, além do Nome e CPF.
8. **UI/UX e Identidade**: Placeholder Dashboard criado ("Resumo do dia", "Estatísticas Rápida"). "Dentista" substituído por AC Odontologia. Paginação via Client-Side Javascript adicionada em módulos encorpados (Exames, Plano de Tratamento). 

---

## 🚨 NOVOS Itens Identificados para Correção / Ajuste

Ao auditar a implementação do app, pude verificar questões arquiteturais não reportadas antes ou criadas como sequelas de implementações rápidas.

### 🟡 1. Arquitetura: Rate Limiting usando Storage de Memória (memory://)
**Problema:** Em `extensions.py`, o limiter foi declarado com `storage_uri="memory://"`.
Quando usado com Gunicorn ou múltiplos workers (o que justificou ligarmos a WAL mode), a "memória" é local a cada processo. Logo, um ataque de força bruta pode esgotar a cota em um worker, mas acertar livremente outro. Somado a isso, em todo reinício de serviço a contagem global é resetada.
**Como Implementar (Correção Detalhada):**
1. Idealmente trocar para um in-memory server real como **Redis / Memcached**. 
2. Se o contexto for limitar dependências a apenas DB no disco (sem redis), usar um armazenamento compatível que suporte multiprocesso como banco local, ou aceitar a inconsistência em prol da dependência mínima. No cenário atual, considere a biblioteca `limits` aceitando roteamentos baseados no IP.

### 🟡 2. Performance: Armazenamento Base64 de Assinaturas direto no SQLite
**Problema:** Em `patient_tcle`, `prosthesis_pagamentos` e demais tabelas de assinaturas, a imagem capturada em tela (canvas/pad) é varrida inteira via string codificada com `assinatura_paciente_base64 TEXT` dentro da estrutura relacional. A longo prazo, e com milhares de atendimentos, o `clinica.db` estufará absurdamente de tamanho. O SQLite não performará bem com milhares de blobs em texto trafegando em todos os `SELECT *`.
**Como Implementar (Correção Detalhada):**
1. Construir uma rotina que salve a String em um arquivo físico `.png` dentro de uma pasta `static/uploads/signatures/`.
2. No DB, as colunas guardariam o `path/filename.png` e não a string contínua, extraindo apenas nos `INSERT/UPDATES` essa rotina.

### 🟡 3. Arquitetura: Limitação Severa do Paginador Javascript Light
**Problema:** Implementou-se uma paginação CSS via Javascript (que oculta `<tr>` e divs usando `display:none`). Porém o HTML original continuará renderizando e baixando da base TODOS OS EXAMES de todas as datas.
**Como Implementar (Correção Detalhada):**
1. O backend (`PatientService.get_patient_treatments`) deverá aceitar parâmetros `(id, offset=0, limit=10)`.
2. As rotas HTTP entregarão fragmentos HTML. Essa implementação é custosa (3~4h estimadas), por isso, se o número de tratamentos por paciente for razoável (vida não passa de alguns exames), o Client-Side pode ser aceito indefinidamente dependendo do escopo.

### 🟢 4. Segurança: Sessão e CSRF expostos nos Cookies Permanentes
**Problema:** Flask default gerencia sessions armazenadas no cookie do navegador, se as configurações default do Flask Session (Lifetime / HttpOnly) não forem apertadas o risco de Session Fixation existe.
**Como Implementar (Correção Detalhada):**
Em `app.py`:
```python
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=6)
)
```

### 🟢 5. MVC e Clean Code: Rotas cruas em blueprints
**Problema:** Alguns Blueprints (`prosthesis.py` e `endodontia.py`) continuam orquestrando Queries (`execute(INSERT...`) dentro do arquivo roteador.
**Como Implementar (Correção Detalhada):**
1. Evoluir fortemente o `services/patient_service.py` ou criar seus irmãos (`prosthesis_service.py`) para encapsular lógicas de Inclusão, Alteração e Deleção de Entidades complexas. Exemplo: um `def add_treatment(...)` no serviço e o BP chamando `service.add_treatment(request.form)`.

---

> **Recomendação final:** O sistema encontra-se com todas as funções vitais operando num formato altamente resiliente para uma stack local (Flask/SQLite). Dos itens listados, recomendo focar **URGENTEMENTE no Item 2 (Base64 no SQLite)**. Com o tempo, essa string estática encherá exponencialmente os índices do SQLite.
