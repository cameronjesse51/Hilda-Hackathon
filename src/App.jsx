import { useState, useRef, useEffect } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || ''

const GRADE_OPTIONS = ['9th', '10th', '11th', '12th']

function OnboardingNameInput({ onSubmit }) {
  const [name, setName] = useState('')
  const inputRef = useRef(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (name.trim()) onSubmit(name.trim())
  }

  return (
    <form className="onboarding-widget" onSubmit={handleSubmit}>
      <input
        ref={inputRef}
        type="text"
        placeholder="Your name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="onboarding-input"
      />
      <button type="submit" disabled={!name.trim()} className="onboarding-submit">Continue</button>
    </form>
  )
}

function OnboardingGradeChips({ onSelect }) {
  return (
    <div className="onboarding-widget">
      <div className="grade-chips">
        {GRADE_OPTIONS.map(grade => (
          <button
            key={grade}
            type="button"
            className="grade-chip"
            onClick={() => onSelect(grade)}
          >
            {grade}
          </button>
        ))}
      </div>
    </div>
  )
}

function OnboardingZipInput({ onSubmit }) {
  const [zip, setZip] = useState('')
  const inputRef = useRef(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (zip.length === 5) onSubmit(zip)
  }

  return (
    <form className="onboarding-widget" onSubmit={handleSubmit}>
      <input
        ref={inputRef}
        type="text"
        placeholder="12345"
        value={zip}
        onChange={(e) => setZip(e.target.value.replace(/\D/g, '').slice(0, 5))}
        maxLength="5"
        className="onboarding-input"
        style={{ maxWidth: 140 }}
      />
      <button type="submit" disabled={zip.length !== 5} className="onboarding-submit">Continue</button>
    </form>
  )
}

function OnboardingSchoolSearch({ zip, onSelect }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [showResults, setShowResults] = useState(false)
  const inputRef = useRef(null)
  const debounceRef = useRef(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  useEffect(() => {
    if (query.length < 2) {
      setResults([])
      setShowResults(false)
      return
    }

    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await fetch(
          `${API_URL}/api/schools/search?q=${encodeURIComponent(query)}&zip=${encodeURIComponent(zip)}`
        )
        const data = await res.json()
        setResults(data.schools || [])
        setShowResults(true)
      } catch {
        setResults([])
      }
      setLoading(false)
    }, 250)

    return () => clearTimeout(debounceRef.current)
  }, [query, zip])

  const handleSelect = (school) => {
    onSelect(`${school.name} (${school.city}, ${school.state})`)
    setShowResults(false)
  }

  const handleCustomSubmit = (e) => {
    e.preventDefault()
    if (query.trim()) onSelect(query.trim())
  }

  return (
    <form className="onboarding-widget school-search" onSubmit={handleCustomSubmit}>
      <div className="school-search-container">
        <div className="school-input-row">
          <input
            ref={inputRef}
            type="text"
            placeholder="Start typing your school name..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="onboarding-input"
          />
          {loading && <span className="search-loading"><span className="spinner" /></span>}
        </div>
        {showResults && results.length > 0 && (
          <div className="school-results">
            {results.map((school, i) => (
              <button
                key={i}
                type="button"
                className="school-result-item"
                onClick={() => handleSelect(school)}
              >
                <span className="school-name">{school.name}</span>
                <span className="school-location">{school.city}, {school.state}</span>
              </button>
            ))}
          </div>
        )}
        {showResults && results.length === 0 && query.length >= 2 && !loading && (
          <div className="school-results">
            <div className="school-no-results">No matches — press Continue to use what you typed</div>
          </div>
        )}
      </div>
      <button type="submit" disabled={!query.trim()} className="onboarding-submit">Continue</button>
    </form>
  )
}

