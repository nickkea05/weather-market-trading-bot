"""
Master script to run all three data collectors (ETH, SOL, XRP) simultaneously
Each collector connects to its respective database via environment variables:
- ETH_DATABASE_URL
- SOL_DATABASE_URL
- XRP_DATABASE_URL
"""

import subprocess
import sys
import signal
import os
from pathlib import Path

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent

# Paths to the collector scripts
ETH_SCRIPT = SCRIPT_DIR / "test_postgres_stream_eth.py"
SOL_SCRIPT = SCRIPT_DIR / "test_postgres_stream_sol.py"
XRP_SCRIPT = SCRIPT_DIR / "test_postgres_stream_xrp.py"

# Store process references
processes = []

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print("\n[MASTER] Shutting down all collectors...")
    for process in processes:
        if process.poll() is None:  # Process is still running
            print(f"[MASTER] Terminating process {process.pid}...")
            process.terminate()
    
    # Wait for processes to terminate
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print(f"[MASTER] Force killing process {process.pid}...")
            process.kill()
            process.wait()
    
    print("[MASTER] All collectors stopped.")
    sys.exit(0)

def main():
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    print("=" * 60)
    print("  MULTI-ASSET DATA COLLECTOR")
    print("=" * 60)
    print("\nStarting collectors for:")
    print("  - Ethereum (ETH_DATABASE_URL)")
    print("  - Solana (SOL_DATABASE_URL)")
    print("  - XRP (XRP_DATABASE_URL)")
    print("\n" + "=" * 60 + "\n")
    
    # Check that all scripts exist
    for script, name in [(ETH_SCRIPT, "ETH"), (SOL_SCRIPT, "SOL"), (XRP_SCRIPT, "XRP")]:
        if not script.exists():
            print(f"[ERROR] {name} collector script not found: {script}")
            sys.exit(1)
    
    # Check environment variables
    env_vars = {
        "ETH_DATABASE_URL": os.getenv("ETH_DATABASE_URL"),
        "SOL_DATABASE_URL": os.getenv("SOL_DATABASE_URL"),
        "XRP_DATABASE_URL": os.getenv("XRP_DATABASE_URL")
    }
    
    missing_vars = [var for var, value in env_vars.items() if not value]
    if missing_vars:
        print("[ERROR] Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease set these in Railway or your .env file")
        sys.exit(1)
    
    print("[MASTER] All environment variables found. Starting collectors...\n")
    
    # Start each collector in a separate process
    collectors = [
        ("ETH", ETH_SCRIPT, "ETH_DATABASE_URL"),
        ("SOL", SOL_SCRIPT, "SOL_DATABASE_URL"),
        ("XRP", XRP_SCRIPT, "XRP_DATABASE_URL")
    ]
    
    for name, script, env_var in collectors:
        print(f"[MASTER] Starting {name} collector...")
        
        # Create environment for this process with only its database URL
        env = os.environ.copy()
        # Keep only the relevant DATABASE_URL for this collector
        # (each script will read its specific env var)
        
        try:
            process = subprocess.Popen(
                [sys.executable, str(script)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            processes.append(process)
            print(f"[MASTER] {name} collector started (PID: {process.pid})")
            
            # Start a thread to print output from this process
            import threading
            def print_output(proc, collector_name):
                for line in iter(proc.stdout.readline, ''):
                    if line:
                        print(f"[{collector_name}] {line.rstrip()}")
                proc.stdout.close()
            
            thread = threading.Thread(
                target=print_output,
                args=(process, name),
                daemon=True
            )
            thread.start()
            
        except Exception as e:
            print(f"[ERROR] Failed to start {name} collector: {e}")
            signal_handler(None, None)
            sys.exit(1)
    
    print("\n[MASTER] All collectors running. Press Ctrl+C to stop.\n")
    print("=" * 60 + "\n")
    
    # Monitor processes and restart if they crash
    try:
        while True:
            import time
            time.sleep(5)
            
            # Check if any process has died
            for i, process in enumerate(processes):
                if process.poll() is not None:
                    collector_name = collectors[i][0]
                    print(f"\n[MASTER] WARNING: {collector_name} collector crashed (exit code: {process.returncode})")
                    print(f"[MASTER] Restarting {collector_name} collector...")
                    
                    # Restart the process
                    name, script, env_var = collectors[i]
                    env = os.environ.copy()
                    new_process = subprocess.Popen(
                        [sys.executable, str(script)],
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )
                    processes[i] = new_process
                    
                    # Restart output thread
                    import threading
                    def print_output(proc, collector_name):
                        for line in iter(proc.stdout.readline, ''):
                            if line:
                                print(f"[{collector_name}] {line.rstrip()}")
                        proc.stdout.close()
                    
                    thread = threading.Thread(
                        target=print_output,
                        args=(new_process, name),
                        daemon=True
                    )
                    thread.start()
                    
                    print(f"[MASTER] {collector_name} collector restarted (PID: {new_process.pid})")
    
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()

