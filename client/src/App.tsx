import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom';
import { Header, HeaderProvider } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { Board } from './components/Board';
import { NewTaskPage } from './components/NewTaskPage';
import { TaskDetailPage } from './components/TaskDetailPage';
import { SettingsPage } from './components/SettingsPage';
import { RoutinesPage } from './components/RoutinesPage';
import { SkillsPage } from './components/SkillsPage';
import { FileBrowserPage } from './components/FileBrowserPage';
import { useTasks } from './hooks/useTasks';
import { useTheme } from './hooks/useTheme';

function AppShell() {
  useTasks();
  useTheme();

  return (
    <div className="h-screen flex overflow-hidden bg-sidebar dark:bg-zinc-950">
      <Sidebar />
      <main className="m-2 ml-0 flex-1 flex flex-col min-w-0 overflow-hidden rounded-xl border border-zinc-200 bg-surface shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <HeaderProvider>
          <Header />
          <Routes>
            <Route path="/" element={<Board />} />
            <Route path="/tasks/new" element={<NewTaskPage />} />
            <Route path="/tasks/:taskId" element={<TaskDetailPage />} />
            <Route path="/cron" element={<Navigate to="/routines" replace />} />
            <Route path="/routines" element={<RoutinesPage />} />
            <Route path="/routines/new" element={<RoutinesPage />} />
            <Route path="/routines/:routineId/edit" element={<RoutinesPage />} />
            <Route path="/routines/:routineId/runs" element={<RoutinesPage />} />
            <Route path="/routines/:routineId/runs/:runId" element={<RoutinesPage />} />
            <Route path="/routines/:routineId" element={<RoutinesPage />} />
            <Route path="/skills" element={<SkillsPage />} />
            <Route path="/files" element={<FileBrowserPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </HeaderProvider>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}
