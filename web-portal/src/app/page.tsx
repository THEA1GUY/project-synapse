'use client';

import { useState, useEffect } from 'react';
import { SynapseEngine } from '@/lib/SynapseEngine';

interface ForgeResult {
  id: string;
  maskName: string;
  token: string;
  fileName: string;
  timestamp: number;
}

export default function SynapseDashboard() {
  const [activeTab, setActiveTab] = useState<'forge' | 'vault' | 'bridge'>('forge');
  const [payload, setPayload] = useState('');
  const [maskName, setMaskName] = useState('');
  const [passkey, setPasskey] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ token?: string, file?: string, blob?: Blob } | null>(null);
  const [vault, setVault] = useState<ForgeResult[]>([]);

  // Load vault from local storage
  useEffect(() => {
    const savedVault = localStorage.getItem('synapse_vault');
    if (savedVault) setVault(JSON.parse(savedVault));
  }, []);

  const saveToVault = (newResult: ForgeResult) => {
    const updatedVault = [newResult, ...vault];
    setVault(updatedVault);
    localStorage.setItem('synapse_vault', JSON.stringify(updatedVault));
  };

  const handleForge = async () => {
    setLoading(true);
    try {
      const engine = new SynapseEngine(passkey);
      const { filename, buffer } = await engine.forge(payload, maskName);
      const blob = new Blob([buffer], { type: 'application/octet-stream' });
      
      const mockToken = "SYN-WEB-" + btoa(JSON.stringify({ pld: maskName, exp: Date.now() + 86400000 })).substring(0, 32);

      setResult({ token: mockToken, file: filename, blob: blob });
      
      saveToVault({
        id: Math.random().toString(36).substring(7),
        maskName,
        token: mockToken,
        fileName: filename,
        timestamp: Date.now()
      });
    } catch (error) {
      console.error("Forge failed:", error);
    } finally {
      setLoading(false);
    }
  };

  const downloadFile = () => {
    if (!result?.blob || !result?.file) return;
    const url = window.URL.createObjectURL(result.blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = result.file;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      {/* Tab Navigation */}
      <div style={{ display: 'flex', gap: '32px', borderBottom: '1px solid var(--border)', marginBottom: '32px' }}>
        <button 
          onClick={() => setActiveTab('forge')}
          style={{ 
            padding: '12px 4px', 
            background: 'none', 
            border: 'none', 
            borderBottom: activeTab === 'forge' ? '2px solid var(--primary)' : '2px solid transparent',
            color: activeTab === 'forge' ? 'var(--primary)' : 'var(--text-secondary)',
            fontWeight: 500,
            cursor: 'pointer'
          }}
        >Forge</button>
        <button 
          onClick={() => setActiveTab('vault')}
          style={{ 
            padding: '12px 4px', 
            background: 'none', 
            border: 'none', 
            borderBottom: activeTab === 'vault' ? '2px solid var(--primary)' : '2px solid transparent',
            color: activeTab === 'vault' ? 'var(--primary)' : 'var(--text-secondary)',
            fontWeight: 500,
            cursor: 'pointer'
          }}
        >Neural Vault</button>
      </div>

      {activeTab === 'forge' && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
            <div>
              <h1 style={{ fontSize: '24px', fontWeight: 500 }}>The Foundry</h1>
              <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>Secure Knowledge Injection Interface</p>
            </div>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button className="btn btn-text" onClick={() => { setPayload(''); setMaskName(''); setPasskey(''); setResult(null); }}>Clear</button>
              <button className="btn btn-primary" onClick={handleForge} disabled={loading || !payload || !maskName || !passkey}>
                <span className="material-icons" style={{ fontSize: '18px' }}>bolt</span>
                {loading ? 'Forging...' : 'Forge Mask'}
              </button>
            </div>
          </div>

          {result && (
            <div className="card" style={{ borderLeft: '4px solid var(--success)', marginBottom: '32px', background: '#f6fbf7' }}>
              <h3 style={{ marginBottom: '16px', color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="material-icons">verified</span> Mask Ready
              </h3>
              <div style={{ display: 'flex', gap: '12px' }}>
                <button className="btn btn-outline" onClick={downloadFile}>
                  <span className="material-icons" style={{ fontSize: '18px' }}>download</span> Download {result.file}
                </button>
              </div>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '24px' }}>
            {/* Steps remain same as previous version but styled better */}
            <div className="card" style={{ background: '#fff' }}>
              <label style={{ fontWeight: 700, textTransform: 'uppercase', fontSize: '11px', letterSpacing: '1px' }}>1. Payload</label>
              <textarea 
                className="google-input" 
                style={{ height: '200px', marginTop: '16px' }} 
                placeholder="Paste knowledge base here..."
                value={payload}
                onChange={(e) => setPayload(e.target.value)}
              />
            </div>
            <div className="card" style={{ background: '#fff' }}>
              <label style={{ fontWeight: 700, textTransform: 'uppercase', fontSize: '11px', letterSpacing: '1px' }}>2. Identity</label>
              <div className="form-group" style={{ marginTop: '16px' }}>
                <label>Mask Name</label>
                <input type="text" className="google-input" value={maskName} onChange={(e) => setMaskName(e.target.value)} />
              </div>
              <div className="form-group">
                <label>Neural Density</label>
                <select className="google-select">
                  <option>Standard (1.0x)</option>
                  <option>Sparse (0.5x)</option>
                  <option>Dense (2.0x)</option>
                </select>
              </div>
            </div>
            <div className="card" style={{ background: '#fff' }}>
              <label style={{ fontWeight: 700, textTransform: 'uppercase', fontSize: '11px', letterSpacing: '1px' }}>3. Security</label>
              <div className="form-group" style={{ marginTop: '16px' }}>
                <label>Master Passkey</label>
                <input type="password" className="google-input" value={passkey} onChange={(e) => setPasskey(e.target.value)} />
              </div>
              <div style={{ background: '#e8f0fe', padding: '16px', borderRadius: '8px', marginTop: '24px' }}>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center', color: 'var(--primary)', marginBottom: '8px' }}>
                  <span className="material-icons">security</span>
                  <strong>Skeptic Guard</strong>
                </div>
                <p style={{ fontSize: '12px', margin: 0, color: 'var(--primary)', lineHeight: 1.4 }}>
                  Weights will be adjusted at the 6th decimal place. CRC32 integrity check will be layered into the LSB map.
                </p>
              </div>
            </div>
          </div>
        </>
      )}

      {activeTab === 'vault' && (
        <div className="card">
          <h1 style={{ fontSize: '24px', fontWeight: 500, marginBottom: '24px' }}>Neural Vault</h1>
          {vault.length === 0 ? (
            <p style={{ color: 'var(--text-secondary)' }}>No masks forged yet.</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                  <th style={{ padding: '12px' }}>Mask Name</th>
                  <th style={{ padding: '12px' }}>Token</th>
                  <th style={{ padding: '12px' }}>Date</th>
                  <th style={{ padding: '12px' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {vault.map(item => (
                  <tr key={item.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '12px' }}>{item.maskName}</td>
                    <td style={{ padding: '12px', fontFamily: 'monospace', fontSize: '11px' }}>{item.token.substring(0, 20)}...</td>
                    <td style={{ padding: '12px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                      {new Date(item.timestamp).toLocaleDateString()}
                    </td>
                    <td style={{ padding: '12px' }}>
                      <button className="btn btn-text" onClick={() => navigator.clipboard.writeText(item.token)}>Copy Token</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
