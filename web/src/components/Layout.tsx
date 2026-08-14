import { NavLink, Outlet } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-full px-3.5 py-1.5 text-sm transition-colors ${
    isActive ? "bg-hero text-white" : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900"
  }`;

export function Layout() {
  const { user, refresh } = useAuth();

  async function handleLogout() {
    await api.logout().catch(() => {});
    refresh();
  }

  return (
    <div className="min-h-screen bg-page">
      <header className="border-b border-hairline bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-6">
            <span className="text-lg font-normal tracking-tight text-zinc-900">
              LoL Accountability
            </span>
            <nav className="flex gap-1">
              <NavLink to="/" end className={navLinkClass}>
                Dashboard
              </NavLink>
              <NavLink to="/history" className={navLinkClass}>
                History
              </NavLink>
              <NavLink to="/templates" className={navLinkClass}>
                Tasks
              </NavLink>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-zinc-500">{user?.discord_username}</span>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-full border border-hairline px-3.5 py-1.5 text-sm text-zinc-500 transition-colors hover:bg-zinc-50 hover:text-zinc-900"
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>
    </div>
  );
}
