# Production Deployment Guide - ConnectBeacon AI Chatbot

## Overview

This guide covers deploying the AI Chatbot to production with:
- **Main Domain:** `connectbeacon.com`
- **Login:** `login.connectbeacon.com`
- **Chatbot:** `chat.connectbeacon.com`
- **Shortcut:** `connectbeacon.com/aichatbot` → redirects to chat

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Internet (HTTPS - Port 443)                               │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  connectbeacon.com/aichatbot                         │  │
│  │  → Redirects to chat.connectbeacon.com               │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Nginx Reverse Proxy (Port 443)                      │  │
│  │  • SSL/TLS Termination                               │  │
│  │  • Subdomain routing                                 │  │
│  │  • Security headers                                  │  │
│  └──────────────────────────────────────────────────────┘  │
│           │                           │                     │
│           │ HTTP                      │ HTTP                │
│           ▼                           ▼                     │
│  ┌──────────────────┐       ┌──────────────────┐          │
│  │ Login Server     │       │ Chatbot Server   │          │
│  │ Port 5000        │       │ Port 8000        │          │
│  │ (Waitress)       │       │ (Waitress)       │          │
│  └──────────────────┘       └──────────────────┘          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Customer URLs

| URL | Purpose |
|-----|---------|
| `https://login.connectbeacon.com` | Login page |
| `https://chat.connectbeacon.com/aichat/` | Chatbot interface |
| `https://connectbeacon.com/aichatbot` | Shortcut (redirects to chat) |

## Prerequisites

### 1. Domain & DNS Setup

Configure DNS records:

```
A Record:  connectbeacon.com       → Your Server IP
A Record:  login.connectbeacon.com → Your Server IP
A Record:  chat.connectbeacon.com  → Your Server IP
```

### 2. SSL Certificate

**Option A: Win-ACME (Free Let's Encrypt for Windows)**

```powershell
# Download Win-ACME from https://www.win-acme.com/
# Extract to C:\win-acme

# Run and follow prompts
cd C:\win-acme
.\wacs.exe

# Select: Create certificate (full options)
# Enter domains: connectbeacon.com, login.connectbeacon.com, chat.connectbeacon.com
# Certificate will be saved to: C:\ProgramData\win-acme\certificates
```

**Option B: Commercial Certificate**

Purchase from a CA and place files:
- Certificate: `C:\ssl\connectbeacon.com.crt`
- Private Key: `C:\ssl\connectbeacon.com.key`

### 3. Server Requirements

- **OS:** Windows Server 2016+ or Windows 10/11
- **RAM:** 8GB minimum, 16GB recommended
- **CPU:** 4 cores minimum
- **Disk:** 50GB minimum
- **Python:** 3.9+
- **Nginx:** Latest Windows version

## Installation Steps

### Step 1: Install Nginx

```powershell
# Download Nginx for Windows
# Visit: http://nginx.org/en/download.html
# Download nginx-1.24.0.zip (or latest stable)

# Extract to C:\nginx
Expand-Archive -Path nginx-1.24.0.zip -DestinationPath C:\
Rename-Item C:\nginx-1.24.0 C:\nginx
```

### Step 2: Configure Nginx

```powershell
# Copy configuration
Copy-Item nginx_connectbeacon.conf C:\nginx\conf\connectbeacon.conf

# Include it in main nginx.conf
Add-Content C:\nginx\conf\nginx.conf "`n    include connectbeacon.conf;"
```

**Update SSL certificate paths:**

Edit `C:\nginx\conf\connectbeacon.conf` and update these lines:

```nginx
ssl_certificate C:/ssl/connectbeacon.com.crt;
ssl_certificate_key C:/ssl/connectbeacon.com.key;
```

**Test and start:**

```powershell
cd C:\nginx
.\nginx.exe -t
.\nginx.exe
```

### Step 3: Configure Application

**Generate secure secret:**

```powershell
$secret = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 64 | ForEach-Object {[char]$_})
Write-Host "Your secret: $secret"
```

**Edit `deploy_production.ps1`:**

```powershell
# Set your generated secret
$env:SSO_SHARED_SECRET = "your-generated-secret-here"

