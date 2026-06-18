import crypto from 'node:crypto'

const SESSION_TTL_SECONDS = 60 * 60 * 24 * 7

function encode(value) {
  return Buffer.from(JSON.stringify(value)).toString('base64url')
}

function sessionSecret() {
  const secret = process.env.SESSION_SECRET
  if (!secret || secret.length < 32) {
    throw new Error('SESSION_SECRET must be set to at least 32 characters')
  }
  return secret
}

export function createSessionToken(studentId) {
  const now = Math.floor(Date.now() / 1000)
  const expiresAt = now + SESSION_TTL_SECONDS
  const header = encode({ alg: 'HS256', typ: 'JWT' })
  const payload = encode({ sub: studentId, iat: now, exp: expiresAt, iss: 'halda' })
  const unsignedToken = `${header}.${payload}`
  const signature = crypto
    .createHmac('sha256', sessionSecret())
    .update(unsignedToken)
    .digest('base64url')

  return {
    token: `${unsignedToken}.${signature}`,
    expiresAt,
  }
}
