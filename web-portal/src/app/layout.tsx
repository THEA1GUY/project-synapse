import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Synapse Portal",
  description: "Neural Steganography Management Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet" />
      </head>
      <body>
        <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
          {/* Sidebar */}
          <aside style={{
            width: '240px',
            background: 'var(--bg-surface)',
            borderRight: '1px solid var(--border)',
            display: 'flex',
            flexDirection: 'column',
            paddingTop: '16px'
          }}>
            <div style={{
              padding: '0 24px 24px',
              fontFamily: 'Google Sans',
              fontSize: '20px',
              fontWeight: 500,
              color: 'var(--text-primary)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <span className="material-icons" style={{ color: '#1a73e8' }}>psychology</span>
              Synapse
            </div>
            <nav>
              <a href="#" style={{
                padding: '10px 24px',
                fontSize: '14px',
                fontWeight: 500,
                color: 'var(--primary)',
                background: '#e8f0fe',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                textDecoration: 'none'
              }}>
                <span className="material-icons">build</span> Forge
              </a>
              <a href="#" style={{
                padding: '10px 24px',
                fontSize: '14px',
                fontWeight: 500,
                color: 'var(--text-secondary)',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                textDecoration: 'none'
              }}>
                <span className="material-icons">model_training</span> Models
              </a>
              <a href="#" style={{
                padding: '10px 24px',
                fontSize: '14px',
                fontWeight: 500,
                color: 'var(--text-secondary)',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                textDecoration: 'none'
              }}>
                <span className="material-icons">lock</span> Security
              </a>
            </nav>
          </aside>

          {/* Main Content */}
          <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            {/* Top Bar */}
            <header style={{
              height: '64px',
              background: 'var(--bg-surface)',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0 24px'
            }}>
              <div style={{ fontSize: '22px', fontWeight: 400 }}>Founder Portal</div>
              <div style={{ display: 'flex', gap: '16px' }}>
                <button className="btn btn-text">Help</button>
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: '#1a73e8',
                  color: 'white',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '14px',
                  fontWeight: 500
                }}>J</div>
              </div>
            </header>
            
            <div style={{ flex: 1, padding: '24px', overflowY: 'auto' }}>
              {children}
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}
