# Evidências de verificação

Verificação local em 02/10/2026, Windows, Python 3.14 e Node.js 24.

| Verificação | Resultado |
|---|---|
| Pytest: integração HTTP e regras | 11 cenários passaram. |
| Concorrência | Duas saídas disputando saldo e duas entradas com a mesma chave verificadas. |
| Ruff: análise e formatação | Sem erros após correção dos contextos de teste. |
| TypeScript e Prettier | Verificação passou. |
| Build React | Compilação de produção passou. |
| Playwright com API real | 2 fluxos passaram: cadastro/movimentação/persistência e filtros/layout de 390 px. |
| Aplicação compilada servida pela API | Página, health, OpenAPI, seed e CSV verificados por `scripts/smoke.py`. |
| Capturas de tela | `overview.png` e `mobile.png`, obtidas da aplicação compilada. |

Os testes usam arquivos SQLite temporários ou `.data/e2e.db`. O teste de schema incompatível
verifica recusa de uma versão desconhecida sem substituir o arquivo original.
O contrato em `openapi.json` e os CSVs em `samples/` são gerados pela API com `scripts/export_examples.py`.

O defeito de largura no celular, sua medição e correção estão registrados em `ANALISE.md`.
Na rodada conjunta de navegador, requisições ficaram pendentes com o log de acesso do servidor
no processo de teste. Uvicorn passou a usar `--no-access-log` nesse processo;
os mesmos fluxos passaram em nova execução conjunta, incluindo a saída anteriormente pendente.

O TestClient de Starlette emite aviso de depreciação sobre httpx. Os testes passam com as versões fixadas.
O Docker Desktop não estava disponível localmente: build e smoke do container são etapas do
[GitHub Actions](https://github.com/JVCSampaio/stockflow/actions/workflows/ci.yml), cujo resultado deve ser consultado na execução correspondente.
Não foram executados testes de carga, auditoria de acessibilidade ou validação no Power BI Desktop.
