import { createRoot } from 'react-dom/client';
import { App } from './App.tsx';
import { DashboardPage } from './DashboardPage.tsx';
import './style.css';
import './dashboard.css';

const root = document.getElementById('root');
if (!root) throw new Error('Application root is missing');
const isDashboard = window.location.pathname.replace(/\/+$/, '') === '/dashboard';
document.title = isDashboard ? 'Run dashboard · The Sims 6ix' : 'Toronto in motion · The Sims 6ix';
createRoot(root).render(isDashboard ? <DashboardPage /> : <App />);