function ChatScreen({ studentId, initialProfile, onSignOut }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [profile, setProfile] = useState(initialProfile || null)
  const [onboardingStep, setOnboardingStep] = useState(initialProfile ? 'done' : 'name')
  const [onboardingData, setOnboardingData] = useState({})
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, onboardingStep])

  useEffect(() => {
    const greeting = initialProfile?.contact?.first_name
      ? `Welcome back, ${initialProfile.contact.first_name}! What can I help you with today?`
      : "Hey! I'm Halda, your AI college counselor. Let's get to know each other — what's your name?"
    setMessages([{ role: 'assistant', text: greeting }])
  }, [])

  const advanceOnboarding = (stepCompleted, value) => {
    const newData = { ...onboardingData, [stepCompleted]: value }
    setOnboardingData(newData)

    switch (stepCompleted) {
      case 'name': {
        const firstName = value.split(' ')[0]
        setMessages(prev => [
          ...prev,
          { role: 'user', text: value },
          { role: 'assistant', text: `Nice to meet you, ${firstName}! What grade are you in?` }
        ])
        setOnboardingStep('grade')
        break
      }
      case 'grade': {
        setMessages(prev => [
          ...prev,
          { role: 'user', text: `${value} grade` },
          { role: 'assistant', text: "Got it! What's your zip code? This helps me find schools and resources near you." }
        ])
        setOnboardingStep('zip')
        break
      }
      case 'zip': {
        setMessages(prev => [
          ...prev,
          { role: 'user', text: value },
          { role: 'assistant', text: "What high school do you go to?" }
        ])
        setOnboardingStep('school')
        break
      }
      case 'school': {
        setMessages(prev => [
          ...prev,
          { role: 'user', text: value },
          { role: 'assistant', text: "Awesome! Last thing — tell me about your goals. What are you interested in studying? What do you want to do after high school? Just type whatever comes to mind." }
        ])
        setOnboardingStep('goals')
        break
      }
    }
  }

  const initializeProfile = async (allData) => {
    try {
      const res = await fetch(`${API_URL}/api/onboard`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_id: studentId,
          name: allData.name,
          grade: allData.grade,
          zip: allData.zip,
          high_school: allData.school,
        })
      })
      const data = await res.json()
      if (data.profile) setProfile(data.profile)
    } catch (err) {
      console.error('Onboarding init error:', err)
    }
  }

  const sendMessage = async (e) => {
    e.preventDefault()
    if (!input.trim() || streaming) return

    const userMessage = input.trim()
    setInput('')

    if (onboardingStep === 'goals') {
      const allData = { ...onboardingData, goals: userMessage }
      setOnboardingData(allData)
      setOnboardingStep('done')
      await initializeProfile(allData)
    }

    setMessages(prev => [...prev, { role: 'user', text: userMessage }])
    setStreaming(true)
    setMessages(prev => [...prev, { role: 'assistant', text: '' }])

    try {
      const res = await fetch(`${API_URL}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id: studentId, message: userMessage })
      })

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        let eventType = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7)
          } else if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6))

            if (eventType === 'text_delta') {
              setMessages(prev => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                if (last && last.role === 'assistant') {
                  updated[updated.length - 1] = { ...last, text: last.text + data.text }
                }
                return updated
              })
            } else if (eventType === 'profile_update' || eventType === 'done') {
              setProfile(data.updated_profile)
            }
          }
        }
      }
    } catch {
      setMessages(prev => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        if (last && last.role === 'assistant' && last.text === '') {
          updated[updated.length - 1] = { ...last, text: 'Sorry, something went wrong. Please try again.' }
        }
        return updated
      })
    }

    setStreaming(false)
  }

  const showInputBar = onboardingStep === 'goals' || onboardingStep === 'done'
  const inputPlaceholder = onboardingStep === 'goals'
    ? 'Tell me about your goals and interests...'
    : 'Type a message...'

  return (
    <div className="chat-layout">
      <div className="chat-main">
        <div className="chat-header">
          <img src="/halda_logo_white.svg" alt="Halda" className="chat-header-logo" />
          <span className="chat-header-subtitle">AI College Counselor</span>
          <button className="sign-out-btn" onClick={onSignOut}>Sign out</button>
        </div>

        <div className="chat-messages">
          {messages.map((msg, i) => (
            <div key={i} className={`chat-bubble ${msg.role}`}>
              {msg.role === 'assistant' && <span className="bubble-label">Halda</span>}
              <p>{msg.text}{msg.role === 'assistant' && streaming && i === messages.length - 1 ? '▌' : ''}</p>
            </div>
          ))}

          {onboardingStep === 'name' && (
            <OnboardingNameInput onSubmit={(v) => advanceOnboarding('name', v)} />
          )}
          {onboardingStep === 'grade' && (
            <OnboardingGradeChips onSelect={(v) => advanceOnboarding('grade', v)} />
          )}
          {onboardingStep === 'zip' && (
            <OnboardingZipInput onSubmit={(v) => advanceOnboarding('zip', v)} />
          )}
          {onboardingStep === 'school' && (
            <OnboardingSchoolSearch
              zip={onboardingData.zip || ''}
              onSelect={(v) => advanceOnboarding('school', v)}
            />
          )}

          <div ref={messagesEndRef} />
        </div>

        {showInputBar && (
          <form className="chat-input-bar" onSubmit={sendMessage}>
            <input
              type="text"
              placeholder={inputPlaceholder}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={streaming}
            />
            <button type="submit" disabled={streaming || !input.trim()}>
              {streaming ? <span className="spinner"></span> : 'Send'}
            </button>
          </form>
        )}
      </div>

      <div className="chat-sidebar">
        <h3>Student Profile</h3>
        {profile ? (
          <div className="profile-data">
            {profile.contact?.first_name && (
              <div className="profile-field">
                <span className="field-label">Name</span>
                <span className="field-value">{profile.contact.first_name} {profile.contact.last_name}</span>
              </div>
            )}
            {profile.stage && (
              <div className="profile-field">
                <span className="field-label">Stage</span>
                <span className="profile-tag">{profile.stage}</span>
              </div>
            )}
            {profile.academic?.grade && (
              <div className="profile-field">
                <span className="field-label">Grade</span>
                <span className="field-value">{profile.academic.grade}</span>
              </div>
            )}
            {profile.contact?.high_school && (
              <div className="profile-field">
                <span className="field-label">High School</span>
                <span className="field-value">{profile.contact.high_school}</span>
              </div>
            )}
            {profile.contact?.zip && (
              <div className="profile-field">
                <span className="field-label">Zip Code</span>
                <span className="field-value">{profile.contact.zip}</span>
              </div>
            )}
            {profile.academic?.gpa && (
              <div className="profile-field">
                <span className="field-label">GPA</span>
                <span className="field-value">{profile.academic.gpa}</span>
              </div>
            )}
            {profile.stated?.interests?.length > 0 && (
              <div className="profile-field">
                <span className="field-label">Interests</span>
                <div className="tag-list">
                  {profile.stated.interests.map((t, i) => <span key={i} className="profile-tag">{t}</span>)}
                </div>
              </div>
            )}
            {profile.stated?.career_goals?.length > 0 && (
              <div className="profile-field">
                <span className="field-label">Career Goals</span>
                <div className="tag-list">
                  {profile.stated.career_goals.map((t, i) => <span key={i} className="profile-tag">{t}</span>)}
                </div>
              </div>
            )}
            <div className="profile-section">
              <span className="field-label">Confidence Scores</span>
              {Object.entries(profile.confidence_scores || {}).map(([key, val]) => (
                <div key={key} className="confidence-bar">
                  <span className="bar-label">{key.replace('_', ' ')}</span>
                  <div className="bar-track">
                    <div className="bar-fill" style={{ width: `${(val || 0) * 100}%` }}></div>
                  </div>
                  <span className="bar-value">{((val || 0) * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
            {profile.behavioral?.micro_internship_results?.length > 0 && (
              <div className="profile-section">
                <span className="field-label">Micro-Internships</span>
                {profile.behavioral.micro_internship_results.map((intern, i) => (
                  <div key={i} className="internship-card">
                    <span className="profile-tag">{intern.domain?.replace('_', ' ')}</span>
                    <span className="field-value"> Module {intern.current_module}/3 — {intern.status}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <p className="sidebar-empty">Profile will appear here as you chat...</p>
        )}
      </div>
    </div>
  )
}

function PhoneInput({ phone, setPhone, onSubmit, loading, error }) {
  return (
    <div className="form-container">
      <h1>Welcome to Halda</h1>
      <p className="subtitle">Enter your phone number to get started</p>
      <form onSubmit={onSubmit}>
        <div className="form-group">
          <label htmlFor="phone">Phone Number</label>
          <div className="input-wrapper">
            <input
              type="tel"
              id="phone"
              placeholder="(555) 123-4567"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              required
            />
          </div>
          {error && <div className="error-message show">{error}</div>}
        </div>
        <button type="submit" disabled={loading}>
          {loading ? <span className="spinner"></span> : 'Continue'}
        </button>
      </form>
    </div>
  )
}

function VerificationCode({ code, setCode, onSubmit, loading, error, phone }) {
  return (
    <div className="form-container">
      <h1>Verify your number</h1>
      <p className="subtitle">Enter the 6-digit code we sent to {phone}</p>
      <form onSubmit={onSubmit}>
        <div className="form-group">
          <label htmlFor="code">Verification Code</label>
          <div className="input-wrapper">
            <input
              type="text"
              id="code"
              placeholder="000000"
              value={code}
              onChange={(e) => setCode(e.target.value.slice(0, 6))}
              maxLength="6"
              required
            />
          </div>
          {error && <div className="error-message show">{error}</div>}
        </div>
        <button type="submit" disabled={loading}>
          {loading ? <span className="spinner"></span> : 'Verify'}
        </button>
      </form>
      <p className="hint">Didn't receive a code? <a href="#">Resend</a></p>
    </div>
  )
}

function Success({ phone, onStartChat }) {
  return (
    <div className="form-container success-state">
      <div className="success-icon">&#10003;</div>
      <h1>Phone verified!</h1>
      <p>Your number {phone} is now verified. We'll send you SMS updates and deadline reminders.</p>
      <button onClick={onStartChat}>Start chatting with Halda</button>
    </div>
  )
}

function WelcomeBack({ profile, onContinue, onSignOut }) {
  const name = profile?.first_name || 'there'
  return (
    <div className="form-container">
      <h1>Welcome back, {name}!</h1>
      <p className="subtitle">Ready to continue your college journey?</p>
      <button onClick={onContinue} style={{ marginBottom: 12 }}>Continue as {name}</button>
      <button onClick={onSignOut} style={{ background: 'transparent', color: '#888', border: '1px solid #ddd', marginTop: 4 }}>
        Sign in as someone else
      </button>
    </div>
  )
}

export default function App() {
  const [step, setStep] = useState('loading')
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [studentId, setStudentId] = useState('')
  const [existingProfile, setExistingProfile] = useState(null)

  useEffect(() => {
    const savedPhone = localStorage.getItem('halda_phone')
    if (!savedPhone) {
      setStep('phone')
      return
    }
    fetch(`${API_URL}/api/profile/${savedPhone}`)
      .then(r => r.json())
      .then(data => {
        if (data?.first_name) {
          setStudentId(savedPhone)
          setExistingProfile(data)
          setStep('welcome')
        } else {
          setStep('phone')
        }
      })
      .catch(() => setStep('phone'))
  }, [])

  const startChat = (id, profile = null) => {
    const sid = id || phone.replace(/\D/g, '')
    localStorage.setItem('halda_phone', sid)
    setStudentId(sid)
    setExistingProfile(profile)
    setStep('chat')
  }

  const handleSignOut = () => {
    localStorage.removeItem('halda_phone')
    setExistingProfile(null)
    setStudentId('')
    setStep('phone')
  }

  const validatePhone = (phoneStr) => {
    const digitsOnly = phoneStr.replace(/\D/g, '')
    return digitsOnly.length === 10
  }

  const handlePhoneSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (!validatePhone(phone)) {
      setError('Please enter a valid 10-digit phone number')
      return
    }

    setLoading(true)
    const apiUrl = API_URL

    try {
      const response = await fetch(`${apiUrl}/api/send-verification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone })
      })

      const data = await response.json()

      if (!response.ok) {
        setError(data.error || 'Failed to send verification code')
        setLoading(false)
        return
      }

      localStorage.setItem('studentPhone', phone)
      setLoading(false)
      setStep('verify')
    } catch {
      setError('Network error. Please try again.')
      setLoading(false)
    }
  }

  const handleVerifySubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (code.length !== 6) {
      setError('Please enter a 6-digit code')
      return
    }

    setLoading(true)

    try {
      const response = await fetch(`${API_URL}/api/verify-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, code })
      })

      const data = await response.json()

      if (!response.ok) {
        setError(data.error || 'Verification failed')
        setLoading(false)
        return
      }

      const sid = phone.replace(/\D/g, '')
      let existing = null
      try {
        const profileRes = await fetch(`${API_URL}/profile/${sid}`)
        const profileData = await profileRes.json()
        if (profileRes.ok && profileData.contact?.first_name) {
          existing = profileData
        }
      } catch { /* no profile found, treat as new user */ }

      setLoading(false)
      startChat(sid, existing)
    } catch {
      setError('Network error. Please try again.')
      setLoading(false)
    }
  }

  if (step === 'loading') return null

  if (step === 'chat') {
    return <ChatScreen studentId={studentId} initialProfile={existingProfile} onSignOut={handleSignOut} />
  }

  return (
    <div className="container">
      <div className="branding-side">
        <img src="/halda_logo_white.svg" alt="Halda" className="halda-logo" />
        <button
          type="button"
          className="dev-skip-btn"
          onClick={() => startChat('test-jordan')}
        >
          Skip to Chat (dev)
        </button>
      </div>

      <div className="form-side">
        {step === 'welcome' && (
          <WelcomeBack
            profile={existingProfile}
            onContinue={() => startChat(studentId, existingProfile)}
            onSignOut={handleSignOut}
          />
        )}

        {step === 'phone' && (
          <PhoneInput
            phone={phone}
            setPhone={setPhone}
            onSubmit={handlePhoneSubmit}
            loading={loading}
            error={error}
          />
        )}

        {step === 'verify' && (
          <VerificationCode
            code={code}
            setCode={setCode}
            onSubmit={handleVerifySubmit}
            loading={loading}
            error={error}
            phone={phone}
          />
        )}
      </div>
    </div>
  )
}
