# Installation & Setup Guide

This guide shows how to set up the inventory system with systemd services for easy management.

## Prerequisites

1. **Install the package:**
   ```bash
   pip install -e /home/tobias/inventory-system
   ```

2. **Install chat dependencies:**
   ```bash
   pip install fastapi uvicorn anthropic
   ```

3. **Get your Claude API key:**
   - Visit https://console.anthropic.com/
   - Create an API key
   - Copy it for the next step

## Quick Setup

### 1. Set your API key:
```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

### 2. Install systemd services:
```bash
cd /home/tobias/inventory-system
make install-services
```

This will (requires sudo):
- Create dedicated `inventory` user (system user, no shell access)
- Set permissions on inventory directory
- Install service files to `/etc/systemd/system/`
- Set your API key in the chat service
- Reload systemd
- Services will run as user 'inventory' with read-only access

### 3. Start the services:
```bash
make start
```

### 4. Access your inventory:
Open http://localhost:8000/search.html in your browser

## Makefile Commands

### Service Management
```bash
make start          # Start both web and chat servers
make stop           # Stop both servers
make restart        # Restart both servers
make status         # Show status of both servers
make enable         # Enable auto-start on boot
make disable        # Disable auto-start
```

### Individual Services
```bash
make start-chat     # Start chat server only
make start-web      # Start web server only
make stop-chat      # Stop chat server only
make stop-web       # Stop web server only
make restart-chat   # Restart chat server only
make restart-web    # Restart web server only
```

### Logs
```bash
make logs           # Show logs for both servers (follow mode)
make logs-chat      # Show chat server logs only
make logs-web       # Show web server logs only
```

### Updating API Key
```bash
make set-api-key API_KEY=your-new-key-here
make restart-chat   # Restart to apply changes
```

## Manual Setup (without Makefile)

If you prefer to set up manually:

### 1. Create inventory user:
```bash
sudo useradd -r -s /usr/bin/nologin -d /nonexistent inventory
```

### 2. Set permissions:
```bash
sudo chgrp -R inventory /home/tobias/furusetalle9/inventory
sudo chmod -R g+rX /home/tobias/furusetalle9/inventory
```

### 3. Copy service files:
```bash
sudo cp systemd/inventory-web.service /etc/systemd/system/
sudo cp systemd/inventory-chat.service /etc/systemd/system/
```

### 4. Edit chat service to add your API key:
```bash
sudo nano /etc/systemd/system/inventory-chat.service
# Change: Environment="ANTHROPIC_API_KEY="
# To:     Environment="ANTHROPIC_API_KEY=your-key-here"
```

### 5. Reload systemd:
```bash
sudo systemctl daemon-reload
```

### 6. Start services:
```bash
sudo systemctl start inventory-web.service
sudo systemctl start inventory-chat.service
```

### 7. Enable auto-start (optional):
```bash
sudo systemctl enable inventory-web.service
sudo systemctl enable inventory-chat.service
```

## Verifying Installation

### Check service status:
```bash
sudo systemctl status inventory-web.service
sudo systemctl status inventory-chat.service
```

### Check if servers are running:
```bash
# Web server
curl http://localhost:8000/search.html

# Chat server health check
curl http://localhost:8765/health
```

### View logs:
```bash
journalctl --user -u inventory-chat.service -n 50
journalctl --user -u inventory-web.service -n 50
```

## Troubleshooting

### Chat service fails to start
1. **Check API key is set:**
   ```bash
   sudo systemctl cat inventory-chat.service | grep ANTHROPIC_API_KEY
   ```

2. **Check logs:**
   ```bash
   sudo journalctl -u inventory-chat.service -n 50
   ```

3. **Check permissions:**
   ```bash
   sudo -u inventory ls -la /home/tobias/furusetalle9/inventory/inventory.json
   ```

3. **Verify inventory.json exists:**
   ```bash
   ls -lh ~/furusetalle9/inventory/inventory.json
   ```

### Port already in use
If ports 8000 or 8765 are already in use, edit the service files:

```bash
sudo nano /etc/systemd/system/inventory-web.service
# Change: ExecStart=/usr/bin/inventory-system serve
# To:     ExecStart=/usr/bin/inventory-system serve --port 8080

sudo nano /etc/systemd/system/inventory-chat.service
# Change: ExecStart=/usr/bin/inventory-system chat
# To:     ExecStart=/usr/bin/inventory-system chat --port 8866

sudo systemctl daemon-reload
sudo systemctl restart inventory-web.service inventory-chat.service
```

Also update the chat server URL in search.html:
```javascript
const CHAT_SERVER_URL = 'http://localhost:8866';
```

## Uninstallation

### Stop and disable services:
```bash
make stop
make disable
```

### Remove service files:
```bash
sudo rm /etc/systemd/system/inventory-web.service
sudo rm /etc/systemd/system/inventory-chat.service
sudo systemctl daemon-reload
```

### Remove inventory user (optional):
```bash
sudo userdel inventory
```

## Usage

Once installed and running:

1. **Access web interface:**
   - Open http://localhost:8000/search.html

2. **Use the chat:**
   - Click the green chat button (💬) in bottom-right corner
   - Ask questions about your inventory
   - Examples:
     - "What's in box A78?"
     - "Where are my winter clothes?"
     - "Show me all boxes with skiing equipment"

3. **Update inventory:**
   ```bash
   cd ~/furusetalle9/inventory
   # Edit inventory.md
   inventory-system parse inventory.md
   make restart  # Reload with new data
   ```

## Next Steps

- See `README.md` for inventory system documentation
- See `CHANGELOG.md` for recent changes
- Phase 2 will add write operations (update inventory through chat)
