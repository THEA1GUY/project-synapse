import subprocess
import sys
import os
import time

def launch():
    print("📟 Launching Project Synapse Stack...")
    
    # 1. Start Python Backend
    print("[*] Starting Synapse Engine (Python)...")
    backend = subprocess.Popen([sys.executable, "synapse_platform.py"], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.STDOUT,
                               text=True,
                               encoding='utf-8')
    
    # Wait for backend to be ready
    time.sleep(3)
    
    # 2. Start Next.js Frontend
    print("[*] Starting Founder Portal (Next.js)...")
    portal_path = os.path.join(os.getcwd(), "web-portal")
    
    # Determine shell for Windows vs Unix
    shell = True if os.name == 'nt' else False
    
    frontend = subprocess.Popen(["npm", "run", "dev"], 
                                cwd=portal_path,
                                shell=shell,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                text=True)

    print("\n✅ System Online.")
    print("🔗 Engine: http://127.0.0.1:8000")
    print("🔗 Portal: http://localhost:3000")
    print("\nPress CTRL+C to kill both servers.")

    try:
        while True:
            # Simple relay of logs if needed, or just keep alive
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
        backend.terminate()
        frontend.terminate()
        print("✅ Clean exit.")

if __name__ == "__main__":
    launch()
