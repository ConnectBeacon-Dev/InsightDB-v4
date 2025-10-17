#!/usr/bin/env python3
"""
stop_servers.py - Stop running login and chatbot servers

Usage:
    python stop_servers.py
"""

import os
import sys
import signal
from pathlib import Path

REPO = Path(__file__).resolve().parent
PID_FILE = REPO / "logs" / "server.pids"

def stop_servers():
    """Stop all running servers by reading PIDs from file"""
    
    if not PID_FILE.exists():
        print("[INFO] No PID file found. Servers may not be running.")
        print(f"[INFO] Expected file: {PID_FILE}")
        return
    
    print(f"[INFO] Reading PIDs from: {PID_FILE}")
    
    pids = {}
    with open(PID_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                pids[key] = int(value)
    
    if not pids:
        print("[WARN] No PIDs found in file")
        return
    
    # Stop servers
    stopped = []
    failed = []
    
    for name, pid in pids.items():
        server_name = "Login Server" if "LOGIN" in name else "Chatbot Server"
        print(f"\n[STOP] {server_name} (PID: {pid})")
        
        try:
            if os.name == 'nt':
                # Windows
                import subprocess
                result = subprocess.run(['taskkill', '/F', '/PID', str(pid)], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"[OK] {server_name} stopped")
                    stopped.append(server_name)
                else:
                    print(f"[WARN] {server_name} may not be running (PID: {pid})")
                    failed.append(server_name)
            else:
                # Unix/Linux
                os.kill(pid, signal.SIGTERM)
                print(f"[OK] {server_name} stopped")
                stopped.append(server_name)
        except ProcessLookupError:
            print(f"[WARN] {server_name} not found (PID: {pid})")
            failed.append(server_name)
        except Exception as e:
            print(f"[ERROR] Failed to stop {server_name}: {e}")
            failed.append(server_name)
    
    # Clean up PID file
    try:
        PID_FILE.unlink()
        print(f"\n[CLEANUP] Removed PID file: {PID_FILE}")
    except Exception as e:
        print(f"\n[WARN] Could not remove PID file: {e}")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    if stopped:
        print(f"✅ Stopped: {', '.join(stopped)}")
    if failed:
        print(f"⚠️  Failed/Not running: {', '.join(failed)}")
    print("\nAll done!")

if __name__ == "__main__":
    try:
        stop_servers()
    except KeyboardInterrupt:
        print("\n[ABORT] Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
