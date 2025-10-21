#!/usr/bin/env python3
"""
deploy.py - Unified Production Deployment Script

ONE SCRIPT TO RULE THEM ALL!
This script handles everything:
  1. Secret generation and management (.env.production)
  2. Virtual environment setup
  3. Dependency installation
  4. ETL pipeline execution (optional)
  5. Server launching (calls run_pipeline_and_serve.py)

═══════════════════════════════════════════════════════════════════════════
TWO INTEGRATION SCENARIOS:
═══════════════════════════════════════════════════════════════════════════

A) EMBEDDED CHATBOT (in your existing webpage):
   ┌─────────────────────────────────────────────────────────────────────┐
   │ Your Webpage (already has user login)                               │
   │                                                                      │
   │  [💬 Chat Button] ← User clicks                                     │
   │         ↓                                                            │
   │  JavaScript: fetch('/api/chatbot-token')  ← Gets JWT                │
   │         ↓                                                            │
   │  Backend: Returns JWT with user info (sub, name, email)             │
   │         ↓                                                            │
   │  <iframe src="http://localhost:8000/aichat/sso?token=JWT">          │
   │         ↓                                                            │
   │  Chatbot validates JWT → User auto-logged in! ✓                     │
   │                                                                      │
   │  Example: http://localhost:8000/examples/chatbot_embedded_local.html│
   └─────────────────────────────────────────────────────────────────────┘

B) STANDALONE (separate login page):
   ┌─────────────────────────────────────────────────────────────────────┐
   │ User visits: http://localhost:5000/                                  │
   │         ↓                                                            │
   │  Login Page: Enter User ID, Name, Email                             │
   │         ↓                                                            │
   │  Click "Continue to Chatbot"                                         │
   │         ↓                                                            │
   │  Backend generates JWT with user info                                │
   │         ↓                                                            │
   │  Redirect to: http://localhost:8000/aichat/sso?token=JWT            │
   │         ↓                                                            │
   │  Chatbot validates JWT → User logged in! ✓                          │
   └─────────────────────────────────────────────────────────────────────┘

Both scenarios use the SAME /api/chatbot-token endpoint!
The JWT token contains: {sub: user_id, name: name, email: email, ...}

═══════════════════════════════════════════════════════════════════════════

Usage:
    # Production deployment (auto-generates secret, skips ETL)
    python deploy.py
    
    # First time with ETL
    python deploy.py --with-etl
    
    # Development mode (foreground, with ETL)
    python deploy.py --dev
    
    # Custom configuration
    python deploy.py --port 9000 --login-port 6000
    
    # Without SSO (no authentication, single server)
    python deploy.py --no-sso

What happens:
    1. Generates/loads SSO secret → .env.production
    2. Sets up virtual environment if needed
    3. Loads environment variables
    4. Calls run_pipeline_and_serve.py with appropriate flags
    5. Servers start in background
    6. Access URLs displayed
"""

import os
import sys
import secrets
import string
import subprocess
import argparse
import time
import socket
from pathlib import Path

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

REPO = Path(__file__).resolve().parent
CONFIG_FILE = REPO / ".env.production"

# ============================================================================
# SECRET MANAGEMENT
# ============================================================================

