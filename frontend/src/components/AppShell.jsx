import React, { useState } from 'react'
import { Globe, RefreshCw, LogOut } from 'lucide-react'
import { greeting } from '../lib/format'

export default function AppShell({ user, lang, onToggleLang, onSwitchProfile, onLogout }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const t = (en, de) => (lang === 'de' ? de : en)

  return (
    <header className="shell">
      <div className="shell__inner content-wrap">
        <div className="shell__brand">
          <span className="brand-mark">DB</span>
          <span className="shell__name">Move<b>Optimizer</b></span>
        </div>

        <span className="shell__greeting">{greeting(user.firstName, lang)} 👋</span>

        <div className="shell__actions">
          <button className="lang-toggle" onClick={onToggleLang} aria-label={t('Switch language', 'Sprache wechseln')}>
            <Globe size={14} /> {lang === 'en' ? 'EN' : 'DE'}
          </button>

          <div className="menu-wrap">
            <button
              className="avatar-btn"
              onClick={() => setMenuOpen((o) => !o)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label={t('Account menu', 'Kontomenü')}
            >
              <span className="avatar">{user.initials}</span>
            </button>

            {menuOpen && (
              <>
                <div className="menu__backdrop" onClick={() => setMenuOpen(false)} />
                <div className="menu" role="menu">
                  <div className="menu__head">
                    <span className="avatar">{user.initials}</span>
                    <div>
                      <div className="menu__name">{user.name}</div>
                      <div className="menu__email">{user.email}</div>
                    </div>
                  </div>
                  <button className="menu__item" role="menuitem" onClick={() => { setMenuOpen(false); onSwitchProfile() }}>
                    <RefreshCw size={16} /> {t('Switch profile', 'Profil wechseln')}
                  </button>
                  <div className="menu__sep" />
                  <button className="menu__item menu__item--danger" role="menuitem" onClick={onLogout}>
                    <LogOut size={16} /> {t('Log out', 'Abmelden')}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
