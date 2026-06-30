import React from 'react';

export default function Logo({ className = '', showText = true }) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      {/* Das neue Premium Fintech-Icon */}
      <svg 
        width="44" 
        height="44" 
        viewBox="0 0 44 44" 
        fill="none" 
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          {/* Der Finanzguru-Style Farbverlauf (Neon-Grün zu Cyan/Teal) */}
          <linearGradient id="fintechGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#00f2fe" />
            <stop offset="100%" stopColor="#4facfe" />
          </linearGradient>
        </defs>
        
        {/* Äußerer dynamischer Bogen (Mobilität) */}
        <path 
          d="M6 22C6 13.1634 13.1634 6 22 6C28.5 6 34.2 9.8 36.8 15.5" 
          stroke="url(#fintechGradient)" 
          strokeWidth="4.5" 
          strokeLinecap="round" 
        />
        
        {/* Innerer Bogen (Optimierung/Sparen) */}
        <path 
          d="M38 22C38 30.8366 30.8366 38 22 38C15.5 38 9.8 34.2 7.2 28.5" 
          stroke="#ffffff" 
          strokeWidth="4" 
          strokeLinecap="round" 
          style={{ opacity: 0.9 }}
        />
        
        {/* Der zentrale Fokuspunkt (Der smarte Core) */}
        <circle cx="22" cy="22" r="4.5" fill="url(#fintechGradient)" />
      </svg>

      {/* Typografie im echten Fintech-Stil */}
      {showText && (
        <span style={{ 
          fontSize: '1.5rem', 
          fontWeight: '300', /* Schön dünn und elegant wie bei modernen Banken */
          color: '#ffffff',
          letterSpacing: '-0.02em',
          fontFamily: 'system-ui, -apple-system, sans-serif'
        }}>
          move<span style={{ fontWeight: '700', color: '#00f2fe' }}>advisor</span>
        </span>
      )}
    </div>
  );
}