# URLs are already configured for connectbeacon.com
$env:CHATBOT_URL = "https://chat.connectbeacon.com/aichat/sso"
$env:LOGIN_URL = "https://login.connectbeacon.com"
```

**Update `config.yaml`:**

```yaml
cookie:
  secure: true                      # HTTPS only
  domain: ".connectbeacon.com"      # Share across subdomains
  samesite: "Lax"
  httponly: true

sso:
  secret: "your-secret-here"        # Or use environment variable
  expect_issuer: "ddpdashboard-aichatbot-portal"
  expect_audience: "aichat"
  
redis:
  use_fake_redis: false             # Use real Redis in production
  url: "redis://localhost:6379/0"

session:
  ttl_idle: 1800                    # 30 minutes idle
  ttl_absolute: 28800               # 8 hours maximum
```

### Step 4: Install Redis (Production)

```powershell
# Download Redis for Windows
# Visit: https://github.com/tporadowski/redis/releases
# Download Redis-x64-5.0.14.1.msi

# Install and start service
Start-Service Redis

# Verify
redis-cli ping
# Should return: PONG
```

### Step 5: Deploy Application

```powershell
# Run deployment script
.\deploy_production.ps1
```

This will:
1. Validate configuration
2. Start login server (port 5000)
3. Start chatbot server (port 8000)
4. Run both in background
5. Save PIDs for management

### Step 6: Verify Deployment

**Check servers are running:**

```powershell
# Check PIDs
Get-Content logs\server.pids

# Check processes
Get-Process python

# View logs
Get-Content logs\login_server.out -Tail 20
Get-Content logs\chatbot_server.out -Tail 20
```

**Test health endpoints:**

```powershell
# Login server
curl http://localhost:5000/health

# Chatbot server
curl http://localhost:8000/aichat/health
```

**Test public URLs:**

```powershell
# Should redirect to HTTPS
curl -I http://connectbeacon.com

# Should return 200
curl -I https://login.connectbeacon.com
curl -I https://chat.connectbeacon.com/aichat/health
```

### Step 7: Test Complete Flow

1. Open browser: `https://login.connectbeacon.com`
2. Enter test credentials
3. Should redirect to: `https://chat.connectbeacon.com/aichat/`
4. Test chatbot functionality
5. Test logout
6. Test shortcut: `https://connectbeacon.com/aichatbot`

## Monitoring

### Log Files

```powershell
# Real-time monitoring
Get-Content logs\login_server.out -Wait
Get-Content logs\chatbot_server.out -Wait

# Check for errors
Select-String -Path logs\*.out -Pattern "ERROR"
```

### Health Checks

Set up automated health checks:

```powershell
# health_check.ps1
$urls = @(
    "https://login.connectbeacon.com/health",
    "https://chat.connectbeacon.com/aichat/health"
)

foreach ($url in $urls) {
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host "✓ $url - OK" -ForegroundColor Green
        }
    } catch {
        Write-Host "✗ $url - FAILED" -ForegroundColor Red
        # Send alert here
    }
}
```

### Process Monitoring

```powershell
# Check if servers are running
$pids = Get-Content logs\server.pids
foreach ($line in $pids) {
    $name, $pid = $line -split '='
    $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if ($process) {
        Write-Host "✓ $name (PID: $pid) - Running" -ForegroundColor Green
    } else {
        Write-Host "✗ $name (PID: $pid) - Not running" -ForegroundColor Red
        # Restart server here
    }
}
```

## Maintenance

### Update Application

```powershell
# 1. Stop servers
python stop_servers.py

# 2. Backup current version
Copy-Item -Path . -Destination ..\InsightDB-backup-$(Get-Date -Format 'yyyyMMdd') -Recurse

# 3. Update code
git pull  # or copy new files

# 4. Restart servers
.\deploy_production.ps1
```

### Rotate Logs

```powershell
# rotate_logs.ps1
$logDir = "logs"
$archiveDir = "logs\archive"

New-Item -ItemType Directory -Force -Path $archiveDir

$date = Get-Date -Format "yyyyMMdd"
Get-ChildItem $logDir\*.out | ForEach-Object {
    $archiveName = "$archiveDir\$($_.BaseName)_$date.log"
    Move-Item $_.FullName $archiveName -Force
}

# Restart servers to create new log files
python stop_servers.py
.\deploy_production.ps1
```

