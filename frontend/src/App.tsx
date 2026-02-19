import React, { useEffect, useState } from 'react';
import ReportPage from './components/ReportPage';

const App: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:8000/api/userinfo', {
        credentials: 'include'
    })
    .then(res => {
      if (res.ok) {
        setIsAuthenticated(true);
      } else {
        setIsAuthenticated(false);
      }
      setLoading(false);
    })
    .catch(err => {
        console.error(err);
        setIsAuthenticated(false);
        setLoading(false);
    });
  }, []);

  const handleLogin = () => {
      window.location.href = "http://localhost:8000/login";
  };

  const handleLogout = () => {
      window.location.href = "http://localhost:8000/logout";
  };

  if (loading) return <div className="p-4">Loading...</div>;

  if (!isAuthenticated) {
    return (
        <div className="flex items-center justify-center h-screen bg-gray-50">
            <button onClick={handleLogin} className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">
                Login with Keycloak
            </button>
        </div>
    );
  }

  return (
    <div className="App">
       <div className="p-4 bg-gray-100 flex justify-end border-b">
           <button onClick={handleLogout} className="text-red-500 hover:text-red-700 font-semibold">Logout</button>
       </div>
      <ReportPage />
    </div>
  );
};

export default App;
