import { useState, useRef } from 'react'
import Editor from '@monaco-editor/react'
import ConflictDialog from './ConflictDialog'
import { useRulesStore, Rule } from '../../store/rules'
import { api } from '../../api/client'

interface RuleEditorProps {
  rule: Rule | null
  mode: 'edit' | 'create'
  onClose: () => void
}

const RULE_TEMPLATE = `{
  "name": "New Rule",
  "description": "",
  "severity": "warning",
  "enabled": true,
  "target": {
    "scope": "org"
  },
  "trigger_condition": {
    "type": "compare",
    "metric": "temperature",
    "comparator": ">",
    "threshold": 80,
    "temporal": {
      "type": "consecutive",
      "count": 3
    }
  },
  "recovery_condition": null,
  "actions": {
    "webhook_urls": [],
    "cooldown_seconds": 300
  }
}`

function buildEditableJson(rule: Rule): string {
  const editable = {
    name: rule.name,
    description: rule.description,
    severity: rule.severity,
    enabled: rule.enabled,
    target: rule.target,
    trigger_condition: rule.trigger_condition,
    recovery_condition: rule.recovery_condition,
    actions: rule.actions,
  }
  return JSON.stringify(editable, null, 2)
}

export default function RuleEditor({ rule, mode, onClose }: RuleEditorProps) {
  const { createRule, updateRule, fetchRules, selectRule } = useRulesStore()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showConflict, setShowConflict] = useState(false)
  const editorRef = useRef<any>(null)
  const versionRef = useRef(rule?.version ?? 0)

  const initialValue = mode === 'edit' && rule ? buildEditableJson(rule) : RULE_TEMPLATE

  const handleSave = async () => {
    setError(null)
    const value = editorRef.current?.getValue()
    if (!value) return

    let parsed: any
    try {
      parsed = JSON.parse(value)
    } catch {
      setError('Invalid JSON syntax')
      return
    }

    setSaving(true)
    try {
      if (mode === 'create') {
        await createRule(parsed)
        onClose()
      } else if (rule) {
        const result = await updateRule(rule.id, parsed, versionRef.current)
        if (result === 'conflict') {
          setShowConflict(true)
        } else {
          onClose()
        }
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleReload = async () => {
    setShowConflict(false)
    if (!rule) return
    try {
      const res = await api.get(`/api/v1/rules/${rule.id}`)
      const fresh: Rule = res.data
      versionRef.current = fresh.version
      selectRule(fresh)
      if (editorRef.current) {
        editorRef.current.setValue(buildEditableJson(fresh))
      }
      await fetchRules()
    } catch {
      setError('Failed to reload rule')
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }}>
      <div style={{
        background: '#1e1e1e', borderRadius: 8, width: '80%', maxWidth: 900,
        height: '80vh', display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '12px 20px', background: '#252526', borderBottom: '1px solid #333',
        }}>
          <h3 style={{ margin: 0, color: '#fff', fontSize: 16 }}>
            {mode === 'create' ? 'Create Rule' : `Edit Rule: ${rule?.name}`}
          </h3>
          {rule && (
            <span style={{ color: '#888', fontSize: 12 }}>
              Version: {versionRef.current}
            </span>
          )}
        </div>

        {/* Editor */}
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <Editor
            height="100%"
            language="json"
            theme="vs-dark"
            defaultValue={initialValue}
            onMount={(editor) => { editorRef.current = editor }}
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              scrollBeyondLastLine: false,
              automaticLayout: true,
              tabSize: 2,
            }}
          />
        </div>

        {/* Footer */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '12px 20px', background: '#252526', borderTop: '1px solid #333',
        }}>
          <span style={{ color: '#f44336', fontSize: 13 }}>{error || ''}</span>
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              onClick={onClose}
              style={{
                padding: '8px 16px', border: '1px solid #555', borderRadius: 4,
                background: 'transparent', color: '#ccc', cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              style={{
                padding: '8px 16px', border: 'none', borderRadius: 4,
                background: saving ? '#666' : '#4caf50', color: '#fff', cursor: 'pointer',
              }}
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      </div>

      <ConflictDialog
        open={showConflict}
        onReload={handleReload}
        onClose={() => setShowConflict(false)}
      />
    </div>
  )
}
