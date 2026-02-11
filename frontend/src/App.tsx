import React, { useState, useEffect } from 'react';
import DiagnosisForm from './components/DiagnosisForm';
import DiagnosisList from './components/DiagnosisList';

function App() {
  const [activeTab, setActiveTab] = useState('create');
  const [refreshList, setRefreshList] = useState(0);
  const [isVisible, setIsVisible] = useState(true);
  const [lastScrollY, setLastScrollY] = useState(0);

  // Logic to hide header on scroll down
  useEffect(() => {
    const controlNavbar = () => {
      if (typeof window !== 'undefined') {
        if (window.scrollY > 100) { // Only trigger after scrolling a bit
          if (window.scrollY > lastScrollY) {
            setIsVisible(false); // Scroll Down -> Hide
          } else {
            setIsVisible(true);  // Scroll Up -> Show
          }
        } else {
          setIsVisible(true);
        }
        setLastScrollY(window.scrollY);
      }
    };

    window.addEventListener('scroll', controlNavbar);
    return () => window.removeEventListener('scroll', controlNavbar);
  }, [lastScrollY]);

  const handleDiagnosisCreated = () => {
    setActiveTab('list');
    setRefreshList(prev => prev + 1);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      
      {/* Sliding Header */}
      <header 
        className={`fixed top-0 w-full z-50 bg-white/90 backdrop-blur-md border-b border-slate-200 transition-transform duration-300 ${
          isVisible ? 'translate-y-0' : '-translate-y-full'
        }`}
      >
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white shadow-sm">
              <span className="text-lg">🏥</span>
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-800 leading-none">Med42-v3</h1>
              <p className="text-[10px] text-slate-500 font-medium tracking-wide">CLINICAL ASSISTANT</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right hidden sm:block">
              <p className="text-xs font-semibold text-slate-700">Dr. Smith</p>
              <p className="text-[10px] text-slate-500">Cardiology</p>
            </div>
            <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center text-xs font-bold text-slate-600">
              DS
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="pt-20 pb-12 max-w-6xl mx-auto px-4 sm:px-6">
        
        {/* Navigation Tabs (Sticky below header logic or just static) */}
        <div className="mb-6 flex space-x-1 bg-slate-200/50 p-1 rounded-xl w-fit mx-auto">
          <button
            onClick={() => setActiveTab('create')}
            className={`px-6 py-1.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'create'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'
            }`}
          >
            + New Diagnosis
          </button>
          <button
            onClick={() => setActiveTab('list')}
            className={`px-6 py-1.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'list'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'
            }`}
          >
            Patient List
          </button>
        </div>

        {/* Content Area */}
        <main className="animate-fadeIn">
          {activeTab === 'create' && (
            <DiagnosisForm onSuccess={handleDiagnosisCreated} />
          )}
          {activeTab === 'list' && (
            <DiagnosisList refreshKey={refreshList} />
          )}
        </main>
      </div>

      {/* Compact Footer */}
      <footer className="py-6 text-center border-t border-slate-200 mt-8">
        <p className="text-xs text-slate-400">
          Powered by <span className="font-semibold text-slate-600">Med42-v3</span> • Clinical Decision Support
        </p>
      </footer>
    </div>
  );
}

export default App;