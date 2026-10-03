# Integração com Power BI

Este guia propõe uma análise simples a partir dos CSVs do sistema.
Não contém um relatório renderizado nem uma publicação no Power BI Service.

## Fontes e granularidade

Exporte `products.csv` e `movements.csv` pelos links da aplicação.
Exemplos sintéticos estão em [samples/](samples/); foram gerados chamando os endpoints em um banco temporário.
Para regerar: `python -m scripts.export_examples`, na raiz, com requirements-dev instalado.

- `products`: um produto por linha, com seu saldo atual e custo cadastrado.
- `movements`: um movimento por linha, com quantidade, tipo, saldo após a operação e custo naquele movimento.

Em **Obter dados → Texto/CSV**, importe os arquivos e renomeie as consultas para `products` e `movements`.
Use UTF-8 e separador vírgula. Em Transformar dados, atribua:

| Tabela | Colunas | Tipo |
|---|---|---|
| products | id, quantity, reorder_point, unit_cost_cents | Número inteiro |
| products | sku, name, category | Texto |
| movements | id, product_id, quantity, balance_after, unit_cost_cents | Número inteiro |
| movements | kind, sku, name, note, idempotency_key | Texto |
| movements | created_at | Data/hora/fuso horário; normalize para UTC antes de remover o fuso |

Relacione `products[id]` **1:N** `movements[product_id]`, direção única de products para movements.
Os arquivos são snapshots independentes; para uma análise consistente, exporte quando não estiver registrando movimentos.
Essa versão não fornece exportação conjunta com isolamento de snapshot entre os dois arquivos.

## Medidas sugeridas

```dax
Unidades Disponíveis = SUM ( products[quantity] )

Valor Cadastrado do Estoque =
SUMX ( products, products[quantity] * products[unit_cost_cents] ) / 100

Produtos para Reposição =
COUNTROWS ( FILTER ( products, products[quantity] <= products[reorder_point] ) )

Entradas =
CALCULATE ( SUM ( movements[quantity] ), movements[kind] = "in" )

Saídas =
CALCULATE ( SUM ( movements[quantity] ), movements[kind] = "out" )

Saldo pelo Histórico = [Entradas] - [Saídas]
```

Sugestão de página: cartões de unidades, valor e reposição; barras de valor por categoria;
tabela de SKU, produto, saldo e ponto de reposição; gráfico de entradas e saídas por data.
Os movimentos de abertura fazem parte da soma; “Saldo pelo Histórico” e o snapshot só devem ser comparados
com o histórico completo e a mesma seleção de produtos. Um filtro de data limita movimentos, mas não representa um saldo histórico do snapshot.

## Conferência

A API `/api/metrics` expõe `units`, `value_cents`, `low_stock` e `empty`.
Compare os indicadores do BI com a mesma exportação e o mesmo filtro de produtos.
Os testes Python conferem saldo, valoração em centavos e reconciliação dos movimentos;
as medidas DAX acima não foram executadas no Power BI Desktop nesta sessão.

Referência: [Microsoft — modelo estrela](https://learn.microsoft.com/en-us/power-bi/guidance/star-schema).
