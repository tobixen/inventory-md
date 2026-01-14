# Installation

There are several ways to install and run the inventory system, depending on your needs.

## Quick Start (Local Development)

```bash
# Clone the repository
git clone https://github.com/tobixen/inventory-system.git
cd inventory-system

# Install in development mode
pip install -e .

# Initialize a new inventory
inventory-system init ~/my-inventory --name "Home Storage"

# Edit the inventory.md file
cd ~/my-inventory
editor inventory.md

# Parse and generate JSON
inventory-system parse inventory.md

# Start local web server
inventory-system serve
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

- **GitHub**: https://github.com/tobixen/puppet-inventory-system
- **Puppet Forge**: `tobixen-inventory_system` (coming soon)

Example Puppet usage:

```puppet
class { 'inventory_system':
  anthropic_api_key => lookup('inventory_system::anthropic_api_key'),
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

Configuration files go in `/etc/inventory-system/<instance>.conf`:

```bash
# Example: /etc/inventory-system/home.conf
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

### Web Server (nginx/Apache)

It's recommended to put the inventory behind a proper web server:

1. Serve static files (HTML, JS, CSS, images) directly
2. Proxy API requests to the inventory-api service
3. Add authentication (basic auth, OAuth, etc.)

Example nginx configuration:

```nginx
server {
    listen 443 ssl;
    server_name inventory.example.com;

    # Static files
    location / {
        root /var/www/inventory/home;
        index search.html;
    }

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8765/;
    }

    # Basic auth (recommended!)
    auth_basic "Inventory";
    auth_basic_user_file /etc/nginx/.htpasswd;
}
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
git remote add server user@server:/var/lib/inventory-system/home.git
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
| API Server | `inventory-system api` | Editing, AI chat |
| AI Chat | API server + ANTHROPIC_API_KEY | Web-based AI assistant |
| Shopping List | `--wanted-items` flag | Compare inventory against wanted items |
| Barcode lookup | Scripts | EAN code lookup from photos |
