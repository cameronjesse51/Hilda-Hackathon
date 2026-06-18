import { useState } from 'react'
import CollegeCard from './CollegeCard.jsx'
import CollegeComparison from './CollegeComparison.jsx'

const MAX_COMPARISON_SCHOOLS = 3

export default function CollegeResults({ resultSet }) {
  const colleges = resultSet?.colleges || []
  const [selectedIds, setSelectedIds] = useState([])

  const toggleComparison = (collegeId) => {
    setSelectedIds(current => {
      if (current.includes(collegeId)) {
        return current.filter(id => id !== collegeId)
      }
      if (current.length >= MAX_COMPARISON_SCHOOLS) return current
      return [...current, collegeId]
    })
  }

  const selectedColleges = selectedIds
    .map(id => colleges.find(college => college.college_id === id))
    .filter(Boolean)

  return (
    <section className="college-results" aria-label="College recommendations">
      <div className="college-results-heading">
        <div>
          <h2>{colleges.length} college {colleges.length === 1 ? 'match' : 'matches'}</h2>
          <p>Select up to three schools to compare.</p>
        </div>
        {selectedIds.length > 0 && (
          <span>{selectedIds.length}/{MAX_COMPARISON_SCHOOLS} selected</span>
        )}
      </div>

      <div className="college-card-list">
        {colleges.map(college => {
          const selected = selectedIds.includes(college.college_id)
          return (
            <CollegeCard
              key={college.college_id}
              college={college}
              selected={selected}
              comparisonDisabled={!selected && selectedIds.length >= MAX_COMPARISON_SCHOOLS}
              onToggleComparison={toggleComparison}
            />
          )
        })}
      </div>

      {selectedColleges.length === 1 && (
        <p className="comparison-hint">Select one more school to open the comparison.</p>
      )}
      {selectedColleges.length >= 2 && (
        <CollegeComparison colleges={selectedColleges} />
      )}
    </section>
  )
}
