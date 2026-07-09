import React from 'react'
import { Sun, Moon } from 'lucide-react'
import { useTheme } from '../context/ThemeContext.jsx'

// Kompakter Hell/Dunkel-Umschalter. `style` erlaubt Positionierung durch den Aufrufer.
export default function ThemeToggle({ style = {} }) {
  const { isDark, toggle } = useTheme()
  return (
    <button
      onClick={toggle}
      title={isDark ? 'Zu Hell wechseln' : 'Zu Dunkel wechseln'}
      aria-label="Theme umschalten"
      style={{
        width: '38px',
        height: '38px',
        borderRadius: '50%',
        border: `1px solid ${isDark ? '#26262b' : '#e3e7eb'}`,
        backgroundColor: isDark ? '#16161a' : '#ffffff',
        color: isDark ? '#00f2fe' : '#0499ad',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        flexShrink: 0,
        transition: 'all 0.2s',
        ...style,
      }}
    >
      {isDark ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  )
}