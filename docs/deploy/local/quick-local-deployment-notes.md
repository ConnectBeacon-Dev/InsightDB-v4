## This document covers local depolyment


### Make sure all the servers are stopped

- python.exe .\stop_servers.py
- del .\.env.production


PS D:\CBDPIT\RELEASE\OCT17\InsightDB-v4> python.exe .\stop_servers.py
PS D:\CBDPIT\RELEASE\OCT17\InsightDB-v4> del .\.env.production
PS D:\CBDPIT\RELEASE\OCT17\InsightDB-v4>


### Certificates for local deployment
---

#### Used pre-created certs 
---
- For local testing the certs are already stored in: InsightDB-v4/docs/deploy/local/certs



#### Create fresh certs (not required if you are using pre-created certs)
---

##### Download choco
```
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
```

##### Create Certificates
```
choco install mkcert -y
```

```
mkcert -install
```

```
mkcert mkcert schemes.ddpdashboard.gov.in login.aichatbot.schemes.ddpdashboard.gov.in chat.aichatbot.schemes.ddpdashboard.gov.in localhost 127.0.0.1 ::1
``` 



### Update local host for dns resolution
---
- on windows powershell run the script : ``` .\update_host.ps1 ```




### Nginx Launching
---

####  Download nginx & Unzip
---

- https://nginx.org/download/nginx-1.29.2.zip
- Unzip and lets assume the unzipped nginx : C:\Users\Yogesh Pandey\Downloads\nginx-1.29.2\nginx-1.29.2
- Replace the content of nginx.conf with following entries
  - Remember to change the path of ssl_certificate & ssl_certificate_key
  
```
#user  nobody;
worker_processes  1;

#error_log  logs/error.log;
#error_log  logs/error.log  notice;
#error_log  logs/error.log  info;

#pid        logs/nginx.pid;


events {
    worker_connections  1024;
}

http {
    # Basic logs
    access_log  logs/access.log;
    error_log   logs/error.log;
    
    # Fix for long server names
    server_names_hash_bucket_size 64;

    # Upstream to your apps
    upstream login_backend {
        server 127.0.0.1:5000;
        keepalive 32;
    }
    
    upstream chatbot_backend {
        server 127.0.0.1:8000;
        keepalive 32;
    }

    # WebSockets (if your app uses them)
    map $http_upgrade $connection_upgrade {
        default upgrade;
        ""      close;
    }
		
    # Login Server
    server {
        listen              443 ssl;
        http2               on;
        server_name         login.connectbeacon.com;

        ssl_certificate     "D:/CBDPIT/RELEASE/InsightDB-v4/tests/certs/connectbeacon.com+5.pem";
        ssl_certificate_key "D:/CBDPIT/RELEASE/InsightDB-v4/tests/certs/connectbeacon.com+5-key.pem";

        ssl_session_cache   shared:SSL:10m;
        ssl_session_timeout 1d;

        location / {
            proxy_pass                          http://login_backend;
            proxy_http_version                   1.1;
            proxy_set_header Host                $host;
            proxy_set_header X-Real-IP           $remote_addr;
            proxy_set_header X-Forwarded-For     $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto   https;
            proxy_set_header Connection          "";
            proxy_buffering                      off;
            proxy_read_timeout                   300s;
            proxy_send_timeout                   300s;
        }
    }

    # Chatbot Server
    server {
        listen              443 ssl;
        http2               on;
        server_name         chat.connectbeacon.com;

        ssl_certificate     "D:/CBDPIT/RELEASE/InsightDB-v4/tests/certs/connectbeacon.com+5.pem";
        ssl_certificate_key "D:/CBDPIT/RELEASE/InsightDB-v4/tests/certs/connectbeacon.com+5-key.pem";

        ssl_session_cache   shared:SSL:10m;
        ssl_session_timeout 1d;

        location / {
            proxy_pass                          http://chatbot_backend;
            proxy_http_version                   1.1;
            proxy_set_header Host                $host;
            proxy_set_header X-Real-IP           $remote_addr;
            proxy_set_header X-Forwarded-For     $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto   https;
            proxy_set_header Connection          "";
            proxy_buffering                      off;
            proxy_read_timeout                   300s;
            proxy_send_timeout                   300s;
        }

        location /ws {
            proxy_pass            http://chatbot_backend;
            proxy_http_version    1.1;
            proxy_set_header      Upgrade $http_upgrade;
            proxy_set_header      Connection $connection_upgrade;
            proxy_set_header      Host $host;
        }
    }

    # Shortcut redirect: connectbeacon.com/aichatbot -> login
    server {
        listen              443 ssl;
        http2               on;
        server_name         connectbeacon.com;

        ssl_certificate     "D:/CBDPIT/RELEASE/InsightDB-v4/tests/certs/connectbeacon.com+5.pem";
        ssl_certificate_key "D:/CBDPIT/RELEASE/InsightDB-v4/tests/certs/connectbeacon.com+5-key.pem";

        ssl_session_cache   shared:SSL:10m;
        ssl_session_timeout 1d;

        location /aichatbot {
            return 301 https://login.connectbeacon.com;
        }

        location / {
            return 404;
        }
    }

    # Optional HTTP→HTTPS redirect (only if you want it)
    server {
        listen      80;
        server_name connectbeacon.com login.connectbeacon.com chat.connectbeacon.com;
        return 301 https://$host$request_uri;
    }
}
```

#### Launch Nginx
---
```
Set-Location "C:\Users\Yogesh Pandey\Downloads\nginx-1.29.2\nginx-1.29.2"
```

```
.\nginx.exe
```

#### Stopping of Nginx
---
- taskkill /F /IM nginx.exe


### Launch the main program
---
python.exe .\deploy_production.py

### Login & query
https://connectbeacon.com/aichatbot 



## Stopping the server

- taskkill /F /IM nginx.exe
- python.exe .\stop_servers.py