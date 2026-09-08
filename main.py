from fastapi import FastAPI
from routers import prs, metrics

app = FastAPI(
    title="GitHub PR Mining API",
    description="Mineração e análise comparativa de PRs: newcomers vs. veteranos",
    version="1.0.0",
)

app.include_router(prs.router)
app.include_router(metrics.router)


@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "ok",
        "docs": "/docs",
        "endpoints": {
            "listar_prs": "GET /prs/{owner}/{repo}?limit=50&state=all",
            "listar_comentarios": "GET /prs/{owner}/{repo}/comments?auto_categorize=true",
            "categorizar_comentario": "PATCH /prs/{owner}/{repo}/comments/categorize",
            "relatorio_comparativo": "GET /metrics/{owner}/{repo}",
        },
    }
