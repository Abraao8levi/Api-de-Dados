# 🚀 GitHub PR Mining API

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.111.0-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Pydantic-v2-E92063?style=for-the-badge&logo=pydantic&logoColor=white" alt="Pydantic" />
  <img src="https://img.shields.io/badge/HTTPX-Async-1f425f?style=for-the-badge" alt="HTTPX" />
  <img src="https://img.shields.io/badge/Uvicorn-ASGI-4051B5?style=for-the-badge&logo=gunicorn&logoColor=white" alt="Uvicorn" />
</p>

API REST assíncrona para **Mineração de Repositórios de Software (MSR)** via GitHub REST API v3. A solução extrai Pull Requests, classifica o perfil de contribuidores (*novatos vs. veteranos*), minera comentários de code review com classificação semântica e gera métricas quantitativas comparativas de produtividade e aceitação.

---

## 🛠️ Tecnologias Utilizadas

| Tecnologia | Versão | Função na Arquitetura |
|---|---|---|
| **Python** | `3.11+` | Linguagem base para processamento de dados e operações assíncronas. |
| **FastAPI** | `0.111.0` | Framework web assíncrono de alta performance com suporte nativo a OpenAPI/Swagger. |
| **Uvicorn** | `0.30.1` | Servidor ASGI leve para execução do loop de eventos assíncrono. |
| **HTTPX** | `0.27.0` | Cliente HTTP assíncrono com suporte a pool de conexões persistentes (*keep-alive*) e controle de concorrência. |
| **Pydantic v2** | `2.7.4` | Validação estrita de contratos de dados, serialização JSON e coerção de tipos em alta velocidade via Rust core. |
| **Pydantic Settings** | `2.3.4` | Gestão centralizada de configurações e variáveis de ambiente via `.env`. |
| **python-dateutil** | `2.9.0` | Parsing e manipulação de timestamps ISO 8601 com timezone awareness UTC. |
| **Pandas** | `2.2.2` | Suporte à agregação analítica e exportação tabular de dados minerados. |

---

## 🏛️ Arquitetura & Decisões de Engenharia

A aplicação foi estruturada seguindo princípios de **Clean Architecture**, desacoplamento por camadas e resiliência contra limites de taxa (*Rate Limiting*):

```
┌─────────────────────────────────────────────────────────────┐
│                       FastAPI Routers                       │
│           (/prs, /metrics, /comments, /cache)               │
└──────────────────────────────┬──────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
   ┌─────────────────────────┐   ┌───────────────────────────┐
   │     Services Layer      │   │       Cache Manager       │
   │  (Extractor/Classifier) │   │ (L1: Memória / L2: Disco) │
   └────────────┬────────────┘   └───────────────────────────┘
                │
                ▼
   ┌─────────────────────────┐
   │    GitHub HTTP Client   │
   │ (Pool de Conexão/Semáf.)│
   └────────────┬────────────┘
                │
                ▼
      GitHub REST API v3
```

### Destaques Técnicos:
1. **Pool de Conexões e Concorrência Controlada:**
   * Utilização de `httpx.AsyncClient` compartilhado evitando handshake SSL repetitivo.
   * Controle de requisições simultâneas via `asyncio.Semaphore(10)` para evitar bloqueios por *Secondary Rate Limit* do GitHub.
2. **Estratégia de Cache de 2 Camadas (L1 RAM + L2 Disco com TTL):**
   * **L1 (In-Memory):** Acesso instantâneo para requisições repetidas na mesma sessão.
   * **L2 (Persistente em Disco):** Cache em `.cache/{owner}__{repo}.json` com TTL de 24 horas. O servidor pode ser reiniciado sem necessidade de refazer extrações custosas.
3. **Resiliência e Higienização de Parâmetros:**
   * Parser inteligente de repositórios que aceita tanto nomes simples (`fastapi`, `fastapi`) quanto URLs completas (`https://github.com/fastapi/fastapi`).
4. **Auto-Extração em Cascata:**
   * Qualquer endpoint (`/comments` ou `/metrics`) pode ser acionado diretamente sem necessidade de executar passos intermediários manuais.

---

## 📊 Metodologia de Mineração & Métricas

