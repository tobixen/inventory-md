# Installation & Setup Guide - Multi-Instance

This guide shows how to set up the inventory system with systemd template services. You can run multiple inventory instances on one server.

## Quick Start

```bash
cd /home/tobias/inventory-system

# 1. Install template services
make install-templates

# 2. Create instances
make create-instance INSTANCE=furuset
make create-instance INSTANCE=solveig

# 3. Edit configs (set paths and API keys)
sudo nano /etc/inventory-system/furuset.conf
sudo nano /etc/inventory-system/solveig.conf

# 4. Set permissions
make set-permissions INSTANCE=furuset
make set-permissions INSTANCE=solveig

# 5. Start instances
make start-all

# 6. Enable auto-start
make enable-all
```

## Concepts

### Systemd Templates
- **Template services**: `inventory-web@.service`, `inventory-chat@.service`
- **Instance**: `inventory-web@furuset.service` (furuset = instance name)
- One template, many instances

### Per-Instance Resources
- **User**: `inventory-{instance}` (e.g., `inventory-furuset`)
- **Config**: `/etc/inventory-system/{instance}.conf`
- **Ports**: Unique per instance (avoid conflicts)

### Example Setup
```
furuset:
  - User: inventory-furuset
  - Config: /etc/inventory-system/furuset.conf
  - Path: /home/tobias/furusetalle9/inventory
  - Ports: 8000 (web), 8765 (chat)

solveig:
  - User: inventory-solveig
  - Config: /etc/inventory-system/solveig.conf
  - Path: /home/tobias/solveig/inventory-web
  - Ports: 8001 (web), 8766 (chat)
```

## Detailed Setup

### 1. Install Template Services

```bash
make install-templates
```

This installs template service files to `/etc/systemd/system/`:
- `inventory-web@.service`
- `inventory-chat@.service`

### 2. Create an Instance

```bash
make create-instance INSTANCE=furuset
```

This will:
1. Create system user `inventory-furuset`
2. Create config `/etc/inventory-system/furuset.conf`
3. Copy from `furuset.conf.example` if it exists

### 3. Edit Configuration

```bash
sudo nano /etc/inventory-system/furuset.conf
```

Configuration file format:
```bash
# Path to inventory directory (containing inventory.json)
INVENTORY_PATH=/home/tobias/furusetalle9/inventory

# Web server port (must be unique)
WEB_PORT=8000

# Chat server port (must be unique)
CHAT_PORT=8765

# Anthropic API key for chatbot
ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Set Permissions

```bash
make set-permissions INSTANCE=furuset
```

This grants the instance user read access to the inventory directory.

### 5. Start the Instance

```bash
make start INSTANCE=furuset
```

Or start both web and chat separately:
```bash
make start-web INSTANCE=furuset
make start-chat INSTANCE=furuset
```

### 6. Enable Auto-Start

```bash
make enable INSTANCE=furuset
```

The instance will now start automatically on boot.

## Makefile Commands

### Installation
```bash
make install-templates              # Install systemd templates (once)
make create-instance INSTANCE=name  # Create new instance
make set-permissions INSTANCE=name  # Set directory permissions
make quick-setup                    # Interactive setup (furuset + solveig)
```

### Instance Management
```bash
make start INSTANCE=name     # Start instance
make stop INSTANCE=name      # Stop instance
make restart INSTANCE=name   # Restart instance
make status INSTANCE=name    # Show status
make enable INSTANCE=name    # Enable auto-start
make disable INSTANCE=name   # Disable auto-start
```

### All Instances
```bash
make start-all      # Start all configured instances
make stop-all       # Stop all instances
make restart-all    # Restart all instances
make status-all     # Show status of all instances
make enable-all     # Enable all instances
make list-instances # List all configured instances
```

### Logs
```bash
make logs INSTANCE=name         # Live logs (both services)
make logs-web INSTANCE=name     # Web server logs only
make logs-chat INSTANCE=name    # Chat server logs only
```

### Individual Services
```bash
make start-web INSTANCE=name
make start-chat INSTANCE=name
make stop-web INSTANCE=name
make stop-chat INSTANCE=name
make restart-web INSTANCE=name
make restart-chat INSTANCE=name
```

## Manual Setup

If you prefer not to use the Makefile:

### Install Templates
```bash
sudo cp systemd/inventory-web@.service /etc/systemd/system/
sudo cp systemd/inventory-chat@.service /etc/systemd/system/
sudo mkdir -p /etc/inventory-system
sudo systemctl daemon-reload
```

### Create Instance
```bash
# Create user
sudo useradd -r -s /usr/bin/nologin -d /nonexistent inventory-furuset

