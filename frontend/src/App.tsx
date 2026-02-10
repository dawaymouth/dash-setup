import { useEffect, useState } from 'react';
import { Dashboard } from './components/Dashboard';
import { PasswordGate, getDashboardUnlocked } from './components/PasswordGate';

const STATIC_MODE = import.meta.env.VITE_STATIC_DATA === 'true';
const DASHBOARD_PASSWORD = (import.meta.env.VITE_DASHBOARD_PASSWORD as string) ?? '';

function App() {
  const [unlocked, setUnlocked] = useState(false);

  useEffect(() => {
    document.title = 'Intake Dashboard';
  }, []);

  const showGate = STATIC_MODE && DASHBOARD_PASSWORD.length > 0;
  const isUnlocked = unlocked || (showGate && getDashboardUnlocked());

  if (showGate && !isUnlocked) {
    return (
      <PasswordGate
        expectedPassword={DASHBOARD_PASSWORD}
        onUnlock={() => setUnlocked(true)}
      />
    );
  }

  return <Dashboard />;
}

export default App;
