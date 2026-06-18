import React from 'react'

export default function SkeletonDashboard() {
  return (
    <div className="dash__stack" aria-busy="true" aria-label="Loading your plan">
      <div className="skel skel--hero" />
      <div className="stats">
        {Array.from({ length: 4 }).map((_, i) => (
          <div className="skel skel--stat" key={i} />
        ))}
      </div>
      <div className="dash__cols">
        <div className="skel skel--block" />
        <div className="dash__stack">
          <div className="skel skel--block" style={{ height: 180 }} />
          <div className="skel skel--block" style={{ height: 150 }} />
        </div>
      </div>
    </div>
  )
}
