import { formatCurrency, formatDate, formatPercent, formatStatus } from '../utils/formatters.js'

const SOURCE_FIELD_LABELS = {
  'financials.net_price': 'net price',
  'admissions.admission_rate': 'admission rate',
  'outcomes.graduation_rate': 'graduation rate',
  'outcomes.median_earnings_10yr': 'median earnings',
  'classification.gpa_comparison': 'GPA comparison',
  program: 'program availability',
  name: 'institution name',
  location: 'location',
}

function Stat({ label, value }) {
  return (
    <div className="college-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function safeSourceUrl(url) {
  if (typeof url !== 'string') return null
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.href : null
  } catch {
    return null
  }
}

function sourceFieldSummary(fields) {
  if (!Array.isArray(fields) || fields.length === 0) return 'Institution details'
  return fields
    .map(field => SOURCE_FIELD_LABELS[field] || field.replaceAll('.', ' '))
    .join(', ')
}

export default function CollegeCard({ college, selected = false, comparisonDisabled = false, onToggleComparison }) {
  const location = [college.location?.city, college.location?.state]
    .filter(Boolean)
    .join(', ')
  const classification = college.classification || {
    label: 'unknown',
    reason: 'Admission fit could not be estimated.',
  }
  const financials = college.financials || {}
  const admissions = college.admissions || {}
  const outcomes = college.outcomes || {}
  const program = college.program || {}
  const sources = college.sources || []
  const difference = financials.budget_difference

  return (
    <article className="college-card" aria-label={`College recommendation for ${college.name}`}>
      <header className="college-card-header">
        <div>
          <h3>{college.name}</h3>
          <p>{location || 'Location not reported'}</p>
        </div>
        <span
          className={`classification-badge ${classification.label}`}
          title={classification.reason}
        >
          {formatStatus(classification.label)}
        </span>
      </header>

      {college.match_score != null && (
        <p className="college-match-score">{Math.round(college.match_score)}% profile match</p>
      )}

      {onToggleComparison && (
        <button
          type="button"
          className={`comparison-toggle ${selected ? 'selected' : ''}`}
          onClick={() => onToggleComparison(college.college_id)}
          disabled={comparisonDisabled}
          aria-pressed={selected}
        >
          {selected ? 'Selected for comparison' : 'Add to comparison'}
        </button>
      )}

      <div className="college-stat-grid">
        <Stat label="Net price" value={formatCurrency(financials.net_price)} />
        <Stat label="Your budget" value={formatCurrency(financials.student_budget)} />
        <Stat label="Admission rate" value={formatPercent(admissions.admission_rate)} />
        <Stat label="Graduation rate" value={formatPercent(outcomes.graduation_rate)} />
        <Stat label="Median earnings" value={formatCurrency(outcomes.median_earnings_10yr)} />
        <Stat label={program.requested || 'Program'} value={formatStatus(program.status)} />
      </div>

      {difference != null && (
        <p className={`budget-status ${financials.within_budget ? 'within' : 'over'}`}>
          {formatCurrency(Math.abs(difference))}{' '}
          {financials.within_budget ? 'under budget' : 'over budget'}
        </p>
      )}

      {college.match_reasons?.length > 0 && (
        <div className="college-reasons">
          <h4>Why it matches</h4>
          <ul>
            {college.match_reasons.map((reason, index) => (
              <li key={`${reason.category}-${reason.text}-${index}`}>
                <span>{reason.text}</span>
                {reason.evidence && <small>{reason.evidence}</small>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {sources.length > 0 && (
        <div className="college-sources">
          <h4>Sources</h4>
          <ul>
            {sources.map((source, index) => {
              const sourceUrl = safeSourceUrl(source.url)
              return (
                <li key={`${source.name}-${source.url}-${index}`}>
                  <div>
                    {sourceUrl ? (
                      <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
                        {source.name}<span aria-hidden="true"> ↗</span>
                      </a>
                    ) : (
                      <span className="college-source-name">{source.name}</span>
                    )}
                    <span className="college-source-date">
                      Retrieved {formatDate(source.retrieved_at)}
                    </span>
                  </div>
                  <small>Supports: {sourceFieldSummary(source.fields)}</small>
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </article>
  )
}