def generate_secret(length=64):
    """Generate a cryptographically secure random secret"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def load_or_create_secret():
    """Load existing secret from .env.production or create a new one"""
    if CONFIG_FILE.exists():
        print(f"[INFO] Loading configuration from: {CONFIG_FILE}")
        with open(CONFIG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('SSO_SHARED_SECRET='):
                    secret = line.split('=', 1)[1]
                    print("[OK] Using existing SSO_SHARED_SECRET")
                    return secret
    
    # Generate new secret
    print("[INFO] No existing secret found. Generating new one...")
    secret = generate_secret(64)
    
    # Save to file
    with open(CONFIG_FILE, 'w') as f:
        f.write(f"# ConnectBeacon Production Configuration\n")
        f.write(f"# Generated automatically - DO NOT COMMIT TO GIT\n\n")
        f.write(f"SSO_SHARED_SECRET={secret}\n")
        f.write(f"CHATBOT_URL=https://chat.aichatbot.schemes.ddpdashboard.gov.in/aichat/sso\n")
        f.write(f"LOGIN_URL=https://login.aichatbot.schemes.ddpdashboard.gov.in\n")
        f.write(f"SERVER_HOST=0.0.0.0\n")
        f.write(f"PORT=8000\n")
        f.write(f"LOGIN_PORT=5000\n")
        f.write(f"SSO_EXPECT_ISS=ddpdashboard-aichatbot-portal\n")
        f.write(f"SSO_EXPECT_AUD=aichat\n")
        f.write(f"TOKEN_EXPIRY=3600\n")
    
    print(f"[OK] New secret generated and saved to: {CONFIG_FILE}")
    print(f"[SECRET] {secret}")
    print("[IMPORTANT] Keep this secret secure and backed up!")
    
    return secret

def load_environment():
    """Load environment variables from .env.production and config.yaml"""
    if not CONFIG_FILE.exists():
        print(f"[ERROR] Configuration file not found: {CONFIG_FILE}")
        sys.exit(1)
    
    print(f"[INFO] Loading environment from: {CONFIG_FILE}")
    
    # Load from .env.production
    with open(CONFIG_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value
                if key != 'SSO_SHARED_SECRET':  # Don't print secret
                    print(f"  {key}={value}")
    
    # Also load URLs from config.yaml if not in environment
    config_yaml = REPO / "config.yaml"
    if config_yaml.exists():
        import yaml
        with open(config_yaml, 'r') as f:
            cfg = yaml.safe_load(f) or {}
            urls = cfg.get('urls', {})
            
            # Set URLs from config.yaml if not already in environment
            if 'LOGIN_URL' not in os.environ and urls.get('login'):
                os.environ['LOGIN_URL'] = urls['login']
                print(f"  LOGIN_URL={urls['login']} (from config.yaml)")
            
            if 'CHATBOT_URL' not in os.environ and urls.get('chatbot_sso'):
                os.environ['CHATBOT_URL'] = urls['chatbot_sso']
                print(f"  CHATBOT_URL={urls['chatbot_sso']} (from config.yaml)")

# ============================================================================
# VIRTUAL ENVIRONMENT SETUP
# ============================================================================

def setup_virtual_environment():
    """Create virtual environment and install dependencies if needed"""
    venv_dir = REPO / ".venv"
    venv_python = venv_dir / "Scripts" / "python.exe"
    requirements_file = REPO / "requirements.txt"
    
    # Check if venv already exists and is functional
    if venv_python.exists():
        print(f"[OK] Virtual environment found at: {venv_dir}")
        return True
    
    print("[INFO] Virtual environment not found. Creating...")
    print(f"[INFO] Target directory: {venv_dir}")
    
    # Create virtual environment
    try:
        print("[INFO] Running: python -m venv .venv")
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            check=True
        )
        print("[OK] Virtual environment created successfully")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to create virtual environment: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        sys.exit(1)
    
    # Verify venv was created
    if not venv_python.exists():
        print(f"[ERROR] Virtual environment creation failed. Python not found at: {venv_python}")
        sys.exit(1)
    
    # Install dependencies
    if requirements_file.exists():
        print(f"[INFO] Installing dependencies from: {requirements_file}")
        print("[INFO] This may take a few minutes...")
        try:
            result = subprocess.run(
                [str(venv_python), "-m", "pip", "install", "--upgrade", "pip"],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                check=True
            )
            print("[OK] pip upgraded")
            
            result = subprocess.run(
                [str(venv_python), "-m", "pip", "install", "-r", str(requirements_file)],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                check=True
            )
            print("[OK] Dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to install dependencies: {e}")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            sys.exit(1)
    else:
        print(f"[WARN] requirements.txt not found at: {requirements_file}")
        print("[WARN] Skipping dependency installation")
    
    print("[OK] Virtual environment setup complete")
    return True

# ============================================================================
# VALIDATION
# ============================================================================

def validate_configuration():
    """Validate the configuration"""
    print("\n[INFO] Validating configuration...")
    
    # Check secret
    secret = os.environ.get('SSO_SHARED_SECRET')
    if not secret or len(secret) < 32:
        print("[ERROR] SSO_SHARED_SECRET is not set or too short!")
        sys.exit(1)
    
    # Check virtual environment
    venv_python = REPO / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        print(f"[ERROR] Virtual environment not found at: {venv_python}")
        sys.exit(1)
    
    # Check config.yaml
    config_yaml = REPO / "config.yaml"
    if not config_yaml.exists():
        print(f"[WARN] config.yaml not found at: {config_yaml}")
    
    print("[OK] Configuration validated")

def display_configuration():
    """Display the production configuration"""
    print("\n" + "="*70)
    print("DEPLOYMENT CONFIGURATION")
    print("="*70)
    print(f"  Login URL:    {os.environ.get('LOGIN_URL')}")
    print(f"  Chatbot URL:  {os.environ.get('CHATBOT_URL')}")
    print(f"  Login Port:   {os.environ.get('LOGIN_PORT')} (internal)")
    print(f"  Chatbot Port: {os.environ.get('PORT')} (internal)")
    print(f"  Token Expiry: {os.environ.get('TOKEN_EXPIRY')} seconds")
    print("="*70 + "\n")

# ============================================================================
# SERVER LAUNCHING
# ============================================================================

def start_servers(args):
    """Start the production servers using run_pipeline_and_serve.py"""
    print("[INFO] Starting production servers...\n")
    
    launcher_script = REPO / "run_pipeline_and_serve.py"
    if not launcher_script.exists():
        print(f"[ERROR] Launcher script not found: {launcher_script}")
        sys.exit(1)
    
    # Build command
    venv_python = REPO / ".venv" / "Scripts" / "python.exe"
    cmd = [str(venv_python), str(launcher_script)]
    
    # Add flags based on mode
    if not args.with_etl:
        cmd.append("--skip-etl")
    
    if not args.dev:
        cmd.append("--detached")
    
    # Add custom ports if specified
    if args.port:
        cmd.extend(["--port", str(args.port)])
    if args.login_port:
        cmd.extend(["--login-port", str(args.login_port)])
    
    # Add thread counts if specified
    if args.threads:
        cmd.extend(["--threads", str(args.threads)])
    if args.login_threads:
        cmd.extend(["--login-threads", str(args.login_threads)])
    
    print(f"[CMD] {' '.join(cmd)}\n")
    
    try:
        result = subprocess.run(cmd, cwd=str(REPO), check=True)
        
        if result.returncode == 0:
            # Get configured URLs from environment
            login_url = os.environ.get('LOGIN_URL', 'http://localhost:5000')
            chatbot_url = os.environ.get('CHATBOT_URL', 'http://localhost:8000/aichat')
            login_port = os.environ.get('LOGIN_PORT', '5000')
            chatbot_port = os.environ.get('PORT', '8000')
            
            print("\n" + "="*70)
            print("SERVERS STARTED SUCCESSFULLY!")
            print("="*70)
            print("\nConfigured URLs:")
            print(f"  Login:   {login_url}")
            print(f"  Chatbot: {chatbot_url}")
            print("\nInternal URLs (Direct to Python servers):")
            print(f"  Login:   http://localhost:{login_port}")
            print(f"  Chatbot: http://localhost:{chatbot_port}")
            print("\nManagement:")
            print("  Stop servers: python stop_servers.py")
            print("  View logs:    Get-Content logs\\*.out -Wait")
            print("  Check PIDs:   Get-Content logs\\server.pids")
            print()
        else:
            print("\n[ERROR] Failed to start servers")
            print("Check logs in logs\\ directory")
            sys.exit(1)
            
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Failed to start servers: {e}")
        print("Check logs in logs\\ directory")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[ABORT] Interrupted by user")
        sys.exit(1)

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main deployment function"""
    parser = argparse.ArgumentParser(
        description="Deploy ConnectBeacon AI Chatbot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Production deployment (default)
  python deploy.py
  
  # First time with ETL
  python deploy.py --with-etl
  
  # Development mode (foreground)
  python deploy.py --dev
  
  # Custom ports
  python deploy.py --port 9000 --login-port 6000
  
  # Custom threads
  python deploy.py --threads 16 --login-threads 8
        """
    )
    
    # Deployment modes
    parser.add_argument("--dev", action="store_true",
                       help="Development mode (foreground, with ETL)")
    parser.add_argument("--with-etl", action="store_true",
                       help="Run ETL pipeline (default: skip for faster startup)")
    
    # Server configuration
    parser.add_argument("--port", type=int,
                       help="Chatbot server port (default: 8000)")
    parser.add_argument("--login-port", type=int,
                       help="Login server port (default: 5000)")
    parser.add_argument("--threads", type=int,
                       help="Chatbot server threads (default: 8)")
    parser.add_argument("--login-threads", type=int,
                       help="Login server threads (default: 4)")
    
    args = parser.parse_args()
    
    # Override with dev mode defaults
    if args.dev:
        args.with_etl = True
    
    print("="*70)
    print("ConnectBeacon AI Chatbot - Deployment")
    print("="*70)
    print()
    
    # Setup virtual environment (create if needed)
    setup_virtual_environment()
    
    # Load or create secret
    secret = load_or_create_secret()
    
    # Load all environment variables
    load_environment()
    
    # Validate configuration
    validate_configuration()
    
    # Display configuration
    display_configuration()
    
    # Start servers
    start_servers(args)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[ABORT] Deployment interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
