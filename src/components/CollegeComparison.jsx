import { formatCurrency, formatPercent, formatStatus } from '../utils/formatters.js'

const ROWS = [
  ['Classification', college => formatStatus(college.classification?.label)],
  ['Profile match', college => college.match_score == null ? 'Not reported' : `${Math.round(college.match_score)}%`],
  ['Net price', college => formatCurrency(college.financials?.net_price)],
  ['Budget difference', college => {
    const difference = college.financials?.budget_difference
    if (difference == null) return 'Not reported'
    return `${formatCurrency(Math.abs(difference))} ${difference >= 0 ? 'under' : 'over'}`
  }],
  ['Admission rate', college => formatPercent(college.admissions?.admission_rate)],
  ['Graduation rate', college => formatPercent(college.outcomes?.graduation_rate)],
  ['Median earnings', college => formatCurrency(college.outcomes?.median_earnings_10yr)],
  ['Program', college => formatStatus(college.program?.status)],
]

export default function CollegeComparison({ colleges }) {
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
            {ROWS.map(([label, value]) => (
              <tr key={label}>
                <th scope="row">{label}</th>
                {colleges.map(college => <td key={college.college_id}>{value(college)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
