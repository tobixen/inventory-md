# Installation

There are several ways to install and run the inventory system, depending on your needs.

## Quick Start (Local Development)

```bash
# Clone the repository
git clone https://github.com/tobixen/inventory-md.git
cd inventory-md

# Install in development mode
pip install -e .

# Initialize a new inventory
inventory-md init ~/my-inventory --name "Home Storage"

# Edit the inventory.md file
cd ~/my-inventory
$EDITOR inventory.md

# Parse and generate JSON
inventory-md parse inventory.md

# Start local web server
inventory-md serve
```

Then open http://localhost:8000/search.html in your browser.

## Installation Methods

### Using pip (recommended for local use)

```bash
# From the repository
pip install -e .

# Or install in a virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### Using Make (recommended for server deployment)

The Makefile provides convenient commands for installation:

```bash
# Install in a virtual environment
make install

# View all available commands
make help
```

### Using Puppet (recommended for managed servers)

A Puppet module is available for automated deployment:

- **GitHub**: https://github.com/tobixen/puppet-inventory-md
- **Puppet Forge**: `tobixen-inventory_md` (coming soon)

Example Puppet usage:

```puppet
class { 'inventory_md':
  anthropic_api_key => lookup('inventory_md::anthropic_api_key'),
  instances         => {
    'home' => {
      datadir  => '/var/www/inventory/home',
      api_port => 8765,
    },
  },
}
```

The Puppet module handles:
- Installation from git with Python virtual environment
- Systemd service configuration
- User/group management per instance
- Git workflow with bare repositories and auto-deploy hooks

## Server Deployment

### Systemd Services

The system includes template services for running multiple instances:

- `inventory-api@.service` - API server (for chat and editing)
- `inventory-web@.service` - Static web server

Configuration files go in `/etc/inventory-md/<instance>.conf`:

```bash
# Example: /etc/inventory-md/home.conf
INVENTORY_PATH=/var/www/inventory/home
API_PORT=8765
ANTHROPIC_API_KEY=sk-ant-...  # Optional, for AI chat
```

Install and manage services:

```bash
# Install systemd templates
make install-templates

# Create a new instance
make create-instance INSTANCE=home

# Start/stop/restart
make start INSTANCE=home
make stop INSTANCE=home
make restart INSTANCE=home

# Enable auto-start on boot
make enable INSTANCE=home

# View logs
make logs INSTANCE=home
```

### Built-in Proxy (Simple Setup)

For simple setups without nginx/Apache, the `serve` command has a built-in proxy:

```bash
# Start API server in background
inventory-md api --port 8765 &

# Start web server with proxy to API
inventory-md serve --port 8000 --api-proxy localhost:8765
```

This proxies `/api/*`, `/chat`, and `/health` requests to the API backend.

**Note:** The built-in server is suitable for development and simple deployments.
For production with SSL/TLS and authentication, use nginx or Apache.

### Web Server (nginx)

For production deployments, put the inventory behind nginx:

1. Serve static files directly (better performance)
2. Proxy API requests to the inventory-api service
3. Add SSL/TLS certificates (Let's Encrypt, etc.)
4. Add authentication (basic auth, OAuth, etc.)

Example nginx configuration:

```nginx
server {
    listen 443 ssl http2;
    server_name inventory.example.com;

    # SSL certificates (e.g., from Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/inventory.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/inventory.example.com/privkey.pem;

    # Static files
    root /var/www/inventory/home;
    index search.html;

    # API proxy - all API endpoints
    location /api/ {
        proxy_pass http://127.0.0.1:8765/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Chat endpoint
    location /chat {
        proxy_pass http://127.0.0.1:8765/chat;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;  # Chat responses can take time
    }

    # Health check
    location /health {
        proxy_pass http://127.0.0.1:8765/health;
    }

    # Basic auth (recommended!)
    auth_basic "Inventory";
    auth_basic_user_file /etc/nginx/.htpasswd;

    # Exclude health check from auth (for monitoring)
    location = /health {
        auth_basic off;
        proxy_pass http://127.0.0.1:8765/health;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name inventory.example.com;
    return 301 https://$server_name$request_uri;
}
```

Create the password file:
```bash
sudo htpasswd -c /etc/nginx/.htpasswd username
```

### Web Server (Apache)

Example Apache configuration with mod_proxy:

```apache
<VirtualHost *:443>
    ServerName inventory.example.com

    # SSL
    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/inventory.example.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/inventory.example.com/privkey.pem

    # Static files
    DocumentRoot /var/www/inventory/home
    DirectoryIndex search.html

    # API proxy
    ProxyPreserveHost On
    ProxyPass /api/ http://127.0.0.1:8765/api/
    ProxyPassReverse /api/ http://127.0.0.1:8765/api/
    ProxyPass /chat http://127.0.0.1:8765/chat
    ProxyPassReverse /chat http://127.0.0.1:8765/chat
    ProxyPass /health http://127.0.0.1:8765/health
    ProxyPassReverse /health http://127.0.0.1:8765/health

    # Timeout for chat (can take time)
    ProxyTimeout 120

    # Basic auth
    <Location />
        AuthType Basic
        AuthName "Inventory"
        AuthUserFile /etc/apache2/.htpasswd
        Require valid-user
    </Location>

    # Exclude health check from auth
    <Location /health>
        Require all granted
    </Location>
</VirtualHost>
```

Enable required Apache modules:
```bash
sudo a2enmod proxy proxy_http ssl
sudo systemctl reload apache2
```

## Git Workflow

The system supports a git-based workflow for syncing inventory changes:

1. A bare repository on the server receives pushes
2. A post-receive hook auto-deploys changes to the production directory
3. The hook also regenerates `inventory.json`

Set up git hooks:

```bash
# Install hook for a specific instance
make install-hook INSTANCE=home

# Install hooks for all instances
make install-hooks
```

Push changes from your laptop:

```bash
git remote add server user@server:/var/lib/inventory-md/home.git
git push server main
```

## AI Integration

To enable AI-powered features (chat, recipe suggestions):

1. Get an API key from [Anthropic](https://console.anthropic.com/)
2. Set the `ANTHROPIC_API_KEY` environment variable or add it to the instance config
3. Start the API server

For maintaining the inventory database with Claude Code, see the [maintenance guide](MAINTENANCE.md).

## Optional Features

The system is modular - enable only what you need:

| Feature | Requires | Description |
|---------|----------|-------------|
| Search UI | Web server | JavaScript-based search interface |
| API Server | `inventory-md api` | Editing, AI chat |
| AI Chat | API server + ANTHROPIC_API_KEY | Web-based AI assistant |
| Shopping List | `--wanted-items` flag | Compare inventory against wanted items |
| Barcode lookup | Scripts | EAN code lookup from photos |
