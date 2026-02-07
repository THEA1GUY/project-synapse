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
  const [activeTab, setActiveTab] = useState<'forge' | 'vault' | 'terminal'>('forge');
  const [payload, setPayload] = useState('');
  const [maskName, setMaskName] = useState('');
  const [passkey, setPasskey] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ token?: string, file?: string, blob?: Blob } | null>(null);
  const [vault, setVault] = useState<ForgeResult[]>([]);
  const [receiverFile, setReceiverFile] = useState<File | null>(null);
  const [receiverPasskey, setReceiverPasskey] = useState('');
  const [receiverOutput, setReceiverOutput] = useState('');
  const [ollamaQuery, setOllamaQuery] = useState('');
  const [ollamaResponse, setOllamaResponse] = useState('');
  const [verifyTokenInput, setVerifyTokenInput] = useState('');
  const [verifyResult, setVerifyResult] = useState<{ valid: boolean, seed?: string, error?: string } | null>(null);

  const generatePasskey = () => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*';
    let pass = '';
    for (let i = 0; i < 16; i++) pass += chars.charAt(Math.floor(Math.random() * chars.length));
    setPasskey(pass);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => setPayload(event.target?.result as string);
      reader.readAsText(file);
    }
  };

  const handleUnmask = async () => {
    if (!receiverFile) return;
    setLoading(true);
    try {
      const buffer = await receiverFile.arrayBuffer();
      const engine = new SynapseEngine(receiverPasskey);
      const output = await engine.unmask(buffer);
      setReceiverOutput(output);
    } catch (error: any) {
      setReceiverOutput(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const runOllama = async () => {
    setLoading(true);
    try {
      // Send query + context to backend
      const combinedQuery = `${ollamaQuery}|CONTEXT:${receiverOutput}`;
      const response = await fetch('http://127.0.0.1:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: "LOCAL_CONTEXT", query: combinedQuery, model: "llama3" })
      });
      const data = await response.json();
      setOllamaResponse(data.response);
    } catch (error) {
      setOllamaResponse("AI Bridge Error: Backend not reachable or Ollama not running.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyToken = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://127.0.0.1:8000/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: verifyTokenInput })
      });
      const data = await response.json();
      setVerifyResult(data);
    } catch (error) {
      setVerifyResult({ valid: false, error: "Verification server unreachable." });
    } finally {
      setLoading(false);
    }
  };

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
        <button 
          onClick={() => setActiveTab('terminal')}
          style={{ 
            padding: '12px 4px', 
            background: 'none', 
            border: 'none', 
            borderBottom: activeTab === 'terminal' ? '2px solid var(--primary)' : '2px solid transparent',
            color: activeTab === 'terminal' ? 'var(--primary)' : 'var(--text-secondary)',
            fontWeight: 500,
            cursor: 'pointer'
          }}
        >Intelligence</button>
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
              <div style={{ padding: '16px', background: '#fff', borderRadius: '8px', border: '1px solid #e0e0e0', marginBottom: '16px' }}>
                <label style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-secondary)' }}>NEURAL ACCESS TOKEN</label>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '4px' }}>
                  <code style={{ flex: 1, background: '#f8f9fa', padding: '8px', borderRadius: '4px', fontSize: '12px' }}>{result.token}</code>
                  <button className="btn btn-text" onClick={() => navigator.clipboard.writeText(result.token!)}>Copy</button>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '12px' }}>
                <button className="btn btn-outline" onClick={downloadFile}>
                  <span className="material-icons" style={{ fontSize: '18px' }}>download</span> Download {result.file}
                </button>
              </div>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '24px' }}>
            <div className="card" style={{ background: '#fff' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label style={{ fontWeight: 700, textTransform: 'uppercase', fontSize: '11px', letterSpacing: '1px' }}>1. Payload</label>
                <input type="file" id="payload-file" hidden onChange={handleFileUpload} />
                <label htmlFor="payload-file" className="btn btn-text" style={{ fontSize: '10px', padding: '4px 8px' }}>Upload File</label>
              </div>
              <textarea 
                className="google-input" 
                style={{ height: '200px', marginTop: '16px' }} 
                placeholder="Paste knowledge or upload file..."
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
                  <option value="1.0">Standard (1.0x) - Recommended</option>
                  <option value="0.5">Sparse (0.5x) - Maximum Stealth</option>
                  <option value="2.0">Dense (2.0x) - High Capacity</option>
                </select>
                <p style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '8px' }}>
                  Determines how many neural layers are modified to hide the data.
                </p>
              </div>
            </div>
            <div className="card" style={{ background: '#fff' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label style={{ fontWeight: 700, textTransform: 'uppercase', fontSize: '11px', letterSpacing: '1px' }}>3. Security</label>
                <button className="btn btn-text" style={{ fontSize: '10px', padding: '4px 8px' }} onClick={generatePasskey}>Generate</button>
              </div>
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

      {activeTab === 'terminal' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' }}>
          <div>
            <div className="card" style={{ marginBottom: '32px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 500, marginBottom: '24px' }}>Incoming Intelligence</h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginBottom: '20px' }}>
                Decrypt neural masks received from other users.
              </p>
              <div className="form-group">
                <label>Received LoRA (.safetensors)</label>
                <input type="file" onChange={(e) => setReceiverFile(e.target.files?.[0] || null)} className="google-input" />
              </div>
              <div className="form-group">
                <label>Security Passkey</label>
                <input type="password" value={receiverPasskey} onChange={(e) => setReceiverPasskey(e.target.value)} className="google-input" placeholder="Passkey provided by sender" />
              </div>
              <button className="btn btn-primary" onClick={handleUnmask} disabled={loading || !receiverFile}>
                {loading ? 'Decrypting...' : 'Extract Payload'}
              </button>
              {receiverOutput && (
                <div style={{ marginTop: '24px', padding: '16px', background: '#f8f9fa', borderRadius: '8px', border: '1px solid var(--border)' }}>
                  <label style={{ fontWeight: 700, fontSize: '10px', textTransform: 'uppercase' }}>Extracted Content</label>
                  <pre style={{ whiteSpace: 'pre-wrap', fontSize: '13px', marginTop: '8px', maxHeight: '200px', overflow: 'auto' }}>{receiverOutput}</pre>
                </div>
              )}
            </div>

            <div className="card">
              <h2 style={{ fontSize: '18px', fontWeight: 500, marginBottom: '24px' }}>Token Verification</h2>
              <div className="form-group">
                <label>SYN- Access Token</label>
                <input type="text" value={verifyTokenInput} onChange={(e) => setVerifyTokenInput(e.target.value)} className="google-input" placeholder="Paste SYN- token to verify" />
              </div>
              <button className="btn btn-outline" onClick={handleVerifyToken} disabled={loading || !verifyTokenInput}>
                Verify Validity
              </button>
              {verifyResult && (
                <div style={{ marginTop: '16px', padding: '12px', borderRadius: '8px', background: verifyResult.valid ? '#e6f4ea' : '#fce8e6', color: verifyResult.valid ? '#137333' : '#c5221f' }}>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <span className="material-icons">{verifyResult.valid ? 'check_circle' : 'error'}</span>
                    <strong>{verifyResult.valid ? 'Verified Token' : 'Invalid Token'}</strong>
                  </div>
                  {verifyResult.valid && <p style={{ fontSize: '12px', marginTop: '4px' }}>Payload: {verifyResult.seed}</p>}
                  {verifyResult.error && <p style={{ fontSize: '12px', marginTop: '4px' }}>{verifyResult.error}</p>}
                </div>
              )}
            </div>
          </div>

          <div className="card" style={{ background: '#202124', color: '#fff' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 500, marginBottom: '24px', color: '#fff' }}>Ghost Chat (Ollama)</h2>
            <p style={{ color: '#9aa0a6', fontSize: '14px', marginBottom: '24px' }}>
              Interface with hidden knowledge using high-fidelity local inference.
            </p>
            <div style={{ background: '#303134', padding: '16px', borderRadius: '8px', marginBottom: '20px' }}>
              <label style={{ fontSize: '10px', color: '#9aa0a6', fontWeight: 700 }}>ACTIVE CONTEXT</label>
              <div style={{ fontSize: '13px', marginTop: '4px', color: receiverOutput ? '#8ab4f8' : '#5f6368' }}>
                {receiverOutput ? `Loaded: ${receiverOutput.substring(0, 50)}...` : 'No context unmasked. Decrypt a LoRA first.'}
              </div>
            </div>
            <div className="form-group">
              <label style={{ color: '#e8eaed' }}>Query</label>
              <input 
                type="text" 
                value={ollamaQuery} 
                onChange={(e) => setOllamaQuery(e.target.value)} 
                style={{ background: '#3c4043', border: 'none', color: '#fff', padding: '12px', borderRadius: '4px', width: '100%' }} 
                placeholder="Ask your Ghost Agent..." 
              />
            </div>
            <button className="btn btn-primary" onClick={runOllama} disabled={loading || !ollamaQuery || !receiverOutput} style={{ background: '#8ab4f8', color: '#202124' }}>
              <span className="material-icons">psychology</span> Run Inference
            </button>
            {ollamaResponse && (
              <div style={{ marginTop: '32px', borderTop: '1px solid #3c4043', paddingTop: '20px' }}>
                <label style={{ fontWeight: 700, fontSize: '10px', color: '#9aa0a6', textTransform: 'uppercase' }}>Inference Response</label>
                <div style={{ fontSize: '14px', marginTop: '12px', lineHeight: 1.6, color: '#e8eaed' }}>
                  {ollamaResponse}
                </div>
              </div>
            )}
          </div>
        </div>
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