### 1. Classificação de Contribuidores
* **Novatos (*Newcomers*):** Autores identificados com relação `FIRST_TIME_CONTRIBUTOR`, `FIRST_TIMER` ou `NONE` no repositório.
* **Veteranos (*Veterans*):** Autores identificados como `CONTRIBUTOR`, `MEMBER`, `COLLABORATOR` ou `OWNER`.

### 2. Categorização de Comentários de Review
Os comentários são classificados automaticamente via padrões semânticos bilíngues (pt-BR / en) ou manualmente via endpoint `PATCH`:
* `correcao_tecnica`: Aponta bugs, falhas de tipos, vazamentos de memória ou problemas de arquitetura.
* `explicacao_didatica`: Sugestões construtivas, justificativas conceituais e padrões de projeto.
* `rejeicao`: Menções a fechamento, escopo inválido ou duplicação.
* `elogio`: Aprovação, validação positiva e agradecimentos.
* `neutro`: Comentários operacionais gerais.

### 3. Métricas Quantitativas Comparativas
* **Taxa de Aceitação (%):** Percentual de PRs que resultaram em merge em relação ao total.
* **Média de Comentários:** Densidade de interação e discussões por PR.
* **Tempo Médio de Resolução (horas):** Tempo decorrido entre criação e merge/fechamento.
* **Distribuição de Feedback:** Proporção de cada categoria de comentário recebida por novatos vs. veteranos.

---

## 📁 Estrutura do Projeto

```
.
├── main.py                  # Ponto de entrada FastAPI e registro de rotas
├── config.py                # Configurações com Pydantic Settings
├── github_client.py         # Cliente HTTP assíncrono com pool e paginação
├── cache.py                 # Gerenciador de cache com persistência e TTL
├── models.py                # Schemas de dados e validações Pydantic
├── routers/
│   ├── prs.py               # Endpoints de extração de PRs e comentários
│   └── metrics.py           # Endpoints de relatórios analíticos
├── services/
│   ├── extractor.py         # Extração de dados da API do GitHub
│   ├── classifier.py        # Motor de categorização de comentários
│   └── metrics.py           # Agregação e cálculo de métricas
├── requirements.txt         # Dependências do projeto
├── .env.example             # Template de variáveis de ambiente
└── .gitignore               # Proteção de credenciais e caches
```

---

## ⚙️ Instalação e Execução

### 1. Clonar o Repositório
```bash
git clone https://github.com/Abraao8levi/Api-de-Dados.git
cd Api-de-Dados
```

### 2. Criar e Ativar Ambiente Virtual
```bash
python -m venv venv
# Linux / MacOS:
source venv/bin/activate
# Windows:
.\venv\Scripts\activate
```

### 3. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 4. Configurar Variáveis de Ambiente
Copie o arquivo de exemplo e insira seu Token Pessoal do GitHub:
```bash
cp .env.example .env
```
Edite o arquivo `.env`:
```env
GITHUB_TOKEN=ghp_seu_token_aqui
```

### 5. Iniciar o Servidor
```bash
uvicorn main:app --reload
```

Acesse a documentação interativa:
* **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 📌 Exemplos de Uso da API

### Relatório Comparativo Completo (1 Clique)
```http
GET /metrics/{owner}/{repo}
```
**Exemplo:** `GET /metrics/EbookFoundation/free-programming-books`

```json
{
  "repository": "EbookFoundation/free-programming-books",
  "sample_size": 50,
  "newcomers": {
    "contributor_type": "newcomer",
    "total_prs": 20,
    "merged_prs": 0,
    "closed_without_merge": 11,
    "open_prs": 9,
    "acceptance_rate": 0.0,
    "avg_comments_per_pr": 0.0,
    "avg_hours_to_close": 32.1,
    "avg_hours_to_merge": null,
    "comment_categories": {}
  },
  "veterans": {
    "contributor_type": "veteran",
    "total_prs": 30,
    "merged_prs": 23,
    "closed_without_merge": 4,
    "open_prs": 3,
    "acceptance_rate": 76.67,
    "avg_comments_per_pr": 0.0,
    "avg_hours_to_close": 48.86,
    "avg_hours_to_merge": 56.09,
    "comment_categories": {}
  },
  "total_review_comments": 0,
  "comment_category_distribution": {}
}
```

### Gestão de Cache
* Consultar status/expiração: `GET /prs/{owner}/{repo}/cache/info`
* Forçar invalidação: `DELETE /prs/{owner}/{repo}/cache`