# Create config
sudo cp systemd/furuset.conf.example /etc/inventory-system/furuset.conf
sudo nano /etc/inventory-system/furuset.conf  # Edit paths and API key

# Set permissions
sudo chgrp -R inventory-furuset /home/tobias/furusetalle9/inventory
sudo chmod -R g+rX /home/tobias/furusetalle9/inventory
```

### Start Services
```bash
sudo systemctl start inventory-web@furuset.service
sudo systemctl start inventory-chat@furuset.service
```

### Enable Auto-Start
```bash
sudo systemctl enable inventory-web@furuset.service
sudo systemctl enable inventory-chat@furuset.service
```

## Verification

### Check Status
```bash
make status INSTANCE=furuset
# or
sudo systemctl status inventory-web@furuset.service
sudo systemctl status inventory-chat@furuset.service
```

### Check Logs
```bash
make logs INSTANCE=furuset
# or
sudo journalctl -u inventory-web@furuset.service -f
sudo journalctl -u inventory-chat@furuset.service -f
```

### Test Web Server
```bash
curl http://localhost:8000/search.html
```

### Test Chat Server
```bash
curl http://localhost:8765/health
```

## Troubleshooting

### Service fails to start

1. **Check config exists**:
   ```bash
   ls -l /etc/inventory-system/furuset.conf
   ```

2. **Check config is valid**:
   ```bash
   sudo cat /etc/inventory-system/furuset.conf
   ```

3. **Check inventory directory exists**:
   ```bash
   # Get path from config
   grep INVENTORY_PATH /etc/inventory-system/furuset.conf
   ls -la /path/from/config
   ```

4. **Check permissions**:
   ```bash
   sudo -u inventory-furuset ls -la /path/to/inventory/inventory.json
   ```

5. **Check logs**:
   ```bash
   make logs INSTANCE=furuset
   ```

### Port already in use

Edit the config and change ports:
```bash
sudo nano /etc/inventory-system/furuset.conf
# Change WEB_PORT and/or CHAT_PORT
make restart INSTANCE=furuset
```

Also update `CHAT_SERVER_URL` in search.html if you change the chat port.

### API key not working

1. **Check key is set**:
   ```bash
   sudo grep ANTHROPIC_API_KEY /etc/inventory-system/furuset.conf
   ```

2. **Update key**:
   ```bash
   sudo nano /etc/inventory-system/furuset.conf
   # Update ANTHROPIC_API_KEY=...
   make restart-chat INSTANCE=furuset
   ```

### Permission denied errors

```bash
# Check user exists
id inventory-furuset

# Re-apply permissions
make set-permissions INSTANCE=furuset

# Or manually
sudo chgrp -R inventory-furuset /path/to/inventory
sudo chmod -R g+rX /path/to/inventory
```

## Adding New Instances

To add a new instance (e.g., "myhouse"):

```bash
# 1. Create instance
make create-instance INSTANCE=myhouse

# 2. Edit config
sudo nano /etc/inventory-system/myhouse.conf
# Set INVENTORY_PATH, WEB_PORT=8002, CHAT_PORT=8767

# 3. Set permissions
make set-permissions INSTANCE=myhouse

# 4. Start
make start INSTANCE=myhouse

# 5. Enable
make enable INSTANCE=myhouse
```

## Uninstallation

### Remove Instance
```bash
# Stop services
make stop INSTANCE=furuset

# Disable auto-start
make disable INSTANCE=furuset

# Remove config
sudo rm /etc/inventory-system/furuset.conf

# Remove user
sudo userdel inventory-furuset
```

### Remove All
```bash
# Stop all
make stop-all

# Remove templates
sudo rm /etc/systemd/system/inventory-web@.service
sudo rm /etc/systemd/system/inventory-chat@.service
sudo rm -rf /etc/inventory-system
sudo systemctl daemon-reload

# Remove users
sudo userdel inventory-furuset
sudo userdel inventory-solveig
```

## Production Tips

1. **Use systemd for process management** - auto-restart on failure
2. **Enable auto-start** - `make enable-all`
3. **Monitor logs** - `make logs INSTANCE=name`
4. **Unique ports** - avoid conflicts between instances
5. **Firewall** - restrict access if needed
6. **Backups** - backup `/etc/inventory-system/` configs
7. **Updates** - `make restart-all` after updating inventory data

## Next Steps

- See `README.md` for inventory system documentation
- See `CHANGELOG.md` for recent changes
- Phase 2 will add write operations through chat interface
