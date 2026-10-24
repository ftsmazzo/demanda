# Demanda

Plataforma multi-tenant que "escuta" o WhatsApp de uma empresa de serviços (piloto: uma contabilidade), transforma as mensagens em tarefas, compromissos e pendências por setor, e mantém um agente de IA que fala só com os donos sobre o que está parado e o andamento do escritório.

## Documentação

- [PRD](docs/PRD.md): o quê e por quê (v0.2, recorte de MVP).
- [TRD](docs/TRD.md): como construir (v0.1, stack, modelo de dados, ADRs, spikes).
- [Simulação do tenant de teste](docs/simulacao-tenant-teste.md): caso completo usado como alvo e base de testes.

## Estado atual

Scaffold mínimo: API FastAPI com `/health`. Próximo passo: Spike 1 (ingestão do WhatsApp via Evolution), conforme o TRD.

## Rodar localmente

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Teste e qualidade:

```bash
cd backend
pytest
ruff check .
ruff format --check .
```

## Deploy

Imagem a partir do `Dockerfile` na raiz (porta 8000, healthcheck em `/health`), pensada para o EasyPanel com serviços isolados (app, worker, banco, Evolution). Variáveis em `.env.example`.
