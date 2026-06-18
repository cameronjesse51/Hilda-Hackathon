export function formatCurrency(value) {
  if (value == null || !Number.isFinite(Number(value))) return 'Not reported'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(Number(value))
}

export function formatPercent(value) {
  if (value == null || !Number.isFinite(Number(value))) return 'Not reported'
  return new Intl.NumberFormat('en-US', {
    style: 'percent',
    maximumFractionDigits: 0,
  }).format(Number(value))
}

export function formatNumber(value) {
  if (value == null || !Number.isFinite(Number(value))) return 'Not reported'
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(Number(value))
}

export function formatStatus(value) {
  if (!value || value === 'unknown') return 'Not reported'
  return String(value)
    .replaceAll('_', ' ')
    .replace(/\b\w/g, letter => letter.toUpperCase())
}

export function formatDate(value) {
  if (!value) return 'date unavailable'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'date unavailable'
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date)
}
