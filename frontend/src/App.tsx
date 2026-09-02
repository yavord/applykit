import { useState } from 'react';
import { createHashRouter, Navigate, NavLink, Outlet, RouterProvider } from 'react-router';
import Jobs from './routes/Jobs';
import ResumeEditor from './routes/ResumeEditor';
import Resumes from './routes/Resumes';
import { getStoredTheme, toggleTheme as persistToggle } from './theme';

function Layout() {
  const [dark, setDark] = useState(getStoredTheme());

  const onToggle = () => {
    setDark(persistToggle());
  };

  return (
    <>
      <header className="topbar">
        <span className="brand">applykit</span>
        <nav className="nav" aria-label="Primary">
          <NavLink to="/jobs" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            Jobs
          </NavLink>
          <NavLink to="/resumes" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            Resumes
          </NavLink>
        </nav>
        <span className="local">
          <span className="dot" />
          Local
        </span>
        <button
          type="button"
          className="btn"
          aria-pressed={dark}
          title="Toggle theme"
          onClick={onToggle}
        >
          {dark ? 'Dark' : 'Light'}
        </button>
      </header>

      <main>
        <Outlet />
      </main>
    </>
  );
}

const router = createHashRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Navigate to="/resumes" replace /> },
      { path: 'jobs', element: <Jobs /> },
      { path: 'resumes', element: <Resumes /> },
      { path: 'resumes/:id', element: <ResumeEditor /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
