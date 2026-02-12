import React, { useEffect, useMemo, useRef, useState } from 'react';
import DiagnosisForm from './components/DiagnosisForm';
import DiagnosisList from './components/DiagnosisList';
import { FeedbackProvider } from './components/ui/FeedbackProvider';

function App() {
  const [activeTab, setActiveTab] = useState('create');
  const [refreshList, setRefreshList] = useState(0);
  const [isHeaderVisible, setIsHeaderVisible] = useState(true);
  const [scrollY, setScrollY] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(0);
  const [documentHeight, setDocumentHeight] = useState(0);
  const lastScrollYRef = useRef(0);

  useEffect(() => {
    const controlLayout = () => {
      const currentY = window.scrollY;
      const currentViewport = window.innerHeight;
      const currentDocument = document.documentElement.scrollHeight;

      if (currentY > 110 && currentY > lastScrollYRef.current) {
        setIsHeaderVisible(false);
      } else {
        setIsHeaderVisible(true);
      }

      lastScrollYRef.current = currentY;
      setScrollY(currentY);
      setViewportHeight(currentViewport);
      setDocumentHeight(currentDocument);
    };

    controlLayout();
    window.addEventListener('scroll', controlLayout, { passive: true });
    window.addEventListener('resize', controlLayout);

    return () => {
      window.removeEventListener('scroll', controlLayout);
      window.removeEventListener('resize', controlLayout);
    };
  }, []);

  const handleDiagnosisCreated = () => {
    setActiveTab('list');
    setRefreshList((prev) => prev + 1);
  };

  const showScrollUp = scrollY > 280;
  const showScrollDown = useMemo(() => {
    if (!viewportHeight || !documentHeight) return false;
    return scrollY + viewportHeight < documentHeight - 280;
  }, [scrollY, viewportHeight, documentHeight]);

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const scrollToBottom = () => {
    window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' });
  };

  return (
    <FeedbackProvider>
      <div className="app-shell min-h-screen text-slate-100">
        <div className="app-orb app-orb-1" aria-hidden="true"></div>
        <div className="app-orb app-orb-2" aria-hidden="true"></div>
        <div className="app-grid-overlay" aria-hidden="true"></div>

        <header
          className={`fixed top-0 w-full z-50 app-header-shell transition-transform duration-500 ${
            isHeaderVisible ? 'translate-y-0' : '-translate-y-full'
          }`}
        >
          <div className="max-w-6xl mx-auto px-4 sm:px-6 h-[74px] flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="brand-logo-shell" aria-hidden="true">
                <div className="brand-ring"></div>
                <div className="brand-core">
                  <span className="brand-cross-h"></span>
                  <span className="brand-cross-v"></span>
                </div>
              </div>
              <div>
                <h1 className="text-base sm:text-lg font-bold tracking-tight text-white leading-none">
                  Med42 Clinical Suite
                </h1>
                <p className="text-[10px] sm:text-[11px] text-slate-300 font-medium tracking-[0.16em] uppercase">
                  Diagnostic Intelligence Console
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="text-right hidden md:block">
                <p className="text-xs font-semibold text-slate-100">Clinical Workspace</p>
                <p className="text-[10px] text-slate-300 tracking-wide uppercase">Med42-v3 + Safety Layer</p>
              </div>
              <div className="px-3 py-1.5 rounded-full border border-blue-300/30 bg-blue-500/15 text-[11px] font-semibold text-blue-100">
                AI Enabled
              </div>
            </div>
          </div>
        </header>

        <div className="pt-24 pb-16 max-w-6xl mx-auto px-4 sm:px-6 relative z-10">
          <div className="mb-6 md:mb-8 flex space-x-1.5 p-1.5 rounded-2xl w-fit mx-auto app-tab-shell">
            <button
              onClick={() => setActiveTab('create')}
              className={`px-6 py-2 rounded-xl text-sm font-semibold transition-all duration-300 ${
                activeTab === 'create'
                  ? 'bg-blue-600 text-white shadow-[0_10px_28px_rgba(37,99,235,0.38)]'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/70'
              }`}
            >
              + New Diagnosis
            </button>
            <button
              onClick={() => setActiveTab('list')}
              className={`px-6 py-2 rounded-xl text-sm font-semibold transition-all duration-300 ${
                activeTab === 'list'
                  ? 'bg-blue-600 text-white shadow-[0_10px_28px_rgba(37,99,235,0.38)]'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/70'
              }`}
            >
              Patient List
            </button>
          </div>

          <main className="animate-fadeIn app-content-panel">
            {activeTab === 'create' && <DiagnosisForm onSuccess={handleDiagnosisCreated} />}
            {activeTab === 'list' && <DiagnosisList refreshKey={refreshList} />}
          </main>
        </div>

        {(showScrollUp || showScrollDown) && (
          <div className="scroll-controls">
            {showScrollUp && (
              <button
                type="button"
                onClick={scrollToTop}
                className="scroll-control-btn"
                aria-label="Scroll to top"
                title="Scroll to top"
              >
                <span aria-hidden="true">^</span>
              </button>
            )}
            {showScrollDown && (
              <button
                type="button"
                onClick={scrollToBottom}
                className="scroll-control-btn"
                aria-label="Scroll to bottom"
                title="Scroll to bottom"
              >
                <span aria-hidden="true">v</span>
              </button>
            )}
          </div>
        )}

        <footer className="app-footer-shell relative z-10">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-slate-100">Med42 Clinical Suite</p>
              <p className="text-xs text-slate-300">AI-assisted decision support for physicians</p>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-200">
              <span className="status-dot active"></span>
              <span>System Ready</span>
            </div>
          </div>
        </footer>
      </div>
    </FeedbackProvider>
  );
}

export default App;

