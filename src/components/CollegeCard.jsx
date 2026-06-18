import { formatCurrency, formatDate, formatNumber, formatPercent, formatStatus } from '../utils/formatters.js'
import { admissionMessage, bestForSummary, hasValue } from '../utils/collegePresentation.js'

const SOURCE_FIELD_LABELS = {
  'cost.facts.net_price': 'net price',
  'cost.facts.median_grad_debt': 'median graduate debt',
  'admissions.facts.admission_rate': 'admission rate',
  'admissions.facts.sat_average': 'average SAT',
  'outcomes.facts.graduation_rate': 'graduation rate',
  'outcomes.facts.transfer_rate': 'transfer rate',
  'outcomes.facts.median_earnings_10yr': 'median earnings',
  'campus.facts.enrollment': 'enrollment',
  'campus.facts.control': 'institution type',
  'campus.facts.size_category': 'school size',
  'campus.facts.pell_recipient_rate': 'Pell recipient share',
  'campus.facts.international_rate': 'international student share',
  'program_fit.facts.matched_programs': 'matching programs',
  'program_fit.facts.cip_codes': 'program CIP codes',
  'program_fit.facts.awards_last_year': 'recent program completions',
  'program_fit.facts.credentials': 'available credentials',
  'program_fit.personalized.status': 'program fit',
  'admissions.personalized.classification': 'admission classification',
  name: 'institution name',
  location: 'location',
}

function labelWithYear(label, year) {
  return year == null || year === '' ? label : `${label} (${year})`
}

function Stat({ label, value, detail = null, missing = false }) {
  return (
    <div className={`college-stat${missing ? ' missing' : ''}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
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
  const classification = college.admissions?.personalized?.classification || {
    label: 'unknown',
    reason: 'Admission fit could not be estimated.',
  }
  const costFacts = college.cost?.facts || {}
  const costPersonalized = college.cost?.personalized || {}
  const admissionsFacts = college.admissions?.facts || {}
  const outcomesFacts = college.outcomes?.facts || {}
  const campusFacts = college.campus?.facts || {}
  const programFacts = college.program_fit?.facts || {}
  const programPersonalized = college.program_fit?.personalized || {}
  const fit = college.fit || {}
  const sources = college.sources || []
  const difference = costPersonalized.budget_difference
  const admissionMissing = admissionMessage(college)
  const criticalStats = [
    {
      label: labelWithYear('Net price', costFacts.source_years?.net_price),
      value: hasValue(costFacts.net_price) ? formatCurrency(costFacts.net_price) : 'Cost unavailable',
      detail: hasValue(costFacts.net_price) ? null : 'Ask the school for its latest net-price estimate.',
      missing: !hasValue(costFacts.net_price),
    },
    {
      label: labelWithYear('Admission rate', admissionsFacts.source_years?.admission_rate),
      value: admissionMissing?.value || formatPercent(admissionsFacts.admission_rate),
      detail: admissionMissing?.detail,
      missing: Boolean(admissionMissing),
    },
    {
      label: labelWithYear('Graduation rate', outcomesFacts.source_years?.graduation_rate),
      value: hasValue(outcomesFacts.graduation_rate)
        ? formatPercent(outcomesFacts.graduation_rate)
        : 'Completion data unavailable',
      detail: hasValue(outcomesFacts.graduation_rate)
        ? null
        : 'Compare retention and completion directly with the school.',
      missing: !hasValue(outcomesFacts.graduation_rate),
    },
  ]
  if (programPersonalized.requested) {
    const credentials = programFacts.credentials
    const credentialSummary = Array.isArray(credentials) && credentials.length > 0
      ? credentials.join(', ')
      : null
    criticalStats.push({
      label: programPersonalized.requested,
      value: programPersonalized.status === 'unknown'
        ? 'Program match unconfirmed'
        : formatStatus(programPersonalized.status),
      detail: programPersonalized.status === 'unknown'
        ? 'Confirm the exact major and credential with the school.'
        : credentialSummary,
      missing: programPersonalized.status === 'unknown',
    })
  }

  const secondaryStats = [
    [costFacts.median_grad_debt, labelWithYear('Median graduate debt', costFacts.source_years?.median_grad_debt), formatCurrency],
    [admissionsFacts.sat_average, labelWithYear('Average SAT', admissionsFacts.source_years?.sat_average), formatNumber],
    [outcomesFacts.transfer_rate, labelWithYear('Transfer rate', outcomesFacts.source_years?.transfer_rate), formatPercent],
    [outcomesFacts.median_earnings_10yr, labelWithYear('Median earnings after 10 years', outcomesFacts.source_years?.earnings), formatCurrency],
    [campusFacts.enrollment, labelWithYear('Enrollment', campusFacts.source_year), formatNumber],
    [campusFacts.control, 'Institution type', formatStatus],
    [campusFacts.size_category, 'School size', formatStatus],
    [campusFacts.pell_recipient_rate, 'Pell recipients', formatPercent],
    [campusFacts.international_rate, 'International students', formatPercent],
    [programFacts.awards_last_year, labelWithYear('Program completions', programFacts.source_year), formatNumber],
  ].filter(([value]) => hasValue(value))

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

      {fit.score != null && (
        <p className="college-match-score">
          {Math.round(fit.score)}% recommendation score
          <small>Not an admission probability</small>
        </p>
      )}

      <p className="college-best-for">{bestForSummary(college)}</p>

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

      <div className="college-stat-grid critical">
        {criticalStats.map(stat => <Stat key={stat.label} {...stat} />)}
      </div>

      {secondaryStats.length > 0 && (
        <div className="college-stat-grid secondary">
          {secondaryStats.map(([value, label, formatter]) => (
            <Stat key={label} label={label} value={formatter(value)} />
          ))}
        </div>
      )}

      {difference != null && (
        <p className={`budget-status ${costPersonalized.within_budget ? 'within' : 'over'}`}>
          {formatCurrency(Math.abs(difference))}{' '}
          {costPersonalized.within_budget ? 'under budget' : 'over budget'}
        </p>
      )}

      {fit.reasons?.length > 0 && (
        <div className="college-reasons">
          <h4>Why it matches</h4>
          <ul>
            {fit.reasons.map((reason, index) => (
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
