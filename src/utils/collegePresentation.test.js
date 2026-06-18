import test from 'node:test'
import assert from 'node:assert/strict'

import { admissionMessage, bestForSummary, hasValue } from './collegePresentation.js'

test('zero is treated as reported data while null is unavailable', () => {
  assert.equal(hasValue(0), true)
  assert.equal(hasValue(null), false)
})

test('missing admission rates explain the open-admission possibility without claiming it', () => {
  const message = admissionMessage({ admissions: { facts: { admission_rate: null } } })

  assert.equal(message.value, 'Rate not reported')
  assert.match(message.detail, /common for open-admission schools/)
  assert.match(message.detail, /Confirm/)
})

test('reported admission rates do not produce missing-data guidance', () => {
  assert.equal(admissionMessage({ admissions: { facts: { admission_rate: 0.72 } } }), null)
})

test('best-for summary uses confirmed student priorities', () => {
  const college = {
    cost: { personalized: { within_budget: true } },
    program_fit: { personalized: { requested: 'Nursing', status: 'available' } },
    fit: { reasons: [{ category: 'program' }, { category: 'financial' }] },
  }

  assert.equal(
    bestForSummary(college),
    'Best for: Nursing students prioritizing affordability.',
  )
})
