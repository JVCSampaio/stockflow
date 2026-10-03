import { test, expect } from '@playwright/test'

test('cadastra, movimenta e bloqueia saída acima do saldo pela interface', async ({ page }) => {
  const sku = `E2E-${Date.now()}`
  await page.goto('/')
  await page.getByRole('button', { name: '+ Novo produto', exact: true }).click()
  await page.getByLabel('SKU', { exact: true }).fill(sku)
  await page.getByLabel('Nome do produto', { exact: true }).fill('Monitor para teste funcional')
  await page.getByLabel('Custo unitário (R$)', { exact: true }).fill('100.50')
  await page.getByRole('button', { name: 'Cadastrar produto', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Produto cadastrado')
  await page.getByLabel('Quantidade', { exact: true }).fill('10')
  await page.getByLabel('Motivo do movimento', { exact: true }).fill('Recebimento de teste')
  await page.getByRole('button', { name: 'Confirmar movimento', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Entrada registrada')
  await page.getByRole('button', { name: '↗ Saída', exact: true }).click()
  await page.getByLabel('Quantidade', { exact: true }).fill('11')
  await page.getByLabel('Motivo do movimento', { exact: true }).fill('Solicitação interna de teste')
  await page.getByRole('button', { name: 'Confirmar movimento', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Saldo insuficiente')
  await page.getByLabel('Quantidade', { exact: true }).fill('7')
  await page.getByRole('button', { name: 'Confirmar movimento', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Saída registrada')
  await page.reload()
  await page.getByRole('textbox', { name: 'Buscar produtos', exact: true }).fill(sku)
  await page.getByRole('button', { name: `Movimentar ${sku}`, exact: true }).click()
  await expect(page.getByText('3 disponíveis', { exact: true })).toBeVisible()
})

test('filtra itens para reposição e mantém tabela dentro da página no celular', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByLabel('Apenas reposição', { exact: true }).check()
  await page.getByRole('textbox', { name: 'Buscar produtos', exact: true }).fill('SSD-512')
  await expect(page.getByRole('button', { name: 'Movimentar SSD-512', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
})
