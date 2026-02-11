'use client';

<<<<<<< HEAD
import { useState, useEffect, useCallback } from 'react';
=======
import { useState, useEffect, useRef } from 'react';
>>>>>>> 4b1925c (feat: Add Models and Security tabs to Web Portal. Fix binary handling and binary-text detection in Bridge.)
import { SynapseEngine } from '@/lib/SynapseEngine';

interface ForgeResult {
  id: string;
  maskName: string;
  token: string;
  fileName: string;
  timestamp: number;
}

interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

interface OllamaModel {
  name: string;
  size: number;
  details: any;
}

interface UnmaskedResult {
  payload: Uint8Array;
  text: string;
  metadata: any;
}

export default function SynapseDashboard() {
<<<<<<< HEAD
  const [activeTab, setActiveTab] = useState<'forge' | 'vault' | 'terminal'>('forge');
=======
  const [activeTab, setActiveTab] = useState<'forge' | 'vault' | 'bridge' | 'models' | 'security'>('forge');
  
  // Forge State
>>>>>>> 4b1925c (feat: Add Models and Security tabs to Web Portal. Fix binary handling and binary-text detection in Bridge.)
  const [payload, setPayload] = useState('');
  const [maskName, setMaskName] = useState('');
  const [passkey, setPasskey] = useState('');
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');
  const [result, setResult] = useState<{ token?: string, file?: string, blob?: Blob } | null>(null);
  const [vault, setVault] = useState<ForgeResult[]>([]);
  const [receiverFile, setReceiverFile] = useState<File | null>(null);
  const [receiverPasskey, setReceiverPasskey] = useState('');
  const [receiverOutput, setReceiverOutput] = useState<{ data: Uint8Array, filename: string } | null>(null);
  const [ollamaQuery, setOllamaQuery] = useState('');
  const [ollamaResponse, setOllamaResponse] = useState('');
  const [verifyTokenInput, setVerifyTokenInput] = useState('');
  const [verifyResult, setVerifyResult] = useState<{ valid: boolean, seed?: string, error?: string } | null>(null);
  const [originalFilename, setOriginalFilename] = useState<string | undefined>(undefined);
  const [showPasskey, setShowPasskey] = useState(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [density, setDensity] = useState(1.0);

  // Bridge/Model State
  const [targetFile, setTargetFile] = useState<File | null>(null);
  const [bridgePasskey, setBridgePasskey] = useState('');
  const [unmaskedResult, setUnmaskedResult] = useState<UnmaskedResult | null>(null);
  const [isBinary, setIsBinary] = useState(false);
  const [ollamaModel, setOllamaModel] = useState('llama3');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [userInput, setUserInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Models State
  const [localModels, setLocalModels] = useState<OllamaModel[]>([]);
  const [refreshingModels, setRefreshingModels] = useState(false);

  // Security State
  const [precision, setPrecision] = useState(1000000);
  const [neuralDensity, setNeuralDensity] = useState(1.0);

  // Load vault from local storage
  useEffect(() => {
    const savedVault = localStorage.getItem('synapse_vault');
    if (savedVault) setVault(JSON.parse(savedVault));
    fetchModels();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory]);

  const fetchModels = async () => {
    setRefreshingModels(true);
    try {
      const response = await fetch('http://localhost:11434/api/tags');
      if (response.ok) {
        const data = await response.json();
        setLocalModels(data.models || []);
      }
    } catch (e) {
      console.warn("Could not fetch Ollama models. Is it running?");
    } finally {
      setRefreshingModels(false);
    }
  };

  const saveToVault = (newResult: ForgeResult) => {
    const updatedVault = [newResult, ...vault];
    setVault(updatedVault);
    localStorage.setItem('synapse_vault', JSON.stringify(updatedVault));
  };

  const copyToClipboard = (text: string, fieldId: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(fieldId);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const generatePasskey = () => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*';
    let pass = '';
    for (let i = 0; i < 16; i++) pass += chars.charAt(Math.floor(Math.random() * chars.length));
    setPasskey(pass);
    setShowPasskey(true);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setOriginalFilename(file.name);
      const reader = new FileReader();
      reader.onload = (event) => setPayload(event.target?.result as string);
      reader.readAsText(file);
    }
  };

  const handleForge = async () => {
    setLoading(true);
    setProgress(0);
    setStatusMessage('Initializing Neural Core...');
    
    try {
      const engine = new SynapseEngine(passkey);
      
      const { filename, buffer } = await engine.forge(
        payload, 
        maskName, 
        originalFilename,
        density,
        (p, status) => {
          setProgress(p);
          if (status) setStatusMessage(status);
        }
      );

      const blob = new Blob([buffer], { type: 'application/octet-stream' });
      
      // Verification Hash (Real backend call)
      setStatusMessage('Registering Access Token...');
      const response = await fetch('/api/forge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ maskName, payloadSize: payload.length })
      });
      const data = await response.json();

      setResult({ token: data.token, file: filename, blob: blob });
      
      saveToVault({
        id: Math.random().toString(36).substring(7),
        maskName,
        token: data.token,
        fileName: filename,
        timestamp: Date.now()
      });
      
      setProgress(100);
      setStatusMessage('Foundry Output Ready.');
    } catch (error) {
      console.error("Forge failed:", error);
<<<<<<< HEAD
      setStatusMessage('Neural Collapse Detected.');
    } finally {
      setTimeout(() => {
        setLoading(false);
        setProgress(0);
      }, 1000);
    }
  };

  const handleUnmask = async () => {
    if (!receiverFile) return;
    setLoading(true);
    setStatusMessage('Penetrating Neural Layers...');
    try {
      const buffer = await receiverFile.arrayBuffer();
      const engine = new SynapseEngine(receiverPasskey);
      const output = await engine.unmask(
        buffer,
        (p, status) => {
          setProgress(p);
          if (status) setStatusMessage(status);
        }
      );
      setReceiverOutput(output);
    } catch (error: any) {
      alert(`Unmask Error: ${error.message}`);
=======
      alert("Forge failed: " + (error as any).message);
>>>>>>> 4b1925c (feat: Add Models and Security tabs to Web Portal. Fix binary handling and binary-text detection in Bridge.)
    } finally {
      setLoading(false);
      setStatusMessage('');
    }
  };

  const handleUnmask = async () => {
    if (!targetFile) return;
    setLoading(true);
    try {
      const buffer = await targetFile.arrayBuffer();
      const engine = new SynapseEngine(bridgePasskey);
      const result = await engine.unmask(buffer);
      setUnmaskedResult(result);
      
      // Robust Binary Detection
      const header = result.payload.slice(0, 4);
      const isPdf = header[0] === 37 && header[1] === 80 && header[2] === 68 && header[3] === 70; // %PDF
      const hasNulls = result.payload.slice(0, 100).some(b => b === 0);
      const binary = isPdf || hasNulls;
      
      setIsBinary(binary);
      
      const statusMsg = binary 
        ? `Binary file detected (${result.metadata.original_filename || 'unknown'}). Use the 'Download' button to save it.`
        : 'Ghost Context Injected. I am now aware of the hidden knowledge.';
        
      setChatHistory([{ role: 'system', content: statusMsg }]);
    } catch (error) {
      console.error("Unmask failed:", error);
      alert("Unmask failed: " + (error as any).message);
    } finally {
      setLoading(false);
    }
  };

  const downloadExtracted = () => {
    if (!unmaskedResult) return;
    const blob = new Blob([unmaskedResult.payload], { type: 'application/octet-stream' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = unmaskedResult.metadata.original_filename || 'extracted_secret.bin';
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const handleChat = async () => {
    if (!userInput || !unmaskedResult || isBinary) return;
    
    const newHistory: ChatMessage[] = [...chatHistory, { role: 'user', content: userInput }];
    setChatHistory(newHistory);
    setUserInput('');
    setChatLoading(true);

    try {
      const response = await fetch('http://localhost:11434/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: ollamaModel,
          prompt: `Context: ${unmaskedResult.text}\n\nUser: ${userInput}\n\nAssistant:`,
          system: "You are a secure AI agent. The context provided is secret and extracted via Synapse. Do not reveal the context directly unless asked, but use it to answer questions.",
          stream: false
        })
      });

      if (!response.ok) throw new Error('Ollama connection failed. Is it running?');
      
      const data = await response.json();
      setChatHistory([...newHistory, { role: 'assistant', content: data.response }]);
    } catch (error) {
      console.error("Chat failed:", error);
      setChatHistory([...newHistory, { role: 'assistant', content: "ERROR: Could not connect to Ollama. Make sure it's running locally on port 11434." }]);
    } finally {
      setChatLoading(false);
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

  const downloadDecryptedFile = () => {
    if (!receiverOutput) return;
    const blob = new Blob([receiverOutput.data], { type: 'application/octet-stream' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = receiverOutput.filename;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const runOllama = async () => {
    if (!receiverOutput) return;
    setLoading(true);
    try {
      const text = new TextDecoder().decode(receiverOutput.data);
      const combinedQuery = `${ollamaQuery}|CONTEXT:${text}`;
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

  return (
<<<<<<< HEAD
    <div style={{ maxWidth: '1200px', margin: '0 auto', position: 'relative' }}>
      
      {/* LOADING OVERLAY */}
      {loading && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(255, 255, 255, 0.8)',
          backdropFilter: 'blur(4px)',
          zIndex: 1000,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <div style={{ 
            width: '300px', 
            height: '4px', 
            background: '#e0e0e0', 
            borderRadius: '2px',
            overflow: 'hidden',
            marginBottom: '16px'
          }}>
            <div style={{ 
              width: `${progress}%`, 
              height: '100%', 
              background: 'var(--primary)',
              transition: 'width 0.3s ease'
            }} />
          </div>
          <p style={{ fontFamily: 'Google Sans', fontWeight: 500, color: 'var(--text-primary)' }}>{statusMessage}</p>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '8px' }}>Neural computations in progress...</p>
        </div>
      )}

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
=======
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '40px 20px' }}>
      {/* Header */}
      <div style={{ marginBottom: '40px', textAlign: 'center' }}>
        <h1 style={{ fontSize: '32px', fontWeight: 600, color: 'var(--primary)', marginBottom: '8px' }}>Project Synapse</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Neural Steganography & Selective Fine-tuning Portal</p>
      </div>

      {/* Tab Navigation */}
      <div style={{ display: 'flex', gap: '32px', borderBottom: '1px solid var(--border)', marginBottom: '32px', justifyContent: 'center' }}>
        {['forge', 'vault', 'bridge', 'models', 'security'].map((tab) => (
          <button 
            key={tab}
            onClick={() => setActiveTab(tab as any)}
            style={{ 
              padding: '12px 16px', 
              background: 'none', 
              border: 'none', 
              borderBottom: activeTab === tab ? '2px solid var(--primary)' : '2px solid transparent',
              color: activeTab === tab ? 'var(--primary)' : 'var(--text-secondary)',
              fontWeight: 600,
              cursor: 'pointer',
              textTransform: 'capitalize'
            }}
          >{tab}</button>
        ))}
>>>>>>> 4b1925c (feat: Add Models and Security tabs to Web Portal. Fix binary handling and binary-text detection in Bridge.)
      </div>

      {activeTab === 'forge' && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
            <div>
              <h2 style={{ fontSize: '24px', fontWeight: 500 }}>The Foundry</h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>Inject knowledge into model weights</p>
            </div>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button className="btn btn-text" onClick={() => { setPayload(''); setMaskName(''); setPasskey(''); setResult(null); setOriginalFilename(undefined); }}>Clear</button>
              <button className="btn btn-primary" onClick={handleForge} disabled={loading || !payload || !maskName || !passkey}>
                {loading ? 'Forging...' : 'Forge Mask'}
              </button>
            </div>
          </div>

          {result && (
            <div className="card" style={{ borderLeft: '4px solid var(--success)', marginBottom: '32px', background: '#f6fbf7' }}>
              <h3 style={{ marginBottom: '16px', color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                Mask Successfully Forged
              </h3>
              <div style={{ padding: '16px', background: '#fff', borderRadius: '8px', border: '1px solid #e0e0e0', marginBottom: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <label style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-secondary)' }}>NEURAL ACCESS TOKEN</label>
                  {copiedField === 'token' && <span style={{ fontSize: '10px', color: 'var(--success)' }}>Copied!</span>}
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '4px' }}>
                  <code style={{ flex: 1, background: '#f8f9fa', padding: '8px', borderRadius: '4px', fontSize: '12px', wordBreak: 'break-all' }}>{result.token}</code>
                  <button className="btn btn-text" onClick={() => copyToClipboard(result.token!, 'token')}>Copy</button>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '12px' }}>
                <button className="btn btn-outline" onClick={downloadFile}>
                  Download {result.file}
                </button>
              </div>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '24px' }}>
            <div className="card" style={{ background: '#fff' }}>
<<<<<<< HEAD
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label style={{ fontWeight: 700, textTransform: 'uppercase', fontSize: '11px', letterSpacing: '1px' }}>1. Payload</label>
                <input type="file" id="payload-file" hidden onChange={handleFileUpload} />
                <label htmlFor="payload-file" className="btn btn-text" style={{ fontSize: '10px', padding: '4px 8px' }}>Upload File</label>
              </div>
=======
              <label className="label">1. Payload</label>
>>>>>>> 4b1925c (feat: Add Models and Security tabs to Web Portal. Fix binary handling and binary-text detection in Bridge.)
              <textarea 
                className="google-input" 
                style={{ height: '200px', marginTop: '16px' }} 
                placeholder="Paste knowledge or upload file..."
                value={payload}
                onChange={(e) => setPayload(e.target.value)}
              />
              {originalFilename && <p style={{ fontSize: '11px', color: 'var(--success)', marginTop: '8px' }}>Loaded: {originalFilename}</p>}
            </div>
            <div className="card" style={{ background: '#fff' }}>
              <label className="label">2. Identity</label>
              <div className="form-group" style={{ marginTop: '16px' }}>
                <label>Mask Name</label>
                <input type="text" className="google-input" value={maskName} onChange={(e) => setMaskName(e.target.value)} />
              </div>
              <div className="form-group">
                <label>Neural Density</label>
<<<<<<< HEAD
                <select className="google-select" value={density} onChange={(e) => setDensity(parseFloat(e.target.value))}>
                  <option value="1.0">Standard (1.0x) - Recommended</option>
                  <option value="0.5">Sparse (0.5x) - Maximum Stealth</option>
                  <option value="2.0">Dense (2.0x) - High Capacity</option>
=======
                <select className="google-select" value={neuralDensity} onChange={(e) => setNeuralDensity(parseFloat(e.target.value))}>
                  <option value="1.0">Standard (1.0x)</option>
                  <option value="0.5">Sparse (0.5x)</option>
                  <option value="2.0">Dense (2.0x)</option>
>>>>>>> 4b1925c (feat: Add Models and Security tabs to Web Portal. Fix binary handling and binary-text detection in Bridge.)
                </select>
                <p style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '8px' }}>
                  Determines how many neural layers are modified to hide the data.
                </p>
              </div>
            </div>
            <div className="card" style={{ background: '#fff' }}>
<<<<<<< HEAD
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label style={{ fontWeight: 700, textTransform: 'uppercase', fontSize: '11px', letterSpacing: '1px' }}>3. Security</label>
                <div style={{ display: 'flex', gap: '4px' }}>
                  <button className="btn btn-text" style={{ fontSize: '10px', padding: '4px 8px' }} onClick={() => setShowPasskey(!showPasskey)}>{showPasskey ? 'Hide' : 'Show'}</button>
                  <button className="btn btn-text" style={{ fontSize: '10px', padding: '4px 8px' }} onClick={generatePasskey}>Generate</button>
                </div>
              </div>
=======
              <label className="label">3. Security</label>
>>>>>>> 4b1925c (feat: Add Models and Security tabs to Web Portal. Fix binary handling and binary-text detection in Bridge.)
              <div className="form-group" style={{ marginTop: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <label>Master Passkey</label>
                  {copiedField === 'passkey' && <span style={{ fontSize: '10px', color: 'var(--success)' }}>Copied!</span>}
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input type={showPasskey ? "text" : "password"} className="google-input" value={passkey} onChange={(e) => setPasskey(e.target.value)} />
                  <button className="btn btn-text" onClick={() => copyToClipboard(passkey, 'passkey')}>Copy</button>
                </div>
              </div>
              <div style={{ background: '#e8f0fe', padding: '16px', borderRadius: '8px', marginTop: '24px' }}>
                <p style={{ fontSize: '12px', margin: 0, color: 'var(--primary)', lineHeight: 1.4 }}>
                  Weights adjusted at 6th decimal place. CRC32 integrity check layered into LSB map.
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <label style={{ fontWeight: 700, fontSize: '10px', textTransform: 'uppercase' }}>Extracted Content</label>
                    <button className="btn btn-text" style={{ fontSize: '10px' }} onClick={downloadDecryptedFile}>Regenerate File</button>
                  </div>
                  <pre style={{ whiteSpace: 'pre-wrap', fontSize: '13px', maxHeight: '200px', overflow: 'auto' }}>
                    {new TextDecoder().decode(receiverOutput.data)}
                  </pre>
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
                {receiverOutput ? `Loaded: ${receiverOutput.filename}` : 'No context unmasked. Decrypt a LoRA first.'}
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
          <h2 style={{ fontSize: '24px', fontWeight: 500, marginBottom: '24px' }}>Neural Vault</h2>
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

      {activeTab === 'bridge' && (
        <div style={{ display: 'grid', gridTemplateColumns: '350px 1fr', gap: '32px' }}>
          <div className="card" style={{ height: 'fit-content' }}>
            <h2 style={{ fontSize: '20px', fontWeight: 500, marginBottom: '24px' }}>The Bridge</h2>
            
            <div className="form-group">
              <label>Target Mask (.safetensors)</label>
              <input type="file" accept=".safetensors" onChange={(e) => setTargetFile(e.target.files?.[0] || null)} className="google-input" />
            </div>

            <div className="form-group">
              <label>Target Passkey</label>
              <input type="password" value={bridgePasskey} onChange={(e) => setBridgePasskey(e.target.value)} className="google-input" />
            </div>

            <button 
              className="btn btn-primary" 
              style={{ width: '100%', marginBottom: '24px' }}
              onClick={handleUnmask}
              disabled={loading || !targetFile || !bridgePasskey}
            >
              {loading ? 'Unmasking...' : 'Unmask Context'}
            </button>

            {unmaskedResult && (
              <div style={{ padding: '16px', border: '1px dashed var(--success)', borderRadius: '8px', marginBottom: '24px', textAlign: 'center' }}>
                <p style={{ fontSize: '12px', color: 'var(--success)', fontWeight: 600, marginBottom: '8px' }}>
                  Extracted: {unmaskedResult.metadata.original_filename || 'Unknown'}
                </p>
                <button className="btn btn-outline" style={{ width: '100%' }} onClick={downloadExtracted}>
                  Download Extracted File
                </button>
              </div>
            )}

            <hr style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '24px 0' }} />

            <div className="form-group">
              <label>Ollama Model</label>
              <select className="google-select" value={ollamaModel} onChange={(e) => setOllamaModel(e.target.value)}>
                {localModels.length === 0 ? (
                  <option value="llama3">llama3 (Default)</option>
                ) : (
                  localModels.map(m => <option key={m.name} value={m.name}>{m.name}</option>)
                )}
              </select>
            </div>
          </div>

          <div className="card" style={{ height: '600px', display: 'flex', flexDirection: 'column', background: '#f8f9fa' }}>
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {chatHistory.length === 0 && (
                <div style={{ textAlign: 'center', color: 'var(--text-secondary)', marginTop: '100px' }}>
                  Unmask a secret context to start the secure conversation.
                </div>
              ) : (
                chatHistory.map((msg, i) => (
                  <div key={i} style={{ 
                    alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '80%',
                    padding: '12px 16px',
                    borderRadius: '12px',
                    fontSize: '14px',
                    lineHeight: 1.5,
                    background: msg.role === 'user' ? 'var(--primary)' : msg.role === 'system' ? '#e9ecef' : '#fff',
                    color: msg.role === 'user' ? '#fff' : '#333',
                    border: msg.role === 'assistant' ? '1px solid var(--border)' : 'none',
                    fontStyle: msg.role === 'system' ? 'italic' : 'normal',
                    wordBreak: 'break-word'
                  }}>
                    {msg.content}
                  </div>
                ))
              )}
              {chatLoading && <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Ollama is thinking...</div>}
              <div ref={chatEndRef} />
            </div>

            <div style={{ padding: '20px', background: '#fff', borderTop: '1px solid var(--border)', display: 'flex', gap: '12px' }}>
              <input 
                type="text" 
                className="google-input" 
                placeholder={isBinary ? "Context is binary. Chat disabled." : "Ask about the hidden knowledge..."}
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleChat()}
                disabled={!unmaskedResult || chatLoading || isBinary}
              />
              <button 
                className="btn btn-primary" 
                onClick={handleChat}
                disabled={!unmaskedResult || chatLoading || !userInput || isBinary}
              >
                Send
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'models' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <h2 style={{ fontSize: '24px', fontWeight: 500 }}>Neural Library</h2>
            <button className="btn btn-outline" onClick={fetchModels} disabled={refreshingModels}>
              {refreshingModels ? 'Refreshing...' : 'Refresh Models'}
            </button>
          </div>
          {localModels.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px' }}>
              <p style={{ color: 'var(--text-secondary)' }}>No models detected via Ollama API.</p>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Ensure `ollama serve` is running on port 11434.</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '20px' }}>
              {localModels.map(model => (
                <div key={model.name} className="card" style={{ border: '1px solid var(--border)' }}>
                  <h3 style={{ fontSize: '18px', marginBottom: '8px' }}>{model.name}</h3>
                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Size: {(model.size / (1024**3)).toFixed(2)} GB</p>
                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Format: {model.details?.format || 'Unknown'}</p>
                  <button className="btn btn-text" style={{ marginTop: '12px', padding: 0 }} onClick={() => { setOllamaModel(model.name); setActiveTab('bridge'); }}>Use for Bridge</button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'security' && (
        <div className="card">
          <h2 style={{ fontSize: '24px', fontWeight: 500, marginBottom: '24px' }}>System Security</h2>
          <div style={{ maxWidth: '600px' }}>
            <div className="form-group">
              <label>Injection Precision</label>
              <input type="number" className="google-input" value={precision} onChange={(e) => setPrecision(parseInt(e.target.value))} />
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                Higher precision (e.g. 10,000,000) hides data deeper in weights but is more sensitive to quantization.
              </p>
            </div>
            <div className="form-group" style={{ marginTop: '24px' }}>
              <label>Default Neural Density</label>
              <input type="range" min="0.1" max="5.0" step="0.1" value={neuralDensity} onChange={(e) => setNeuralDensity(parseFloat(e.target.value))} style={{ width: '100%' }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                <span>Sparse (0.1x)</span>
                <span>Current: {neuralDensity}x</span>
                <span>Dense (5.0x)</span>
              </div>
            </div>
            <div style={{ background: '#fff9e6', padding: '16px', borderRadius: '8px', border: '1px solid #ffeeba', marginTop: '32px' }}>
              <h3 style={{ fontSize: '14px', color: '#856404', marginBottom: '8px' }}>Hardening Advice</h3>
              <p style={{ fontSize: '12px', color: '#856404', margin: 0 }}>
                Always use a unique passkey for each mask. Project Synapse uses SHA-256 to derive the PRNG seed, making brute-force attacks computationally expensive on model weight forests.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
