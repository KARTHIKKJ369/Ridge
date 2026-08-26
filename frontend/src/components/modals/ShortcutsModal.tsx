import React from 'react';
import { X, Command } from 'lucide-react';

interface ShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface ShortcutEntry {
  keys: string[];
  description: string;
  category: string;
}

export const ShortcutsModal: React.FC<ShortcutsModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  const isMac = typeof window !== 'undefined' && navigator.platform.toUpperCase().indexOf('MAC') >= 0;
  const modKey = isMac ? '⌘' : 'Ctrl';

  const shortcuts: ShortcutEntry[] = [
    {
      keys: [modKey, 'K'],
      description: 'Start a new research ascent / conversation',
      category: 'Navigation',
    },
    {
      keys: [modKey, '/'],
      description: 'Focus conversation & knowledge search bar',
      category: 'Navigation',
    },
    {
      keys: [modKey, 'Enter'],
      description: 'Submit prompt from chat input immediately',
      category: 'Chat',
    },
    {
      keys: [modKey, 'Shift', 'L'],
      description: 'Cycle theme (Stone / Void / Rust)',
      category: 'Appearance',
    },
    {
      keys: ['Esc'],
      description: 'Close open modal, previewer, or stop active stream',
      category: 'General',
    },
    {
      keys: ['?'],
      description: 'Toggle this keyboard shortcuts cheat-sheet',
      category: 'General',
    },
  ];

  return (
    <div className="recall-modal-backdrop" onClick={onClose}>
      <div
        className="recall-modal-card shortcuts-modal-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div className="modal-title-wrap">
            <div className="modal-icon-badge local">
              <Command size={18} />
            </div>
            <div>
              <h3 className="modal-source-title">Keyboard Shortcuts</h3>
              <p className="modal-sub-label">Power tools for rapid research navigation</p>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close shortcuts modal">
            <X size={18} />
          </button>
        </div>

        <div className="modal-body-area">
          <div className="shortcuts-table">
            {shortcuts.map((s, idx) => (
              <div key={idx} className="shortcut-row">
                <div className="shortcut-desc">
                  <span className="shortcut-text">{s.description}</span>
                  <span className="shortcut-cat-chip">{s.category}</span>
                </div>
                <div className="shortcut-keys">
                  {s.keys.map((k, kIdx) => (
                    <React.Fragment key={kIdx}>
                      <kbd className="shortcut-kbd">{k}</kbd>
                      {kIdx < s.keys.length - 1 && <span className="kbd-plus">+</span>}
                    </React.Fragment>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="modal-footer-area">
          <span className="grounding-audit-note">
            Tip: Press <kbd className="shortcut-kbd-inline">?</kbd> anywhere outside inputs to view shortcuts.
          </span>
          <button type="button" className="btn-secondary modal-done-btn" onClick={onClose}>
            Got it
          </button>
        </div>
      </div>
    </div>
  );
};
