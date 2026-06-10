import { useEffect, useState } from 'react'
import { useRulesStore, Rule } from '../../store/rules'
import RuleEditor from './RuleEditor'

export default function RulesPage() {
  const { rules, loading, fetchRules, deleteRule, selectedRule, selectRule, isEditing, isCreating, setEditing, setCreating } = useRulesStore()
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  useEffect(() => { fetchRules() }, [])

  const handleEdit = (rule: Rule) => {
    selectRule(rule)
    setEditing(true)
  }

  const handleDelete = async (id: string) => {
    await deleteRule(id)
    setDeleteConfirm(null)
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Alarm Rules</h2>
        <button
          onClick={() => setCreating(true)}
          style={{
            padding: '8px 16px', border: 'none', borderRadius: 4,
            background: '#1976d2', color: '#fff', cursor: 'pointer', fontSize: 14,
          }}
        >
          + Create Rule
        </button>
      </div>

      <div style={{ background: '#fff', borderRadius: 8, padding: 16 }}>
        {loading && <p style={{ color: '#888' }}>Loading...</p>}
        {!loading && rules.length === 0 && (
          <p style={{ color: '#888' }}>No alarm rules configured yet.</p>
        )}
        {!loading && rules.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f5f5f5' }}>
                <th style={{ padding: 10, textAlign: 'left' }}>Name</th>
                <th style={{ padding: 10, textAlign: 'left' }}>Severity</th>
                <th style={{ padding: 10, textAlign: 'left' }}>Target</th>
                <th style={{ padding: 10, textAlign: 'center' }}>Enabled</th>
                <th style={{ padding: 10, textAlign: 'center' }}>Version</th>
                <th style={{ padding: 10, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={{ padding: 10 }}>{rule.name}</td>
                  <td style={{ padding: 10 }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: 3,
                      background: rule.severity === 'critical' ? '#ffebee' :
                                  rule.severity === 'warning' ? '#fff3e0' : '#e3f2fd',
                      fontSize: 12,
                    }}>
                      {rule.severity}
                    </span>
                  </td>
                  <td style={{ padding: 10, fontSize: 13 }}>
                    {rule.target?.scope as string}: {(rule.target?.group_id as string) || 'all'}
                  </td>
                  <td style={{ padding: 10, textAlign: 'center' }}>
                    {rule.enabled ? 'Yes' : 'No'}
                  </td>
                  <td style={{ padding: 10, textAlign: 'center', color: '#888', fontSize: 12 }}>
                    v{rule.version}
                  </td>
                  <td style={{ padding: 10, textAlign: 'right' }}>
                    <button
                      onClick={() => handleEdit(rule)}
                      style={{
                        padding: '4px 10px', marginRight: 6, border: '1px solid #1976d2',
                        borderRadius: 3, background: '#fff', color: '#1976d2', cursor: 'pointer', fontSize: 12,
                      }}
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(rule.id)}
                      style={{
                        padding: '4px 10px', border: '1px solid #d32f2f',
                        borderRadius: 3, background: '#fff', color: '#d32f2f', cursor: 'pointer', fontSize: 12,
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Editor Modal */}
      {isEditing && selectedRule && (
        <RuleEditor
          rule={selectedRule}
          mode="edit"
          onClose={() => { setEditing(false); selectRule(null) }}
        />
      )}
      {isCreating && (
        <RuleEditor
          rule={null}
          mode="create"
          onClose={() => setCreating(false)}
        />
      )}

      {/* Delete Confirmation */}
      {deleteConfirm && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
        }}>
          <div style={{
            background: '#fff', borderRadius: 8, padding: 24, maxWidth: 380, width: '90%',
          }}>
            <h3 style={{ margin: '0 0 12px' }}>Delete Rule</h3>
            <p style={{ margin: '0 0 20px', color: '#555' }}>
              Are you sure? This action cannot be undone.
            </p>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setDeleteConfirm(null)}
                style={{
                  padding: '8px 16px', border: '1px solid #ccc', borderRadius: 4,
                  background: '#fff', cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                style={{
                  padding: '8px 16px', border: 'none', borderRadius: 4,
                  background: '#d32f2f', color: '#fff', cursor: 'pointer',
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
