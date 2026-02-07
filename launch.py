import subprocess
import sys
import os
import time

def launch():
    print("📟 Launching Project Synapse Stack...")
    
    frontend = subprocess.Popen(["npm", "run", "dev"], 
                                cwd=portal_path,
                                shell=shell,
                                text=True)

    backend = subprocess.Popen([sys.executable, "synapse_platform.py"], 
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
