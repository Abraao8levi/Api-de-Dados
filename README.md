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

## Fluxo de uso recomendado

### 1. Extrair os PRs
```
GET /prs/{owner}/{repo}?limit=50&state=all
```
Exemplo: `GET /prs/facebook/react?limit=50`

Retorna a lista de PRs com classificação `newcomer` ou `veteran` já aplicada.

---

### 2. Coletar comentários de review
```
GET /prs/{owner}/{repo}/comments?auto_categorize=true
```

Com `auto_categorize=true`, os comentários já são categorizados automaticamente por palavras-chave.

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

- Os dados ficam em cache em memória por sessão. Reiniciar o servidor limpa o cache.
- Sem token, a API do GitHub limita a 60 req/hora. Com token, o limite é 5000 req/hora.
- Para uma amostra de 30–50 PRs (trabalho de disciplina), o limite sem token pode ser suficiente se o repositório não for muito movimentado.
