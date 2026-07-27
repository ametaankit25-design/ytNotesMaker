import { NavLink } from 'react-router-dom'

export default function Header({ profile, onOpenProfile, theme, onToggleTheme }) {
  const initial = profile?.name ? profile.name.charAt(0).toUpperCase() : 'Y'
  const isDark = theme === 'dark'

  return (
    <header className="bg-surface/90 backdrop-blur-md sticky top-0 z-50 border-b-2 border-primary">
      <nav className="flex justify-between items-center h-16 px-4 md:px-6 max-w-5xl mx-auto w-full">

        <div className="flex items-center gap-8">
          <NavLink to="/" className="font-headline text-xl font-bold text-primary tracking-tight select-none">
            ytNotes<span className="text-secondary">Maker</span>
          </NavLink>

          <div className="hidden md:flex gap-6 items-center font-label text-sm font-bold uppercase tracking-wider">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                isActive
                  ? 'text-primary border-b-2 border-primary pb-0.5'
                  : 'text-outline hover:text-primary transition-colors'
              }
            >
              Dashboard
            </NavLink>
            <NavLink
              to="/history"
              className={({ isActive }) =>
                isActive
                  ? 'text-primary border-b-2 border-primary pb-0.5'
                  : 'text-outline hover:text-primary transition-colors'
              }
            >
              History
            </NavLink>
          </div>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <button
            type="button"
            onClick={onToggleTheme}
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            className="w-9 h-9 border-2 border-primary bg-surface-container-lowest flex items-center justify-center text-primary hover:bg-primary-fixed hover:text-on-primary-fixed transition-colors"
            style={{ boxShadow: '2px 2px 0px var(--shadow-color)' }}
          >
            <span className="material-symbols-outlined text-[20px]">
              {isDark ? 'light_mode' : 'dark_mode'}
            </span>
          </button>

          {profile && (
            <div className="hidden sm:flex flex-col items-end text-right">
              <span className="font-headline font-bold text-xs text-primary truncate max-w-[120px]">
                {profile.name}
              </span>
              <span className="text-[10px] text-outline font-mono truncate max-w-[140px]">
                {profile.education}
              </span>
            </div>
          )}

          <button
            onClick={onOpenProfile}
            title={profile ? `${profile.name} (${profile.education}) — Click to edit profile` : 'Set Profile'}
            className="w-9 h-9 rounded-full overflow-hidden border-2 border-primary bg-primary-fixed flex items-center justify-center font-bold text-on-primary-fixed text-sm hover:scale-105 transition-transform"
            style={{ boxShadow: '2px 2px 0px var(--shadow-color)' }}
          >
            {initial}
          </button>
        </div>
      </nav>
    </header>
  )
}
