# GitHub PR Mining API

API em Python (FastAPI) para mineração e análise comparativa de Pull Requests no GitHub, focada em comparar **newcomers** (primeira contribuição) vs. **veteranos** (contribuidores recorrentes).

## Funcionalidades

- Extração de PRs via API do GitHub com paginação automática
- Classificação automática de contribuidores (newcomer / veteran)
- Coleta de comentários de review por PR
- Categorização automática de comentários por palavras-chave (pt-BR e inglês)
- Categorização manual via PATCH
- Métricas comparativas: taxa de aceitação, média de comentários, tempo até merge/fechamento

## Estrutura

```
.
├── main.py                  # Ponto de entrada FastAPI
├── config.py                # Configurações via .env
├── github_client.py         # Cliente HTTP para a API do GitHub
├── models.py                # Schemas Pydantic
├── services/
│   ├── extractor.py         # Extração de PRs e comentários
│   ├── classifier.py        # Categorização de comentários
│   └── metrics.py           # Cálculo de métricas comparativas
├── routers/
│   ├── prs.py               # Endpoints de PRs e comentários
│   └── metrics.py           # Endpoint de relatório comparativo
├── requirements.txt
└── .env.example
```

## Configuração

1. Copie `.env.example` para `.env`:
   ```bash
   cp .env.example .env
   ```

2. Gere um token no GitHub em **Settings → Developer settings → Personal access tokens** com escopo `public_repo` e preencha no `.env`:
   ```
   GITHUB_TOKEN=ghp_seu_token_aqui
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. Suba a API:
   ```bash
   uvicorn main:app --reload
   ```

Acesse `http://localhost:8000/docs` para a documentação interativa (Swagger UI).

## Como Usar

Você pode chamar **qualquer endpoint diretamente** (a API faz a extração necessária automaticamente):

### 1. Extração completa e Relatório em 1 clique (Recomendado)
```
GET /metrics/{owner}/{repo}
```
Exemplo: `GET /metrics/fastapi/fastapi` ou `GET /metrics/EbookFoundation/free-programming-books`

A API extrai os PRs, coleta e categoriza os comentários, e devolve o relatório comparativo completo (newcomers vs. veteranos).

---

### 2. Extração individual de PRs
```
GET /prs/{owner}/{repo}?limit=50&state=all
```
Retorna a lista de PRs classificados como `newcomer` ou `veteran`.

---

### 3. Extração e Categorização de comentários
```
GET /prs/{owner}/{repo}/comments?auto_categorize=true
```
Coleta todos os comentários dos PRs e os classifica por palavras-chave.

---

### 3. Categorizar manualmente (opcional)
```
PATCH /prs/{owner}/{repo}/comments/categorize
Body: { "comment_id": 123456, "category": "correcao_tecnica" }
```

Categorias disponíveis:
| Valor | Descrição |
|---|---|
| `correcao_tecnica` | Aponta bug, erro ou problema técnico |
| `explicacao_didatica` | Explica o motivo, sugere boas práticas |
| `rejeicao` | Indica que o PR não será aceito |
| `elogio` | Feedback positivo / aprovação |
| `neutro` | Não se encaixa nas demais |

---

### 4. Gerar relatório comparativo
```
GET /metrics/{owner}/{repo}
```

Retorna métricas lado a lado de newcomers vs. veteranos:
- Total de PRs por grupo
- Taxa de aceitação (%)
- Média de comentários por PR
- Tempo médio até merge / fechamento (horas)
- Distribuição de categorias de comentários

## Critério de classificação de contribuidores

O sistema consulta a API do GitHub para contar o total histórico de PRs do autor naquele repositório. Se o autor tem **1 ou menos PR** no repositório, é classificado como **newcomer**; caso contrário, **veteran**.

## Notas

- Os dados são salvos em disco na pasta `.cache/` com TTL de **24 horas**. Reiniciar o servidor **não perde os dados** — eles são recarregados automaticamente enquanto não expirarem.
- Para forçar nova extração sem esperar o TTL, use `?forcar_atualizacao=true` nos endpoints de PRs e comentários.
- Para consultar quando o cache expira: `GET /prs/{owner}/{repo}/cache/info`
- Para limpar manualmente: `DELETE /prs/{owner}/{repo}/cache`
- Sem token, a API do GitHub limita a 60 req/hora. Com token, o limite é 5000 req/hora.
- Para uma amostra de 30–50 PRs (trabalho de disciplina), o limite sem token pode ser suficiente se o repositório não for muito movimentado.
