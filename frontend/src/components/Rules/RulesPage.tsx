import { useEffect, useState } from 'react'
import { api } from '../../api/client'

export default function RulesPage() {
  const [rules, setRules] = useState<any[]>([])

  useEffect(() => {
    api.get('/api/v1/rules').then((res) => setRules(res.data)).catch(() => {})
  }, [])

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Alarm Rules</h2>
      </div>
      <div style={{ background: '#fff', borderRadius: 8, padding: 16 }}>
        {rules.length === 0 ? (
          <p style={{ color: '#888' }}>No alarm rules configured yet.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f5f5f5' }}>
                <th style={{ padding: 10, textAlign: 'left' }}>Name</th>
                <th style={{ padding: 10, textAlign: 'left' }}>Severity</th>
                <th style={{ padding: 10, textAlign: 'left' }}>Target</th>
                <th style={{ padding: 10, textAlign: 'center' }}>Enabled</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={{ padding: 10 }}>{rule.name}</td>
                  <td style={{ padding: 10 }}>
                    <span style={{
                      padding: '2px 8px',
                      borderRadius: 3,
                      background: rule.severity === 'critical' ? '#ffebee' :
                                  rule.severity === 'warning' ? '#fff3e0' : '#e3f2fd',
                      fontSize: 12,
                    }}>
                      {rule.severity}
                    </span>
                  </td>
                  <td style={{ padding: 10, fontSize: 13 }}>
                    {rule.target?.scope}: {rule.target?.group_id || 'all'}
                  </td>
                  <td style={{ padding: 10, textAlign: 'center' }}>
                    {rule.enabled ? 'Yes' : 'No'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
