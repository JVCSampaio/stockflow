import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, dateTime, money } from './api'

type Product = {
  id: number
  sku: string
  name: string
  category: string
  unit_cost_cents: number
  reorder_point: number
  quantity: number
  low_stock: boolean
}
type Movement = {
  id: number
  product_id: number
  sku: string
  name: string
  kind: 'in' | 'out'
  quantity: number
  balance_after: number
  note: string
  created_at: string
}
type Metrics = {
  products: number
  units: number
  value_cents: number
  low_stock: number
  empty: number
}

export default function App() {
  const [products, setProducts] = useState<Product[]>([])
  const [movements, setMovements] = useState<Movement[]>([])
  const [total, setTotal] = useState(0)
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [query, setQuery] = useState('')
  const [onlyLow, setOnlyLow] = useState(false)
  const [page, setPage] = useState(0)
  const [refresh, setRefresh] = useState(0)
  const [selected, setSelected] = useState<Product | null>(null)
  const [newProduct, setNewProduct] = useState(false)
  const [kind, setKind] = useState<'in' | 'out'>('in')
  const [quantity, setQuantity] = useState('1')
  const [note, setNote] = useState('')
  const [operation, setOperation] = useState<{ signature: string; key: string } | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const reload = () => setRefresh((n) => n + 1)

  useEffect(() => {
    let active = true
    setLoading(true)
    const params = new URLSearchParams({
      q: query,
      low_stock: String(onlyLow),
      limit: '8',
      offset: String(page * 8),
    })
    Promise.all([
      api<{ items: Product[]; total: number }>(`/products?${params}`),
      api<Metrics>('/metrics'),
      api<{ items: Movement[] }>('/movements'),
    ])
      .then(([list, m, history]) => {
        if (active) {
          setProducts(list.items)
          setTotal(list.total)
          setMetrics(m)
          setMovements(history.items)
        }
      })
      .catch((e) => {
        if (active) setError(e.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [query, onlyLow, page, refresh])

  useEffect(() => {
    let active = true
    if (selected)
      api<Product>(`/products/${selected.id}`)
        .then((p) => {
          if (active) setSelected(p)
        })
        .catch((e) => {
          if (active) setError(e.message)
        })
    return () => {
      active = false
    }
    // O saldo é atualizado após cada movimento sem apagar os campos de uma tentativa pendente.
  }, [selected?.id, refresh])

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = Object.fromEntries(new FormData(event.currentTarget))
    const cost = String(fields.cost).trim()
    if (!/^\d+(\.\d{1,2})?$/.test(cost)) {
      setError('Informe um custo válido com até duas casas decimais.')
      return
    }
    const [whole, fraction = ''] = cost.split('.')
    const payload = {
      sku: fields.sku,
      name: fields.name,
      category: fields.category,
      unit_cost_cents: Number(whole) * 100 + Number(fraction.padEnd(2, '0')),
      reorder_point: Number(fields.reorder_point),
    }
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const product = await api<Product>('/products', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setSelected(product)
      setNewProduct(false)
      setQuery('')
      setOnlyLow(false)
      setPage(0)
      setOperation(null)
      setNotice('Produto cadastrado. Registre uma entrada para adicionar saldo.')
      reload()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function move(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selected) return
    const fields = { product_id: selected.id, kind, quantity: Number(quantity), note: note.trim() }
    const signature = JSON.stringify(fields)
    // Uma falha de rede mantém a chave. Reenviar os mesmos campos não repete a saída ou entrada.
    const key = operation?.signature === signature ? operation.key : crypto.randomUUID()
    setOperation({ signature, key })
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await api('/movements', {
        method: 'POST',
        body: JSON.stringify({ ...fields, idempotency_key: key }),
      })
      setNotice(
        `${kind === 'in' ? 'Entrada' : 'Saída'} registrada: ${quantity} unidade(s) de ${selected.sku}.`,
      )
      setNote('')
      setQuantity('1')
      setOperation(null)
      reload()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="workspace stock-theme">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="StockFlow início">
          <span className="brand-icon">▦</span>
          <span>
            StockFlow<small>CONTROLE DE ESTOQUE</small>
          </span>
        </a>
        <div className="nav-label">WORKSPACE</div>
        <div className="nav-item active">
          <span>▤</span> Inventário
        </div>
        <a className="nav-item" href="#history">
          <span>↔</span> Movimentações
        </a>
        <a className="nav-item" href="/api/export/products.csv">
          <span>↓</span> Exportar inventário
        </a>
        <a className="nav-item" href="/docs" target="_blank" rel="noreferrer">
          <span>⌘</span> Documentação da API
        </a>
        <div className="sidebar-foot">
          <span className="avatar">JS</span>
          <div>
            John Sampaio<small>Projeto de portfólio</small>
          </div>
        </div>
      </aside>
      <div className="content">
        <header className="topbar">
          <span>
            Operações <span className="muted">/</span> Inventário
          </span>
          <span className="demo-tag">
            <i /> Dados de demonstração
          </span>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <p className="eyebrow">DISPONIBILIDADE & RASTREABILIDADE</p>
              <h1>Cada movimento conta.</h1>
              <p className="muted">
                Acompanhe o saldo, antecipe a reposição e mantenha o histórico.
              </p>
            </div>
            <button className="primary" onClick={() => setNewProduct(!newProduct)}>
              {newProduct ? 'Cancelar cadastro' : '+ Novo produto'}
            </button>
          </div>
          {error && (
            <div className="alert error" role="alert">
              {error}
              <button
                onClick={() => {
                  setError('')
                  reload()
                }}
              >
                Atualizar saldo
              </button>
            </div>
          )}
          {notice && (
            <div className="alert success" role="status">
              {notice}
            </div>
          )}
          <div className="metrics">
            <Metric
              label="VALOR DO ESTOQUE"
              value={metrics ? money(metrics.value_cents) : '—'}
              hint="Custo unitário cadastrado × saldo"
            />
            <Metric
              label="UNIDADES DISPONÍVEIS"
              value={metrics?.units ?? '—'}
              hint={`${metrics?.products ?? '—'} produtos cadastrados`}
            />
            <Metric
              label="PRECISAM DE REPOSIÇÃO"
              value={metrics?.low_stock ?? '—'}
              hint="Saldo no ponto de reposição ou abaixo"
              warning
            />
            <Metric
              label="SEM ESTOQUE"
              value={metrics?.empty ?? '—'}
              hint="Produtos com saldo zero"
            />
          </div>
          {newProduct && (
            <section className="panel form-panel">
              <div className="panel-heading">
                <h2>Cadastrar produto</h2>
                <span>O saldo inicial será zero</span>
              </div>
              <form className="form-grid" onSubmit={create}>
                <label>
                  SKU
                  <input
                    name="sku"
                    required
                    minLength={3}
                    maxLength={25}
                    pattern="[A-Za-z0-9][A-Za-z0-9_-]{2,24}"
                    placeholder="EX.: MON-27"
                  />
                </label>
                <label>
                  Nome do produto
                  <input
                    name="name"
                    required
                    minLength={3}
                    maxLength={120}
                    placeholder="Descrição do item"
                  />
                </label>
                <label>
                  Categoria
                  <select name="category">
                    {['Hardware', 'Periféricos', 'Infraestrutura', 'Papelaria'].map((c) => (
                      <option key={c}>{c}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Custo unitário (R$)
                  <input
                    name="cost"
                    type="number"
                    required
                    min="0"
                    max="1000000"
                    step="0.01"
                    placeholder="0.00"
                  />
                </label>
                <label>
                  Ponto de reposição
                  <input
                    name="reorder_point"
                    type="number"
                    required
                    min="0"
                    max="1000000"
                    step="1"
                    defaultValue="5"
                  />
                </label>
                <div className="form-actions span-2">
                  <span className="muted">O SKU identifica o produto e precisa ser único.</span>
                  <button className="primary" disabled={busy}>
                    {busy ? 'Salvando…' : 'Cadastrar produto'}
                  </button>
                </div>
              </form>
            </section>
          )}
          <div className="split-layout inventory-layout">
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Inventário</h2>
                  <span>{total} produto(s) no filtro</span>
                </div>
                <button className="ghost" onClick={reload}>
                  ↻ Atualizar
                </button>
              </div>
              <div className="filters">
                <label className="search-label">
                  <span className="sr-only">Buscar produtos</span>
                  <input
                    placeholder="Buscar nome ou SKU…"
                    value={query}
                    onChange={(e) => {
                      setQuery(e.target.value)
                      setPage(0)
                    }}
                  />
                </label>
                <label className="check-label">
                  <input
                    type="checkbox"
                    checked={onlyLow}
                    onChange={(e) => {
                      setOnlyLow(e.target.checked)
                      setPage(0)
                    }}
                  />{' '}
                  Apenas reposição
                </label>
              </div>
              {loading ? (
                <div className="empty">Carregando inventário…</div>
              ) : products.length === 0 ? (
                <div className="empty">
                  Nenhum produto encontrado. Ajuste a busca ou cadastre um novo item.
                </div>
              ) : (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>PRODUTO</th>
                        <th>SALDO</th>
                        <th>CUSTO</th>
                        <th>DISPONIBILIDADE</th>
                        <th>
                          <span className="sr-only">Ações</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {products.map((p) => (
                        <tr key={p.id} className={selected?.id === p.id ? 'selected' : ''}>
                          <td>
                            <strong>{p.name}</strong>
                            <small>
                              {p.sku} · {p.category}
                            </small>
                          </td>
                          <td>
                            <span className="quantity">{p.quantity}</span>
                            <small>mín. {p.reorder_point}</small>
                          </td>
                          <td>{money(p.unit_cost_cents)}</td>
                          <td>
                            <span
                              className={`badge ${p.quantity === 0 ? 'urgent' : p.low_stock ? 'high' : 'healthy'}`}
                            >
                              {p.quantity === 0
                                ? 'Sem estoque'
                                : p.low_stock
                                  ? 'Repor'
                                  : 'Disponível'}
                            </span>
                            <div className="stock-bar">
                              <i
                                style={{
                                  width: `${Math.min(100, (p.quantity / Math.max(1, p.reorder_point * 3)) * 100)}%`,
                                }}
                              />
                            </div>
                          </td>
                          <td>
                            <button
                              className="secondary compact"
                              aria-label={`Movimentar ${p.sku}`}
                              onClick={() => {
                                setSelected(p)
                                setNote('')
                                setQuantity('1')
                                setOperation(null)
                              }}
                            >
                              Movimentar
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="pagination">
                <button
                  className="ghost"
                  disabled={page === 0 || loading}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Anterior
                </button>
                <span>Página {page + 1}</span>
                <button
                  className="ghost"
                  disabled={(page + 1) * 8 >= total || loading}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Próxima
                </button>
              </div>
            </section>
            <section className="panel detail" aria-label="Registrar movimentação">
              {!selected ? (
                <div className="detail-placeholder">
                  <span className="placeholder-icon">↔</span>
                  <h2>Um histórico confiável começa aqui.</h2>
                  <p>
                    Selecione um produto para registrar uma entrada ou saída. O saldo e o histórico
                    são atualizados juntos.
                  </p>
                  <div className="workflow-mini">
                    Entrada <span>→</span> Saldo <span>→</span> Saída
                  </div>
                </div>
              ) : (
                <>
                  <div className="panel-heading">
                    <div>
                      <h2>Registrar movimento</h2>
                      <span>{selected.sku}</span>
                    </div>
                    <span className="badge healthy">{selected.quantity} disponíveis</span>
                  </div>
                  <form className="detail-body" onSubmit={move}>
                    <h3>{selected.name}</h3>
                    <div className="segmented">
                      <button
                        type="button"
                        className={kind === 'in' ? 'active' : ''}
                        onClick={() => setKind('in')}
                      >
                        ↙ Entrada
                      </button>
                      <button
                        type="button"
                        className={kind === 'out' ? 'active' : ''}
                        onClick={() => setKind('out')}
                      >
                        ↗ Saída
                      </button>
                    </div>
                    <label>
                      Quantidade
                      <input
                        type="number"
                        required
                        min="1"
                        max="1000000"
                        step="1"
                        value={quantity}
                        onChange={(e) => setQuantity(e.target.value)}
                      />
                    </label>
                    <label>
                      Motivo do movimento
                      <textarea
                        required
                        minLength={5}
                        maxLength={500}
                        rows={3}
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="Recebimento, solicitação interna ou ajuste justificado…"
                      />
                    </label>
                    <p className="muted small">
                      {kind === 'out'
                        ? 'Saídas acima do saldo serão recusadas.'
                        : 'Informe a quantidade recebida para atualizar o saldo.'}
                    </p>
                    <button className="primary full" disabled={busy}>
                      {busy ? 'Registrando…' : 'Confirmar movimento'}
                    </button>
                  </form>
                </>
              )}
            </section>
          </div>
          <section className="panel movement-panel" id="history">
            <div className="panel-heading">
              <div>
                <h2>Últimas movimentações</h2>
                <span>Registro permanente de entradas e saídas · últimos 20 registros</span>
              </div>
              <a className="secondary compact" href="/api/export/movements.csv">
                ↓ Exportar CSV
              </a>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>OPERAÇÃO</th>
                    <th>PRODUTO</th>
                    <th>QUANTIDADE</th>
                    <th>SALDO APÓS</th>
                    <th>MOTIVO</th>
                    <th>DATA</th>
                  </tr>
                </thead>
                <tbody>
                  {movements.map((m) => (
                    <tr key={m.id}>
                      <td>
                        <span className={`badge ${m.kind === 'in' ? 'healthy' : 'normal'}`}>
                          {m.kind === 'in' ? '↙ Entrada' : '↗ Saída'}
                        </span>
                      </td>
                      <td>
                        <strong>{m.name}</strong>
                        <small>{m.sku}</small>
                      </td>
                      <td className={m.kind === 'in' ? 'positive' : ''}>
                        {m.kind === 'in' ? '+' : '−'}
                        {m.quantity}
                      </td>
                      <td>{m.balance_after}</td>
                      <td>{m.note}</td>
                      <td className="nowrap">{dateTime(m.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {movements.length === 0 && !loading && (
                <div className="empty">Nenhuma movimentação registrada.</div>
              )}
            </div>
          </section>
          <footer className="page-footer">
            StockFlow · Dados sintéticos · Valor calculado pelo custo cadastrado, sem valoração
            fiscal ou contábil.
          </footer>
        </main>
      </div>
    </div>
  )
}

function Metric({
  label,
  value,
  hint,
  warning = false,
}: {
  label: string
  value: string | number
  hint: string
  warning?: boolean
}) {
  return (
    <section className={`metric ${warning ? 'warning' : ''}`}>
      <div>{label}</div>
      <strong>{value}</strong>
      <small>{hint}</small>
    </section>
  )
}
