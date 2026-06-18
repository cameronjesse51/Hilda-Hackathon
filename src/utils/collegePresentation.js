export function hasValue(value) {
  return value != null && value !== '' && (!Number.isNaN(Number(value)) || typeof value !== 'number')
}

export function admissionMessage(college) {
  const rate = college.admissions?.facts?.admission_rate
  if (hasValue(rate)) return null
  return {
    value: 'Rate not reported',
    detail: 'This is common for open-admission schools. Confirm the school’s admission policy.',
  }
}

export function bestForSummary(college) {
  const reasons = college.fit?.reasons || []
  const categories = new Set(reasons.map(reason => reason.category))
  const program = college.program_fit?.personalized || {}
  const cost = college.cost?.personalized || {}
  const classification = college.admissions?.personalized?.classification?.label
  const priorities = []
  const audience = program.requested && program.status === 'available'
    ? `${program.requested} students`
    : 'students'

  if (categories.has('financial') && cost.within_budget === true) {
    priorities.push('affordability')
  }
  if (categories.has('location')) {
    priorities.push('their preferred location')
  }
  if (categories.has('outcomes')) {
    priorities.push('completion and career outcomes')
  }
  if (priorities.length > 0) {
    return `Best for: ${audience} prioritizing ${priorities.slice(0, 2).join(' and ')}.`
  }

  if (classification === 'likely') return 'Best for: students seeking a more accessible admissions option.'
  if (classification === 'target') return 'Best for: students seeking a balanced admissions option.'
  return 'Best for: overall alignment with your stated preferences.'
}
