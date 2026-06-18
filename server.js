import express from 'express'
import cors from 'cors'
import dotenv from 'dotenv'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))

dotenv.config()

const app = express()
app.use(cors())
app.use(express.json())

const TEXTBELT_KEY = process.env.TEXTBELT_KEY || 'textbelt'

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

    if (!phone) {
      return res.status(400).json({ error: 'Phone number required' })
    }

    // Generate code
    const code = generateCode()

    // Store code with 10-minute expiry
    verificationCodes.set(phone, {
      code,
      expiresAt: Date.now() + 10 * 60 * 1000,
      attempts: 0
    })

    // Send SMS via TextBelt
    const response = await fetch('https://textbelt.com/text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone,
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

    if (!phone || !code) {
      return res.status(400).json({ error: 'Phone and code required' })
    }

    const stored = verificationCodes.get(phone)

    if (!stored) {
      return res.status(400).json({ error: 'No verification code found' })
    }

    if (Date.now() > stored.expiresAt) {
      verificationCodes.delete(phone)
      return res.status(400).json({ error: 'Code expired' })
    }

    if (stored.attempts >= 3) {
      verificationCodes.delete(phone)
      return res.status(400).json({ error: 'Too many attempts' })
    }

    if (stored.code !== code) {
      stored.attempts++
      return res.status(400).json({ error: 'Invalid code' })
    }

    // Code is valid - clean up
    verificationCodes.delete(phone)

    res.json({
      success: true,
      message: 'Phone verified',
      phone
    })
  } catch (error) {
    console.error('Verification error:', error)
    res.status(500).json({ error: 'Verification failed' })
  }
})

// Get profile by phone number
app.get('/api/profile/:phone', async (req, res) => {
  try {
    const { phone } = req.params
    const response = await fetch(
      `${process.env.SUPABASE_URL}/rest/v1/student_profiles?phone=eq.${phone}&limit=1`,
      {
        headers: {
          apikey: process.env.SUPABASE_ANON_KEY,
          Authorization: `Bearer ${process.env.SUPABASE_ANON_KEY}`,
        }
      }
    )
    const data = await response.json()
    if (data.length > 0) {
      res.json(data[0])
    } else {
      res.status(404).json({ error: 'Profile not found' })
    }
  } catch (error) {
    console.error('Profile fetch error:', error)
    res.status(500).json({ error: 'Failed to fetch profile' })
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
