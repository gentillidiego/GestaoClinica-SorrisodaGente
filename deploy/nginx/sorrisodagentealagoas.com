server {
    server_name sorrisodagentealagoas.com www.sorrisodagentealagoas.com;

    # Somente respostas previamente autorizadas pelo Flask podem chegar aqui.
    location ^~ /_protected_exam_files/ {
        internal;
        alias /srv/gestaosaudeoral/uploads/;
        sendfile on;
        etag on;
        open_file_cache max=2000 inactive=60s;
        open_file_cache_valid 120s;
        open_file_cache_min_uses 1;
        add_header X-Content-Type-Options nosniff always;
    }

    location / {
        proxy_pass http://127.0.0.1:5003;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 320m;
    }

    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/sorrisodagentealagoas.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sorrisodagentealagoas.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}

server {
    if ($host = www.sorrisodagentealagoas.com) {
        return 301 https://$host$request_uri;
    }

    if ($host = sorrisodagentealagoas.com) {
        return 301 https://$host$request_uri;
    }

    listen 80;
    server_name sorrisodagentealagoas.com www.sorrisodagentealagoas.com;
    return 404;
}
