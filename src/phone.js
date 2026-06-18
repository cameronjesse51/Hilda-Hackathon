export function normalizePhone(phone) {
  const raw = String(phone || '').trim()
  const digits = raw.replace(/\D/g, '')

  if (digits.length === 10) return `+1${digits}`
  if (digits.length === 11 && digits.startsWith('1')) return `+${digits}`
  if (raw.startsWith('+') && digits.length >= 8 && digits.length <= 15 && digits[0] !== '0') {
    return `+${digits}`
  }
  return null
}
