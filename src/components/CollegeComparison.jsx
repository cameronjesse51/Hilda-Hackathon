import { formatCurrency, formatNumber, formatPercent, formatStatus } from '../utils/formatters.js'
import { admissionMessage, bestForSummary, hasValue } from '../utils/collegePresentation.js'

function withYear(value, year) {
  return year == null || year === '' ? value : `${value} · ${year}`
}

function missingOr(value, formatter, year = null, missing = '—') {
  return hasValue(value) ? withYear(formatter(value), year) : missing
}

function numericValue(college, metric) {
  const values = {
    cost: college.cost?.facts?.net_price,
    completion: college.outcomes?.facts?.graduation_rate,
    debt: college.cost?.facts?.median_grad_debt,
  }
  const value = Number(values[metric])
  return Number.isFinite(value) ? value : null
}

function bestValue(colleges, metric, direction) {
  const values = colleges
    .map(college => numericValue(college, metric))
    .filter(value => value != null)
  if (values.length === 0) return null
  return direction === 'min' ? Math.min(...values) : Math.max(...values)
}

function comparisonRows(colleges) {
  const lowestCost = bestValue(colleges, 'cost', 'min')
  const highestCompletion = bestValue(colleges, 'completion', 'max')
  const lowestDebt = bestValue(colleges, 'debt', 'min')
  const anyRequestedProgram = colleges.some(college => college.program_fit?.personalized?.requested)

  const rows = [
    {
      id: 'best-for',
      label: 'Best for',
      critical: true,
      available: () => true,
      value: bestForSummary,
    },
    {
      id: 'classification',
      label: 'Admissions fit',
      critical: true,
      available: () => true,
      value: college => {
        const label = college.admissions?.personalized?.classification?.label
        return label === 'unknown' || !label ? 'Insufficient data' : formatStatus(label)
      },
    },
    {
      id: 'score',
      label: 'Recommendation score',
      note: 'Not admission odds',
      available: college => hasValue(college.fit?.score),
      value: college => hasValue(college.fit?.score) ? `${Math.round(college.fit.score)}%` : '—',
    },
    {
      id: 'cost',
      label: 'Estimated net price',
      critical: true,
      available: college => hasValue(college.cost?.facts?.net_price),
      value: college => missingOr(
        college.cost?.facts?.net_price,
        formatCurrency,
        college.cost?.facts?.source_years?.net_price,
        'Cost unavailable',
      ),
      highlight: college => numericValue(college, 'cost') === lowestCost ? 'Lowest cost' : null,
    },
    {
      id: 'budget',
      label: 'Budget difference',
      available: college => hasValue(college.cost?.personalized?.budget_difference),
      value: college => {
        const difference = college.cost?.personalized?.budget_difference
        if (!hasValue(difference)) return '—'
        return `${formatCurrency(Math.abs(difference))} ${difference >= 0 ? 'under' : 'over'}`
      },
    },
    {
      id: 'debt',
      label: 'Median graduate debt',
      available: college => hasValue(college.cost?.facts?.median_grad_debt),
      value: college => missingOr(
        college.cost?.facts?.median_grad_debt,
        formatCurrency,
        college.cost?.facts?.source_years?.median_grad_debt,
      ),
      highlight: college => numericValue(college, 'debt') === lowestDebt ? 'Lowest debt' : null,
    },
    {
      id: 'admission-rate',
      label: 'Admission rate',
      critical: true,
      available: () => true,
      value: college => {
        const missing = admissionMessage(college)
        return missing?.value || withYear(
          formatPercent(college.admissions?.facts?.admission_rate),
          college.admissions?.facts?.source_years?.admission_rate,
        )
      },
    },
    {
      id: 'sat',
      label: 'Average SAT',
      available: college => hasValue(college.admissions?.facts?.sat_average),
      value: college => missingOr(
        college.admissions?.facts?.sat_average,
        formatNumber,
        college.admissions?.facts?.source_years?.sat_average,
      ),
    },
    {
      id: 'completion',
      label: 'Graduation rate',
      critical: true,
      available: college => hasValue(college.outcomes?.facts?.graduation_rate),
      value: college => missingOr(
        college.outcomes?.facts?.graduation_rate,
        formatPercent,
        college.outcomes?.facts?.source_years?.graduation_rate,
        'Completion unavailable',
      ),
      highlight: college => numericValue(college, 'completion') === highestCompletion ? 'Highest completion' : null,
    },
    {
      id: 'transfer',
      label: 'Transfer rate',
      available: college => hasValue(college.outcomes?.facts?.transfer_rate),
      value: college => missingOr(
        college.outcomes?.facts?.transfer_rate,
        formatPercent,
        college.outcomes?.facts?.source_years?.transfer_rate,
      ),
    },
    {
      id: 'earnings',
      label: 'Median earnings after 10 years',
      available: college => hasValue(college.outcomes?.facts?.median_earnings_10yr),
      value: college => missingOr(
        college.outcomes?.facts?.median_earnings_10yr,
        formatCurrency,
        college.outcomes?.facts?.source_years?.earnings,
      ),
    },
    {
      id: 'enrollment',
      label: 'Enrollment',
      available: college => hasValue(college.campus?.facts?.enrollment),
      value: college => missingOr(
        college.campus?.facts?.enrollment,
        formatNumber,
        college.campus?.facts?.source_year,
      ),
    },
    {
      id: 'control',
      label: 'Institution type',
      available: college => hasValue(college.campus?.facts?.control),
      value: college => hasValue(college.campus?.facts?.control)
        ? formatStatus(college.campus.facts.control)
        : '—',
    },
    {
      id: 'size',
      label: 'School size',
      available: college => hasValue(college.campus?.facts?.size_category),
      value: college => hasValue(college.campus?.facts?.size_category)
        ? formatStatus(college.campus.facts.size_category)
        : '—',
    },
    {
      id: 'pell',
      label: 'Pell recipients',
      available: college => hasValue(college.campus?.facts?.pell_recipient_rate),
      value: college => missingOr(college.campus?.facts?.pell_recipient_rate, formatPercent),
    },
    {
      id: 'international',
      label: 'International students',
      available: college => hasValue(college.campus?.facts?.international_rate),
      value: college => missingOr(college.campus?.facts?.international_rate, formatPercent),
    },
    {
      id: 'program',
      label: 'Requested program',
      critical: anyRequestedProgram,
      available: college => Boolean(college.program_fit?.personalized?.requested),
      value: college => {
        const program = college.program_fit?.personalized || {}
        if (!program.requested) return '—'
        return program.status === 'unknown' ? 'Unconfirmed' : formatStatus(program.status)
      },
      highlight: college => college.program_fit?.personalized?.status === 'available'
        ? 'Confirmed program'
        : null,
    },
    {
      id: 'program-completions',
      label: 'Program completions',
      available: college => hasValue(college.program_fit?.facts?.awards_last_year),
      value: college => missingOr(
        college.program_fit?.facts?.awards_last_year,
        formatNumber,
        college.program_fit?.facts?.source_year,
      ),
    },
  ]

  return rows.filter(row => row.critical || colleges.some(row.available))
}

export default function CollegeComparison({ colleges }) {
  const rows = comparisonRows(colleges)

  return (
    <section className="college-comparison" aria-labelledby="college-comparison-title">
      <h3 id="college-comparison-title">Side-by-side comparison</h3>
      <div className="comparison-table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Metric</th>
              {colleges.map(college => <th scope="col" key={college.college_id}>{college.name}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr key={row.id}>
                <th scope="row">
                  {row.label}
                  {row.note && <small>{row.note}</small>}
                </th>
                {colleges.map(college => {
                  const highlight = row.highlight?.(college)
                  return (
                    <td className={highlight ? 'comparison-best' : undefined} key={college.college_id}>
                      <span>{row.value(college)}</span>
                      {highlight && <small>{highlight}</small>}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
