import { NavLink } from 'react-router-dom'

export default function Header() {
  return (
    <header className="bg-surface/90 backdrop-blur-md sticky top-0 z-50 border-b-2 border-primary">
      <nav className="flex justify-between items-center h-16 px-4 md:px-6 max-w-5xl mx-auto w-full">

        {/* Logo */}
        <div className="flex items-center gap-8">
          <NavLink to="/" className="font-headline text-xl font-bold text-primary tracking-tight select-none">
            ytNotes<span className="text-secondary">Maker</span>
          </NavLink>

          {/* Desktop nav links */}
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

        {/* Avatar only */}
        <div className="w-8 h-8 rounded-full overflow-hidden border-2 border-primary">
          <div className="w-full h-full bg-primary-fixed flex items-center justify-center font-bold text-primary text-xs">
            Y
          </div>
        </div>
      </nav>
    </header>
  )
}
