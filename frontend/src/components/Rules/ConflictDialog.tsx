interface ConflictDialogProps {
  open: boolean
  onReload: () => void
  onClose: () => void
}

export default function ConflictDialog({ open, onReload, onClose }: ConflictDialogProps) {
  if (!open) return null

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1100,
    }}>
      <div style={{
        background: '#fff', borderRadius: 8, padding: 24, maxWidth: 420, width: '90%',
        boxShadow: '0 4px 24px rgba(0,0,0,0.2)',
      }}>
        <h3 style={{ margin: '0 0 12px', color: '#d32f2f' }}>Conflict Detected (409)</h3>
        <p style={{ margin: '0 0 20px', color: '#555', lineHeight: 1.5 }}>
          This rule was modified by another user while you were editing.
          Your changes cannot be saved with the current version.
        </p>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{
              padding: '8px 16px', border: '1px solid #ccc', borderRadius: 4,
              background: '#fff', cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={onReload}
            style={{
              padding: '8px 16px', border: 'none', borderRadius: 4,
              background: '#1976d2', color: '#fff', cursor: 'pointer',
            }}
          >
            Reload Latest
          </button>
        </div>
      </div>
    </div>
  )
}
