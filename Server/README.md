# AlderSync Server - Deployment Guide

This guide will help you deploy the AlderSync server on your NAS or server.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [Initial Setup](#initial-setup)
4. [Configuration](#configuration)
5. [Auto-Start Setup](#auto-start-setup)
6. [SSL Certificate Setup](#ssl-certificate-setup)
7. [Network Configuration](#network-configuration)
8. [Updating the Server](#updating-the-server)
9. [Troubleshooting](#troubleshooting)

---

## System Requirements

- **Operating System**: Linux, macOS, or Windows
- **Python**: 3.8 or higher
- **Network**: Static IP or DDNS recommended
- **Disk Space**: At least 1GB free (more depending on file storage needs)
- **Memory**: Minimum 512MB RAM

---

## Installation

### 1. Install Python

Ensure Python 3.8+ is installed:

```bash
python3 --version
```

If not installed, download from [python.org](https://www.python.org/downloads/).

### 2. Download AlderSync Server

Copy the AlderSync Server files to your desired installation directory:

```bash
# Example installation directory
sudo mkdir -p /opt/aldersync
sudo chown $USER:$USER /opt/aldersync
cd /opt/aldersync

# Copy server files here (or git clone if using version control)
```

### 3. Create Virtual Environment

Create a Python virtual environment to isolate dependencies:

```bash
cd /opt/aldersync
python3 -m venv venv
```

### 4. Activate Virtual Environment

**Linux/Mac:**
```bash
source venv/bin/activate
```

**Windows:**
```cmd
venv\Scripts\activate
```

### 5. Install Dependencies

Install required Python packages:

```bash
pip install -r requirements.txt
```

---

## Initial Setup

### Run the Setup Script

The setup script will:
- Initialize the SQLite database
- Create the admin user
- Set up storage directories
- Configure default settings

```bash
# Make sure virtual environment is activated
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Run setup
python setup_server.py
```

**IMPORTANT**: Save the admin password displayed during setup. It will only be shown once!

Example output:
```
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!                                                                    !
!  IMPORTANT: SAVE THESE CREDENTIALS - PASSWORD SHOWN ONLY ONCE!  !
!                                                                    !
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

  Admin Username: admin
  Admin Password: Xy7$mK9pL3qN

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
```

### Verify Setup

After setup completes, you should see:
- `aldersync.db` - SQLite database file
- `storage/Contemporary/` - Storage for Contemporary service files
- `storage/Traditional/` - Storage for Traditional service files

---

## Configuration

### Server Configuration

The server uses environment variables or command-line arguments for configuration:

**Port Configuration:**
```bash
# Default port is 8000
# To use a different port:
uvicorn server:app --host 0.0.0.0 --port 8080
```

**Database Location:**
The database file (`aldersync.db`) is created in the server's working directory by default.

**Storage Location:**
File storage is in the `storage/` directory by default. This can be configured in `file_storage.py` if needed.

### Application Settings

Server settings are stored in the database and can be modified via the admin web interface:

- `lock_timeout_seconds` - Transaction timeout (default: 300 seconds)
- `min_lock_timeout_seconds` - Minimum Reconcile timeout (default: 300 seconds)
- `max_revisions` - Number of file revisions to keep (default: 10)
- `jwt_expiration_hours` - JWT token expiration time (default: 24 hours)
- `log_retention_days` - Log file retention period (default: 30 days)

---

## Auto-Start Setup

Configure the server to start automatically on boot.

### Linux (systemd)

1. **Edit the service file** to match your installation paths:

   ```bash
   sudo nano /etc/systemd/system/aldersync.service
   ```

   Copy the contents from `aldersync.service` and update these lines:
   ```ini
   User=your_username
   Group=your_group
   WorkingDirectory=/opt/aldersync
   ExecStart=/opt/aldersync/venv/bin/python /opt/aldersync/server.py
   ```

2. **Create a system user** (optional but recommended):

   ```bash
   sudo useradd -r -s /bin/false aldersync
   sudo chown -R aldersync:aldersync /opt/aldersync
   ```

3. **Enable and start the service**:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable aldersync
   sudo systemctl start aldersync
   ```

4. **Check status**:

   ```bash
   sudo systemctl status aldersync
   ```

5. **View logs**:

   ```bash
   sudo journalctl -u aldersync -f
   ```

### macOS (launchd)

1. **Edit the plist file** to match your installation paths:

   ```bash
   nano ~/Library/LaunchAgents/com.aldersync.server.plist
   ```

   Copy contents from `com.aldersync.server.plist` and update these paths:
   ```xml
   <string>/usr/local/aldersync/venv/bin/python</string>
   <string>/usr/local/aldersync/server.py</string>
   <string>/usr/local/aldersync</string>
   ```

2. **Create logs directory**:

   ```bash
   mkdir -p /usr/local/aldersync/logs
   ```

3. **Load the service**:

   ```bash
   launchctl load ~/Library/LaunchAgents/com.aldersync.server.plist
   ```

4. **Check status**:

   ```bash
   launchctl list | grep aldersync
   ```

5. **View logs**:

   ```bash
   tail -f /usr/local/aldersync/logs/aldersync-stdout.log
   tail -f /usr/local/aldersync/logs/aldersync-stderr.log
   ```

### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create a new task with these settings:
   - **Trigger**: At system startup
   - **Action**: Start a program
   - **Program**: `C:\aldersync\venv\Scripts\python.exe`
   - **Arguments**: `C:\aldersync\server.py`
   - **Start in**: `C:\aldersync`

---

## SSL Certificate Setup

**IMPORTANT**: Always use HTTPS in production when accessing over the internet!

### Option 1: Self-Signed Certificate (Home/Church Use)

Generate a self-signed certificate:

```bash
cd /opt/aldersync
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

Start server with SSL:

```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --ssl-keyfile key.pem --ssl-certfile cert.pem
```

**Note**: Clients will need to disable SSL verification or accept the certificate manually.

### Option 2: Let's Encrypt (If You Have a Domain)

If you have a domain name pointing to your server:

1. Install certbot:
   ```bash
   sudo apt-get install certbot  # Debian/Ubuntu
   ```

2. Obtain certificate:
   ```bash
   sudo certbot certonly --standalone -d your-domain.com
   ```

3. Start server with Let's Encrypt certificate:
   ```bash
   uvicorn server:app --host 0.0.0.0 --port 8000 \
     --ssl-keyfile /etc/letsencrypt/live/your-domain.com/privkey.pem \
     --ssl-certfile /etc/letsencrypt/live/your-domain.com/fullchain.pem
   ```

### Option 3: No SSL (Local Network Only)

If only accessing on local network:

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

**Warning**: Do NOT expose this to the internet without SSL!

---

## Network Configuration

### Firewall Rules

Allow inbound connections on your server port (default 8000):

**Linux (ufw):**
```bash
sudo ufw allow 8000/tcp
```

**Linux (firewalld):**
```bash
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

### Port Forwarding (For Remote Access)

Configure your router to forward external traffic to your server:

1. Log in to your router's admin interface
2. Find Port Forwarding settings
3. Create a new rule:
   - **External Port**: 8000 (or your preferred external port)
   - **Internal IP**: Your server's local IP (e.g., 192.168.1.100)
   - **Internal Port**: 8000 (your server port)
   - **Protocol**: TCP

### Static IP or DDNS

For reliable remote access:

**Option A - Static IP:**
- Request a static IP from your ISP, or
- Configure a static local IP on your server

**Option B - Dynamic DNS:**
- Use a DDNS service (e.g., No-IP, DuckDNS, Dynu)
- Configure your router to update DDNS automatically
- Clients connect using your DDNS hostname

---

## Updating the Server

### Update Python Dependencies

```bash
cd /opt/aldersync
source venv/bin/activate
pip install -r requirements.txt --upgrade
```

### Update Server Code

1. Backup your database and configuration:
   ```bash
   cp aldersync.db aldersync.db.backup
   ```

2. Update server files (git pull, or manually copy new files)

3. Restart the server:
   ```bash
   # systemd
   sudo systemctl restart aldersync

   # launchd
   launchctl unload ~/Library/LaunchAgents/com.aldersync.server.plist
   launchctl load ~/Library/LaunchAgents/com.aldersync.server.plist
   ```

---

## Troubleshooting

### Server Won't Start

1. **Check Python version**:
   ```bash
   python3 --version  # Should be 3.8+
   ```

2. **Check dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Check database permissions**:
   ```bash
   ls -la aldersync.db
   # Should be readable/writable by server user
   ```

4. **Check port availability**:
   ```bash
   # Linux
   sudo netstat -tuln | grep 8000

   # Mac
   lsof -i :8000
   ```

5. **View error logs**:
   ```bash
   # systemd
   sudo journalctl -u aldersync -n 50

   # launchd
   tail -n 50 /usr/local/aldersync/logs/aldersync-stderr.log
   ```

### Cannot Connect to Server

1. **Check server is running**:
   ```bash
   # systemd
   sudo systemctl status aldersync

   # launchd
   launchctl list | grep aldersync

   # Or check processes
   ps aux | grep server.py
   ```

2. **Test local connection**:
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status":"healthy"}
   ```

3. **Check firewall**:
   ```bash
   # Linux
   sudo ufw status
   sudo iptables -L

   # Ensure port 8000 is allowed
   ```

4. **Check port forwarding** (if accessing remotely):
   - Verify router port forwarding rules
   - Test from external network
   - Check if ISP blocks the port

### Database Locked Errors

If you get "database is locked" errors:

1. **Check for hung processes**:
   ```bash
   ps aux | grep server.py
   # Kill any duplicate/hung processes
   ```

2. **Increase timeout** (edit `database.py`):
   ```python
   self.engine = create_engine(
       f"sqlite:///{db_path}",
       echo=False,
       connect_args={'timeout': 30}  # Increase from default 5
   )
   ```

### Permission Errors

If you get permission denied errors:

```bash
# Fix ownership
sudo chown -R aldersync:aldersync /opt/aldersync

# Fix permissions
chmod 755 /opt/aldersync
chmod 644 /opt/aldersync/*.py
chmod 755 /opt/aldersync/setup_server.py
chmod 600 /opt/aldersync/aldersync.db  # Database should be private
```

### Admin Web Interface Not Loading

1. **Check server is running** (see above)

2. **Access the correct URL**:
   ```
   http://your-server-ip:8000/admin
   ```

3. **Check browser console** for JavaScript errors

4. **Clear browser cache** and try again

### Client Cannot Authenticate

1. **Verify credentials** - Try logging in via admin web interface

2. **Check user is active**:
   - Log in to admin interface
   - Go to User Management
   - Ensure user's status is "Active"

3. **Check JWT expiration** - May need to update token expiration in settings

---

## Getting Help

For additional support:

1. Check the main project documentation
2. Review the Specification.md for technical details
3. Check server logs for error messages
4. Ensure you're running the latest version

---

## Security Best Practices

1. **Change the default admin password** immediately after setup
2. **Use HTTPS** when accessing over the internet
3. **Keep Python and dependencies updated**
4. **Use a firewall** to restrict access to only necessary ports
5. **Regular backups** of the database:
   ```bash
   cp aldersync.db backups/aldersync-$(date +%Y%m%d).db
   ```
6. **Limit user accounts** - Only create accounts for authorized volunteers
7. **Monitor logs** regularly for suspicious activity
8. **Use strong passwords** for all user accounts

---

## File Locations Reference

- **Database**: `aldersync.db` (in server working directory)
- **Storage**: `storage/Contemporary/` and `storage/Traditional/`
- **Logs**: System logs (journalctl/launchd) or custom log location
- **Config**: Settings stored in database
- **Service Files**:
  - Linux: `/etc/systemd/system/aldersync.service`
  - macOS: `~/Library/LaunchAgents/com.aldersync.server.plist`

---

**End of Deployment Guide**
