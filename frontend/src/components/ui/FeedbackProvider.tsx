import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

type ToastTone = 'success' | 'error' | 'info' | 'warning';

interface ToastItem {
  id: number;
  message: string;
  tone: ToastTone;
}

interface ConfirmOptions {
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  tone?: ToastTone;
}

interface ConfirmState extends ConfirmOptions {
  resolve: (value: boolean) => void;
}

interface FeedbackContextValue {
  notify: (message: string, tone?: ToastTone, timeoutMs?: number) => void;
  confirm: (options: ConfirmOptions) => Promise<boolean>;
}

const FeedbackContext = createContext<FeedbackContextValue | undefined>(undefined);

export const FeedbackProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null);

  const notify = useCallback((message: string, tone: ToastTone = 'info', timeoutMs = 3200) => {
    if (!message.trim()) return;
    const id = Date.now() + Math.floor(Math.random() * 1000);
    setToasts((prev) => [...prev, { id, message, tone }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, timeoutMs);
  }, []);

  const confirm = useCallback((options: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      setConfirmState({
        title: options.title || 'Please confirm',
        message: options.message,
        confirmText: options.confirmText || 'Confirm',
        cancelText: options.cancelText || 'Cancel',
        tone: options.tone || 'warning',
        resolve,
      });
    });
  }, []);

  const handleConfirm = useCallback((accepted: boolean) => {
    setConfirmState((prev) => {
      if (prev) {
        prev.resolve(accepted);
      }
      return null;
    });
  }, []);

  const contextValue = useMemo<FeedbackContextValue>(
    () => ({
      notify,
      confirm,
    }),
    [notify, confirm]
  );

  return (
    <FeedbackContext.Provider value={contextValue}>
      {children}

      <div className="feedback-toast-stack" aria-live="polite" aria-atomic="true">
        {toasts.map((toast) => (
          <div key={toast.id} className={`feedback-toast feedback-toast-${toast.tone}`}>
            <span className="feedback-toast-dot" aria-hidden="true"></span>
            <span>{toast.message}</span>
          </div>
        ))}
      </div>

      {confirmState && (
        <div className="feedback-modal-backdrop" role="presentation">
          <div className="feedback-modal-card" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
            <h3 id="confirm-title" className="feedback-modal-title">
              {confirmState.title}
            </h3>
            <p className="feedback-modal-message">{confirmState.message}</p>
            <div className="feedback-modal-actions">
              <button
                type="button"
                className="ui-btn ui-btn-ghost"
                onClick={() => handleConfirm(false)}
              >
                {confirmState.cancelText}
              </button>
              <button
                type="button"
                className={`ui-btn ${
                  confirmState.tone === 'error'
                    ? 'ui-btn-danger'
                    : confirmState.tone === 'success'
                    ? 'ui-btn-success'
                    : confirmState.tone === 'info'
                    ? 'ui-btn-primary'
                    : 'ui-btn-warning'
                }`}
                onClick={() => handleConfirm(true)}
              >
                {confirmState.confirmText}
              </button>
            </div>
          </div>
        </div>
      )}
    </FeedbackContext.Provider>
  );
};

export const useFeedback = (): FeedbackContextValue => {
  const context = useContext(FeedbackContext);
  if (!context) {
    throw new Error('useFeedback must be used inside FeedbackProvider');
  }
  return context;
};

