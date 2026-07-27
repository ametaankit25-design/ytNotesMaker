import { NavLink } from 'react-router-dom'

const NAV_ITEMS = [
  { icon: 'home',    label: 'Home',    to: '/',        end: true  },
  { icon: 'history', label: 'History', to: '/history', end: false },
]

export default function BottomNav() {
  return (
    <nav className="md:hidden fixed bottom-0 left-0 w-full z-50 flex justify-around items-center h-16 bg-surface/95 backdrop-blur-md border-t-2 border-primary">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.label}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            `flex flex-col items-center justify-center transition-all active:scale-90 ${
              isActive ? 'text-primary' : 'text-outline'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <span
                className="material-symbols-outlined"
                style={{ fontVariationSettings: isActive ? "'FILL' 1" : "'FILL' 0" }}
              >
                {item.icon}
              </span>
              <span className="font-label font-bold text-xs mt-0.5 uppercase tracking-wide">
                {item.label}
              </span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}
