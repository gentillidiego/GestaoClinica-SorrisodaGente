# Roteiro de Apresentação: Gestão Saúde Oral — Sorriso da Gente

*(Guia conversacional para apresentação institucional da plataforma.)*

---

## 1. Visão Geral e o Nosso Propósito
"A plataforma reúne a operação do Programa Sorriso da Gente em um único ambiente: triagem municipal, agenda, prontuário odontológico, exames, gestão clínica e indicadores. O objetivo é reduzir tarefas manuais, ampliar a rastreabilidade e deixar as equipes mais disponíveis para o cuidado com o paciente."

## 2. A Evolução do nosso "Coração" (Banco de Dados e Desempenho)
"No começo, o sistema rodava de forma mais simples para validar a ideia. Com o crescimento do uso, passamos a exigir acesso simultâneo de equipes clínicas, recepção, coordenação e apoio técnico, sem travamentos ou telas de erro.
Por isso, fizemos uma evolução de nível empresarial:
- **Saímos do SQLite e adotamos o PostgreSQL:** É o mesmo motor de banco de dados usado por grandes corporações. Ele garante que os dados dos pacientes estejam perfeitamente amarrados e seguros, suportando acesso pesado e simultâneo.
- **Implementamos serviços em segundo plano (Celery e Redis):** A geração de PDFs e outras tarefas pesadas pode ser processada sem bloquear o trabalho do usuário na tela."

## 3. Infraestrutura Blindada (A Magia do Docker)
"Para garantir que o nosso sistema nunca caia e seja fácil de atualizar, nós empacotamos ele no que chamamos de **Contêineres Docker**.
- **O que isso significa na prática?** Significa que o nosso servidor web, o nosso banco de dados e os nossos geradores de PDF rodam em 'caixas' totalmente isoladas e seguras dentro do servidor. 
- **Dados à Prova de Balas:** Nós usamos algo chamado 'Volumes Persistentes'. Mesmo que o servidor precise ser reiniciado do zero ou passe por uma atualização completa de software, os prontuários, documentos e cadastros estão fisicamente isolados em um cofre na máquina, garantindo **Zero Perda de Dados**."

## 4. Atualizações em Tempo Real (Zero Interrupção)
"Outro benefício dessa arquitetura é a atualização controlada. Ajustes solicitados pelas equipes podem ser empacotados e publicados de forma previsível, com validação, backup e possibilidade de retorno seguro."

---

### 💡 Dicas - Como responder a perguntas difíceis da gestão ressaltando a nova arquitetura:

**1. "Com a nova estrutura, o sistema vai ficar mais caro pra manter de pé?"**
> *R:* "De forma alguma! Toda essa nova arquitetura (PostgreSQL, Celery, Redis) é Open Source (gratuita e de código aberto) e foi desenhada para extrair 100% da potência da nuvem que já pagamos hoje. Nós escalamos a tecnologia sem adicionar nem um real a mais de infraestrutura."

**2. "Se dezenas de profissionais utilizarem prontuários ao mesmo tempo, não vai dar conflito?"**
> *R:* "Esse era o nosso grande limite anterior, mas agora **não mais**. O uso do *PostgreSQL* resolve exatamente isso. Ele possui mecanismos automáticos de filas e travas, processando as requisições em paralelo de maneira cirúrgica. Se 100 usuários apertarem para gerar atestados na mesma fração de segundo, o banco vai delegar os PDFs pacificamente e enfileirar as edições sem derrubar a tela inicial."

**3. "E qual é o nível de segurança da informação (LGPD) em tudo isso?"**
> *R:* "Cada contêiner do Docker fala apenas com quem precisa falar. O banco de dados Postgres está trancado em uma rede interna invisível e isolada da internet. A única coisa acessível de fora é a tela de login. Os dados do paciente estão muito mais preservados agora."
