# Registro de alterações

Na verificação final, a rodada conjunta de navegador apresentou requisições pendentes com access log.
O servidor de teste passou a usar `--no-access-log`; os dois fluxos passaram novamente.
Também foi verificada a recusa de schema desconhecido sem substituição do banco.

## 2026-10-02 — Primeira versão funcional

- Aplicação de portfólio stockflow com API Python, React, SQLite, dados sintéticos e documentação de requisitos.
- Testes das regras, integração HTTP, persistência e fluxos de navegador.
- Container com usuário sem privilégios e CI para testes, build e verificação HTTP da imagem.
- CSVs de exemplo gerados pela API e material de integração com Power BI.
- Avisos conhecidos: TestClient/Starlette informa depreciação de httpx; não é falha de teste.
- O primeiro teste móvel encontrou overflow de 404 px em uma tela de 390 px; duas tentativas localizaram o rótulo acessível da tabela, cujo contexto de posicionamento foi corrigido. Resultado final em docs/VERIFICACAO.md.

As verificações finais e limites estão em docs/VERIFICACAO.md.
