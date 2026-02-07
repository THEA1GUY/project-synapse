import subprocess
import sys
import os
import time
import webbrowser

def run_cmd(cmd, cwd=None, shell=False):
    print(f"[*] Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    return subprocess.run(cmd, cwd=cwd, shell=shell, check=True)

def setup_and_launch():
    print("📟 Senatrax Synapse: Full Auto-Init Sequence Starting...")
    
    root_dir = os.getcwd()
    portal_dir = os.path.join(root_dir, "web-portal")
    is_windows = os.name == 'nt'
    shell = True if is_windows else False

    # 1. Install Python deps
    print("\n[1/3] Syncing Python dependencies...")
    run_cmd([sys.executable, "-m", "pip", "install", "-e", "."], cwd=root_dir)

    # 2. Install Node deps
    print("\n[2/3] Syncing UI dependencies (this may take a minute)...")
    if not os.path.exists(os.path.join(portal_dir, "node_modules")):
        run_cmd(["npm", "install"], cwd=portal_dir, shell=shell)
    else:
        print("[!] node_modules already exists, skipping install.")

    # 3. Launch both servers
    print("\n[3/3] Launching Engine and Portal...")
    
    # Start Backend
    backend = subprocess.Popen([sys.executable, "synapse_platform.py"], 
                               cwd=root_dir,
                               text=True)
    
    # Start Frontend
    frontend = subprocess.Popen(["npm", "run", "dev"], 
                                cwd=portal_dir,
                                shell=shell,
                                text=True)
    
    print("\n✅ All systems nominal.")
    print("🔗 Portal: http://localhost:3000")
    print("🔗 Engine: http://127.0.0.1:8000")
    
    # Wait for servers to breathe
    time.sleep(5)
    
    # 4. Open Browser automatically
    print("[*] Opening Founder Portal...")
    webbrowser.open("http://localhost:3000")

    print("\nKeep this window open. Press CTRL+C to terminate.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Shutting down servers...")
        backend.terminate()
        frontend.terminate()
        print("✅ Systems offline.")

if __name__ == "__main__":
    setup_and_launch()
