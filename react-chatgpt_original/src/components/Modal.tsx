import React, { PropsWithChildren, useEffect } from 'react';

interface ModalProps {
  title?: string;
  onClose: () => void;
  maxWidth?: number | string;
}

export default function Modal({ title, onClose, maxWidth = 720, children }: PropsWithChildren<ModalProps>) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    // prevent background scroll while modal is open
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title || 'Dialog'}
        style={{ maxWidth }}
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header">
          <div className="modal-title">{title}</div>
          <button className="icon-button" aria-label="Close" onClick={onClose}>✖</button>
        </div>
        <div className="modal-body">
          {children}
        </div>
      </div>
    </div>
  );
}
