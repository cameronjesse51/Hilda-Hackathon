import express from 'express'
import cors from 'cors'
import dotenv from 'dotenv'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'
import { normalizePhone } from './src/phone.js'

const __dirname = dirname(fileURLToPath(import.meta.url))

dotenv.config()

const app = express()
app.use(cors())
app.use(express.json())

const TEXTBELT_KEY = process.env.TEXTBELT_KEY || 'textbelt'
const API_INTERNAL_URL = (
  process.env.API_INTERNAL_URL || process.env.VITE_API_URL || 'http://localhost:8000'
).replace(/\/$/, '')

// Store verification codes in memory (in production, use a database with TTL)
const verificationCodes = new Map()

// Generate random 6-digit code
function generateCode() {
  return Math.floor(100000 + Math.random() * 900000).toString()
}

// Send verification code via SMS
app.post('/api/send-verification', async (req, res) => {
  try {
    const { phone } = req.body
    const normalizedPhone = normalizePhone(phone)

    if (!normalizedPhone) {
      return res.status(400).json({ error: 'Valid phone number required' })
    }

    // Generate code
    const code = generateCode()

    // Store code with 10-minute expiry
    verificationCodes.set(normalizedPhone, {
      code,
      expiresAt: Date.now() + 10 * 60 * 1000,
      attempts: 0
    })

    // Send SMS via TextBelt
    const response = await fetch('https://textbelt.com/text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone: normalizedPhone,
        message: `Your Halda verification code is: ${code}`,
        key: TEXTBELT_KEY
      })
    })

    const result = await response.json()

    if (!result.success) {
      throw new Error(result.error || 'TextBelt failed to send SMS')
    }

    console.log(`SMS sent to ${phone}: TextBelt ID ${result.textId}`)

    res.json({
      success: true,
      message: 'Verification code sent',
      textId: result.textId
    })
  } catch (error) {
    console.error('SMS send error:', error)
    res.status(500).json({ error: 'Failed to send verification code' })
  }
})

// Verify code
app.post('/api/verify-code', async (req, res) => {
  try {
    const { phone, code } = req.body
    const normalizedPhone = normalizePhone(phone)

    if (!normalizedPhone || !code) {
      return res.status(400).json({ error: 'Phone and code required' })
    }

    const stored = verificationCodes.get(normalizedPhone)

    if (!stored) {
      return res.status(400).json({ error: 'No verification code found' })
    }

    if (Date.now() > stored.expiresAt) {
      verificationCodes.delete(normalizedPhone)
      return res.status(400).json({ error: 'Code expired' })
    }

    if (stored.attempts >= 3) {
      verificationCodes.delete(normalizedPhone)
      return res.status(400).json({ error: 'Too many attempts' })
    }

    if (stored.code !== code) {
      stored.attempts++
      return res.status(400).json({ error: 'Invalid code' })
    }

    const sessionResponse = await fetch(`${API_INTERNAL_URL}/auth/session`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Secret': process.env.SESSION_SECRET || '',
      },
      body: JSON.stringify({ phone: normalizedPhone }),
    })
    const session = await sessionResponse.json()
    if (!sessionResponse.ok) {
      throw new Error(session.detail || 'Failed to create authenticated session')
    }

    // Consume the OTP only after the authenticated profile/session is ready.
    verificationCodes.delete(normalizedPhone)

    res.json({
      success: true,
      message: 'Phone verified',
      token: session.token,
      expires_at: session.expires_at,
      student_id: session.student_id,
    })
  } catch (error) {
    console.error('Verification error:', error)
    res.status(500).json({ error: 'Verification failed' })
  }
})

// Search schools
app.get('/api/schools/search', async (req, res) => {
  try {
    const q = req.query.q || ''
    const zip = req.query.zip || ''

    if (q.length < 2) {
      if (zip) {
        const response = await fetch(
          `${process.env.SUPABASE_URL}/rest/v1/high_schools?zip=eq.${zip}&limit=5`,
          {
            headers: {
              apikey: process.env.SUPABASE_ANON_KEY,
              Authorization: `Bearer ${process.env.SUPABASE_ANON_KEY}`,
            }
          }
        )
        const data = await response.json()
        return res.json({ schools: data || [] })
      }
      return res.json({ schools: [] })
    }

    const response = await fetch(
      `${process.env.SUPABASE_URL}/rest/v1/rpc/search_high_schools`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          apikey: process.env.SUPABASE_ANON_KEY,
          Authorization: `Bearer ${process.env.SUPABASE_ANON_KEY}`,
        },
        body: JSON.stringify({ query: q, zip_code: zip })
      }
    )
    const data = await response.json()
    return res.json({ schools: data || [] })
  } catch (error) {
    console.error('School search error:', error)
    res.status(500).json({ error: 'Failed to search schools' })
  }
})

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok' })
})

// Serve React frontend in production
app.use(express.static(join(__dirname, 'dist')))
app.get('/{*path}', (req, res) => {
  res.sendFile(join(__dirname, 'dist', 'index.html'))
})

const PORT = process.env.PORT || 3001
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Halda running on port ${PORT}`)
})
