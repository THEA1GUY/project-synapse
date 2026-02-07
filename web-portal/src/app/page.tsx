'use client';

import { useState } from 'react';

export default function ForgePage() {
  const [payload, setPayload] = useState('');
  const [maskName, setMaskName] = useState('');
  const [passkey, setPasskey] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ token?: string, file?: string } | null>(null);

  const handleForge = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/forge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payload, maskName, passkey })
      });
      const data = await response.json();
      if (data.success) {
        setResult({
          token: data.token,
          file: data.filename
        });
      }
    } catch (error) {
      console.error("Forge failed:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 500 }}>Forge: Neural Steganography</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>Inject secure data payloads into functional model weights.</p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="btn btn-text" onClick={() => { setPayload(''); setMaskName(''); setPasskey(''); setResult(null); }}>Reset</button>
          <button className="btn btn-primary" onClick={handleForge} disabled={loading || !payload || !maskName || !passkey}>
            <span className="material-icons" style={{ fontSize: '18px' }}>bolt</span>
            {loading ? 'Forging...' : 'Forge Mask'}
          </button>
        </div>
      </div>

      {result ? (
        <div className="card" style={{ borderLeft: '4px solid var(--success)', marginBottom: '32px' }}>
          <h3 style={{ marginBottom: '16px', color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="material-icons">check_circle</span> Forge Successful
          </h3>
          <div className="form-group">
            <label>Neural Access Token</label>
            <div style={{ 
              background: '#f1f3f4', 
              padding: '12px', 
              borderRadius: '4px', 
              fontFamily: 'monospace', 
              fontSize: '12px',
              wordBreak: 'break-all'
            }}>
              {result.token}
            </div>
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button className="btn btn-outline">
              <span className="material-icons" style={{ fontSize: '18px' }}>download</span> Download .safetensors
            </button>
            <button className="btn btn-outline">
              <span className="material-icons" style={{ fontSize: '18px' }}>content_copy</span> Copy Token
            </button>
          </div>
        </div>
      ) : null}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '24px' }}>
        {/* Step 1: Payload */}
        <div style={{ background: '#f8f9fa', padding: '16px', borderRadius: '8px', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '16px', letterSpacing: '0.5px' }}>
            1. Define Payload
          </div>
          <div className="form-group">
            <label>Secret Data</label>
            <textarea 
              className="google-input" 
              style={{ height: '120px', resize: 'none' }}
              placeholder="Paste secret text or instructions here..."
              value={payload}
              onChange={(e) => setPayload(e.target.value)}
            />
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
            <span className="material-icons" style={{ fontSize: '16px' }}>info</span>
            <span>Synapse supports text, CSV, and binary mapping. Text/CSV is recommended for RAG.</span>
          </div>
        </div>

        {/* Step 2: Mask */}
        <div style={{ background: '#f8f9fa', padding: '16px', borderRadius: '8px', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '16px', letterSpacing: '0.5px' }}>
            2. Configure Mask
          </div>
          <div className="form-group">
            <label>Public Mask Name</label>
            <input 
              type="text" 
              className="google-input" 
              placeholder="e.g. Shakespearean_Style"
              value={maskName}
              onChange={(e) => setMaskName(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Carrier Model Type</label>
            <select className="google-select">
              <option>Llama-3-8B-LoRA</option>
              <option>Mistral-7B-v0.3</option>
              <option>Gemma-2b-Vision</option>
            </select>
          </div>
        </div>

        {/* Step 3: Security */}
        <div style={{ background: '#f8f9fa', padding: '16px', borderRadius: '8px', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '16px', letterSpacing: '0.5px' }}>
            3. Security Protocol
          </div>
          <div className="form-group">
            <label>Master Passkey</label>
            <input 
              type="password" 
              className="google-input" 
              placeholder="Minimum 8 characters..."
              value={passkey}
              onChange={(e) => setPasskey(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Token Expiry</label>
            <select className="google-select">
              <option>24 Hours</option>
              <option>7 Days</option>
              <option>Infinite (Permanent)</option>
            </select>
          </div>
          <div style={{ background: '#e8f0fe', padding: '12px', borderRadius: '4px', display: 'flex', gap: '12px' }}>
            <span className="material-icons" style={{ color: '#1a73e8', fontSize: '20px' }}>verified_user</span>
            <div style={{ fontSize: '12px', color: '#1a73e8', lineHeight: '1.4' }}>
              <strong>Skeptic Mode Enabled:</strong><br />
              CRC32 integrity check will be embedded in neural weights.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