### Update SSL Certificate

```powershell
# Win-ACME auto-renews via scheduled task
# To force renewal:
cd C:\win-acme
.\wacs.exe --renew

# Reload Nginx
cd C:\nginx
.\nginx.exe -s reload
```

## Troubleshooting

### Servers Won't Start

```powershell
# Check logs
Get-Content logs\login_server.out
Get-Content logs\chatbot_server.out

# Check ports
netstat -ano | findstr "5000 8000"

# Verify environment
$env:SSO_SHARED_SECRET
$env:CHATBOT_URL
```

### Can't Access from Internet

```powershell
# Check firewall
Get-NetFirewallRule | Where-Object {$_.DisplayName -like "*nginx*"}

# Add rules if needed
New-NetFirewallRule -DisplayName "Nginx HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
New-NetFirewallRule -DisplayName "Nginx HTTPS" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow

# Check Nginx is running
Get-Process nginx
```

### SSL Certificate Issues

```powershell
# Test certificate
Test-NetConnection -ComputerName login.connectbeacon.com -Port 443

# Check certificate details
$cert = Get-ChildItem Cert:\LocalMachine\My | Where-Object {$_.Subject -like "*connectbeacon*"}
$cert | Format-List Subject, NotAfter, Thumbprint
```

### Session Issues

```powershell
# Check Redis
redis-cli ping

# View sessions
redis-cli KEYS "sess:*"

# Clear all sessions
redis-cli FLUSHDB
```

## Security Checklist

- [ ] Strong `SSO_SHARED_SECRET` (64+ characters)
- [ ] HTTPS enabled with valid certificate
- [ ] `cookie.secure: true` in config.yaml
- [ ] Firewall configured (only 80, 443 open)
- [ ] Redis password protected
- [ ] Regular security updates
- [ ] Log monitoring enabled
- [ ] Backup strategy in place
- [ ] Rate limiting configured (if needed)
- [ ] CORS properly configured

## Performance Tuning

### Nginx

```nginx
# Add to nginx.conf
worker_processes auto;
worker_connections 1024;

# Enable gzip
gzip on;
gzip_types text/plain text/css application/json application/javascript;
```

### Application

```powershell
# Increase threads for high traffic
.\deploy_production.ps1 --threads 16 --login-threads 8
```

### Redis

```powershell
# Edit C:\Program Files\Redis\redis.windows.conf
# Add these lines:
maxmemory 2gb
maxmemory-policy allkeys-lru

# Restart Redis service
Restart-Service Redis
```

## Backup Strategy

```powershell
# backup.ps1
$backupDir = "D:\Backups\InsightDB"
$date = Get-Date -Format "yyyyMMdd_HHmmss"

# Backup application
Compress-Archive -Path . -DestinationPath "$backupDir\app_$date.zip"

# Backup Redis
redis-cli SAVE
Copy-Item "C:\Program Files\Redis\dump.rdb" "$backupDir\redis_$date.rdb"

# Backup logs
Compress-Archive -Path logs -DestinationPath "$backupDir\logs_$date.zip"
```

## Support

### View All Configuration

```powershell
# Show environment
Get-ChildItem Env: | Where-Object {$_.Name -like "*SSO*" -or $_.Name -like "*CHATBOT*"}

# Show config.yaml
Get-Content config.yaml

# Show Nginx config
Get-Content nginx_connectbeacon.conf
```

### Emergency Restart

```powershell
# Stop everything
python stop_servers.py
Stop-Process -Name nginx -Force

# Start everything
Start-Process -FilePath "C:\nginx\nginx.exe" -WindowStyle Hidden
.\deploy_production.ps1
```

## Production URLs Summary

| Purpose | URL | Backend |
|---------|-----|---------|
| Main Site | `https://connectbeacon.com` | Your website |
| Chatbot Shortcut | `https://connectbeacon.com/aichatbot` | Redirect |
| Login | `https://login.connectbeacon.com` | Port 5000 |
| Chatbot | `https://chat.connectbeacon.com/aichat/` | Port 8000 |

---

**Ready to deploy?** Run: `.\deploy_production.ps1`

**Need help?** Check logs in `logs\` directory
