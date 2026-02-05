import { useEffect } from 'react';
import { Dashboard } from './components/Dashboard';

function App() {
  useEffect(() => {
    document.title = 'Intake Dashboard';
  }, []);

  return <Dashboard />;
}

export default App;
