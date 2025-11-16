# AlderSync Server Docker Deployment Guide

This guide provides complete instructions for deploying the AlderSync server using Docker and Docker Compose on a NAS or any Docker-capable system.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Portainer Deployment](#portainer-deployment)
- [Detailed Deployment Steps](#detailed-deployment-steps)
- [Configuration](#configuration)
- [Volume Mounts](#volume-mounts)
- [Backup Procedures](#backup-procedures)
- [Update Procedures](#update-procedures)
- [Troubleshooting](#troubleshooting)
- [Common Tasks](#common-tasks)

---

## Prerequisites

Before deploying AlderSync server, ensure your system has:

1. **Docker Engine** (version 20.10 or later)
   - Installation guides: https://docs.docker.com/engine/install/

2. **Docker Compose** (version 2.0 or later)
   - Included with Docker Desktop
   - For Linux servers: https://docs.docker.com/compose/install/

3. **System Requirements**:
   - Minimum 512MB RAM available for container
   - Minimum 1GB disk space (more depending on file storage needs)
   - Network port 8000 available (or configure alternative)

4. **Verify Installation**:
   ```bash
   docker --version
   docker compose version
   ```

---

## Quick Start

For experienced users who want to get started immediately:

```bash
# 1. Navigate to the Server directory
cd /path/to/AlderSync/Server

# 2. Start the service
docker compose up -d

# 3. Check service is healthy
docker compose ps

# 4. View admin password in logs
docker compose logs | grep "Admin password"

# 5. Access the server
# Web interface: http://your-server-ip:8000
# API: http://your-server-ip:8000/docs
```

The server will automatically create an admin user on first startup. Check the logs for the generated password.

---

## Portainer Deployment

For users deploying to a NAS or server that uses Portainer.io, we provide a pre-built deployment package that simplifies installation.

### What is Portainer?

Portainer is a popular web-based Docker management interface commonly used on NAS systems (Synology, QNAP, etc.) and servers. If your system has Portainer installed, this is the recommended deployment method.

### Portainer Deployment Package

The `portainer-deployment/` directory contains:
- **aldersync-server-image.tar** - Pre-built Docker image (68MB compressed)
- **docker-compose.yml** - Stack configuration optimized for Portainer
- **PORTAINER-README.md** - Complete Portainer-specific deployment instructions
- **storage/** - Pre-created directories for file storage
- **logs/** - Pre-created directory for application logs

### Quick Portainer Deployment

1. **Upload the package** to your NAS (e.g., `/opt/aldersync/portainer-deployment`)

2. **Import the image** in Portainer:
   - Navigate to **Images** → **Import**
   - Upload `aldersync-server-image.tar`
   - Wait for import to complete

3. **Create the stack** in Portainer:
   - Navigate to **Stacks** → **Add stack**
   - Upload the `docker-compose.yml` file
   - **IMPORTANT**: Update volume paths to absolute paths:
     ```yaml
     volumes:
       - /opt/aldersync/portainer-deployment/storage/Contemporary:/app/storage/Contemporary
       - /opt/aldersync/portainer-deployment/storage/Traditional:/app/storage/Traditional
       - /opt/aldersync/portainer-deployment/logs:/app/logs
     ```
   - Deploy the stack

4. **Get the admin password**:
   - Go to **Containers** → **aldersync-server** → **Logs**
   - Find the line: `Admin password: YOUR_PASSWORD`

5. **Access the server**: http://your-nas-ip:8000

### Complete Portainer Instructions

For detailed step-by-step instructions, troubleshooting, and configuration options specific to Portainer deployment, see:

**`portainer-deployment/PORTAINER-README.md`**

This file includes:
- Detailed deployment walkthrough with screenshots references
- Volume path configuration
- Backup and update procedures for Portainer
- Portainer-specific troubleshooting
- Resource limits and security considerations

---

## Detailed Deployment Steps

### Step 1: Prepare Deployment Directory

1. Copy the AlderSync Server files to your deployment location:
   ```bash
   # Example: Copy to /opt/aldersync
   sudo mkdir -p /opt/aldersync
   sudo cp -r Server/* /opt/aldersync/
   cd /opt/aldersync
   ```

2. Verify required files are present:
   ```bash
   ls -la
   # Should see: docker-compose.yml, Dockerfile, server.py, requirements.txt, etc.
   ```

### Step 2: Create Data Directories

The application requires directories for all persistent data:

```bash
# Create all data directories
mkdir -p database
mkdir -p storage/Contemporary
mkdir -p storage/Traditional
mkdir -p client_downloads
mkdir -p logs

# Set appropriate permissions (adjust user/group as needed)
chmod -R 755 database storage client_downloads logs
```

### Step 3: Review Configuration (Optional)

Before starting, you may want to customize the deployment:

1. **Edit docker-compose.yml** to change:
   - Port mapping (default: 8000)
   - Environment variables
   - Resource limits

2. **Common customizations**:
   ```yaml
   ports:
     - "9000:8000"  # Use port 9000 on host instead of 8000

   environment:
     - LOG_LEVEL=DEBUG  # Enable debug logging
   ```

### Step 4: Build and Start the Service

```bash
# Build the Docker image
docker compose build

# Start the service in detached mode
docker compose up -d
```

The build process will:
- Pull Python 3.9 base image
- Install dependencies from requirements.txt
- Copy application files
- Configure the container

### Step 5: Verify Deployment

1. **Check container status**:
   ```bash
   docker compose ps
   ```
   You should see `aldersync-server` with status `Up` and health `healthy`.

2. **View startup logs**:
   ```bash
   docker compose logs
   ```

3. **Find admin password**:
   ```bash
   docker compose logs | grep "Admin password"
   ```
   Look for a line like: `Admin password: AbCd123XyZ$`

   **IMPORTANT**: Save this password securely. You'll need it to log in.

4. **Test health endpoint**:
   ```bash
   curl http://localhost:8000/health
   ```
   Should return: `{"status":"healthy"}`

5. **Access web interface**:
   - Open browser to: `http://your-server-ip:8000`
   - Login with username: `admin` and the password from logs

### Step 6: Verify Data Persistence

Test that data survives container restarts:

```bash
# Restart the container
docker compose restart

# Check it comes back healthy
docker compose ps

# Verify you can still login with same credentials
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"YOUR_PASSWORD_HERE\"}"
```

If you receive a JWT token, persistence is working correctly.

---

## Configuration

### Environment Variables

The following environment variables can be configured in `docker-compose.yml`:

| Variable | Default | Description |
|----------|---------|-------------|
| `PYTHONUNBUFFERED` | `1` | Keep Python output unbuffered for real-time logging |
| `DB_PATH` | `/app/database/aldersync.db` | Path to SQLite database file |
| `CONTEMPORARY_PATH` | `/app/storage/Contemporary` | Storage path for Contemporary service files |
| `TRADITIONAL_PATH` | `/app/storage/Traditional` | Storage path for Traditional service files |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

**Example configuration**:
```yaml
environment:
  - PYTHONUNBUFFERED=1
  - LOG_LEVEL=DEBUG
  - DB_PATH=/app/aldersync.db
```

### Port Configuration

By default, the server uses port 8000. To change:

```yaml
ports:
  - "9000:8000"  # Host port 9000 → Container port 8000
```

**Note**: Only change the host port (first number). The container port (8000) should remain unchanged.

### Resource Limits

For systems with limited resources, uncomment and adjust the resource limits in `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '1.0'
      memory: 512M
    reservations:
      cpus: '0.5'
      memory: 256M
```

---

## Volume Mounts

The Docker setup uses bind mounts for all persistent data, making backups and management straightforward:

### Bind Mounts

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `./database` | `/app/database` | SQLite database storage |
| `./storage/Contemporary` | `/app/storage/Contemporary` | Contemporary service file storage |
| `./storage/Traditional` | `/app/storage/Traditional` | Traditional service file storage |
| `./client_downloads` | `/app/client_downloads` | Client executable distribution |
| `./logs` | `/app/logs` | Application log files |

### Why Bind Mounts?

- **Easy access**: All data is directly accessible on the host filesystem
- **Simple backups**: Just copy the directories - no Docker volume commands needed
- **Transparent management**: Inspect, backup, and restore without Docker-specific tools
- **Consistent approach**: All persistent data stored the same way

### Inspecting Data

```bash
# View all persistent data directories
ls -la database
ls -la storage/Contemporary
ls -la storage/Traditional
ls -la client_downloads
ls -la logs

# Check database file
ls -lh database/aldersync.db
```

---

## Backup Procedures

### Backup Strategy

AlderSync requires backing up three components:
1. SQLite database (user accounts, file metadata)
2. File storage (Contemporary and Traditional directories)
3. Configuration files

### Complete Backup Procedure

```bash
#!/bin/bash
# AlderSync backup script

BACKUP_DIR="/path/to/backups/aldersync-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

# 1. Stop the container (ensures database consistency)
cd /opt/aldersync
docker compose stop

# 2. Backup all data directories (all are bind mounts now)
cp -r database "$BACKUP_DIR/"
cp -r storage "$BACKUP_DIR/"
cp -r client_downloads "$BACKUP_DIR/"
cp -r logs "$BACKUP_DIR/"

# 3. Backup configuration
cp docker-compose.yml "$BACKUP_DIR/"
cp Dockerfile "$BACKUP_DIR/"

# 4. Restart the container
docker compose start

echo "Backup completed: $BACKUP_DIR"
```

### Automated Backups

To schedule daily backups using cron:

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /path/to/backup-script.sh >> /var/log/aldersync-backup.log 2>&1
```

### Restore Procedure

```bash
#!/bin/bash
# AlderSync restore script

BACKUP_DIR="/path/to/backups/aldersync-20240101-020000"
DEPLOY_DIR="/opt/aldersync"

# 1. Stop the service
cd "$DEPLOY_DIR"
docker compose down

# 2. Restore all data directories
rm -rf database storage client_downloads logs
cp -r "$BACKUP_DIR/database" .
cp -r "$BACKUP_DIR/storage" .
cp -r "$BACKUP_DIR/client_downloads" .
cp -r "$BACKUP_DIR/logs" .

# 3. Restart the service
docker compose up -d

echo "Restore completed from: $BACKUP_DIR"
```

---

## Update Procedures

### Updating AlderSync Server

When a new version of AlderSync is released:

#### Method 1: Automated Update Script (Recommended)

Use the provided Python script to automate the build and export process:

```bash
# Navigate to Server directory
cd /path/to/AlderSync/Server

# Build and export for manual Portainer upload
python update_docker_deployment.py --export

# Or build with custom version tag
python update_docker_deployment.py --export --version 1.2.0

# Or use Portainer API for automatic update
python update_docker_deployment.py \
  --portainer-url http://your-nas:9000 \
  --portainer-token YOUR_API_TOKEN \
  --stack-name aldersync-server
```

The script will:
1. Verify Docker is installed and running
2. Build the Docker image with proper tags
3. Export to tar file (if --export specified)
4. Update Portainer stack (if API credentials provided)
5. Provide manual deployment instructions

**Script Options**:
- `--export` - Export image to tar file for manual Portainer import
- `--build-only` - Build image but don't export or deploy
- `--portainer-url URL` - Portainer URL for API updates
- `--portainer-token TOKEN` - Portainer API token
- `--stack-name NAME` - Stack name (default: aldersync-server)
- `--version VERSION` - Version tag (default: latest)

#### Method 2: Manual In-Place Update

```bash
# 1. Navigate to deployment directory
cd /opt/aldersync

# 2. Backup current installation (see Backup Procedures)
./backup-script.sh

# 3. Download new version files
# (Replace old files: server.py, templates/, static/, etc.)
# DO NOT replace docker-compose.yml unless instructed

# 4. Rebuild the Docker image
docker compose build

# 5. Restart with new image
docker compose up -d

# 6. Verify health
docker compose ps
docker compose logs
```

#### Method 3: Clean Deployment

For major version updates or troubleshooting:

```bash
# 1. Backup everything
./backup-script.sh

# 2. Stop and remove containers
docker compose down

# 3. Remove old image (optional)
docker image rm aldersync-server

# 4. Update files to new version

# 5. Deploy new version
docker compose up -d
```

### Database Migrations

If an update requires database schema changes, follow migration instructions provided with the release. Generally:

```bash
# Enter the container
docker compose exec aldersync-server /bin/bash

# Run migration script (if provided)
python migrate.py

# Exit container
exit
```

### Rollback Procedure

If an update causes issues:

```bash
# 1. Stop current version
docker compose down

# 2. Restore from backup (see Restore Procedure)
./restore-script.sh

# 3. Verify service is working
docker compose ps
```

---

## Troubleshooting

### Container Won't Start

**Symptom**: `docker compose up` fails or container exits immediately

**Solutions**:
1. Check logs for errors:
   ```bash
   docker compose logs
   ```

2. Verify port 8000 is not in use:
   ```bash
   # Linux/Mac
   sudo lsof -i :8000

   # Windows
   netstat -ano | findstr :8000
   ```

3. Check file permissions on storage directories:
   ```bash
   ls -la storage logs
   chmod -R 755 storage logs
   ```

4. Verify Docker has enough resources:
   ```bash
   docker info
   ```

### Container Shows "Unhealthy"

**Symptom**: `docker compose ps` shows health status as "unhealthy"

**Solutions**:
1. Check application logs:
   ```bash
   docker compose logs --tail=50
   ```

2. Test health endpoint manually:
   ```bash
   docker compose exec aldersync-server curl http://localhost:8000/health
   ```

3. Restart the container:
   ```bash
   docker compose restart
   ```

4. If persistent, rebuild:
   ```bash
   docker compose down
   docker compose build --no-cache
   docker compose up -d
   ```

### Cannot Access Web Interface

**Symptom**: Browser cannot connect to http://server-ip:8000

**Solutions**:
1. Verify container is running and healthy:
   ```bash
   docker compose ps
   ```

2. Check firewall settings:
   ```bash
   # Linux (ufw)
   sudo ufw allow 8000/tcp

   # Linux (firewalld)
   sudo firewall-cmd --add-port=8000/tcp --permanent
   sudo firewall-cmd --reload
   ```

3. Test from server itself:
   ```bash
   curl http://localhost:8000/health
   ```

4. Check Docker port mapping:
   ```bash
   docker compose port aldersync-server 8000
   ```

### Database Locked Errors

**Symptom**: Logs show "database is locked" errors

**Solutions**:
1. Check if multiple processes are accessing database:
   ```bash
   docker compose exec aldersync-server ps aux
   ```

2. Restart container (releases locks):
   ```bash
   docker compose restart
   ```

3. If persistent, stop container and check database:
   ```bash
   docker compose stop
   ls -la database/
   ```

### Storage Files Not Persisting

**Symptom**: Uploaded files disappear after container restart

**Solutions**:
1. Verify storage directories exist:
   ```bash
   ls -la storage/Contemporary storage/Traditional
   ```

2. Check bind mount is working:
   ```bash
   docker compose exec aldersync-server ls -la /app/storage/Contemporary
   ```

3. Verify files appear in host directory:
   ```bash
   ls -la storage/Contemporary
   ```

4. Check volume mounts in docker-compose.yml are correct

### Permission Denied Errors

**Symptom**: Container cannot write to storage or logs

**Solutions**:
1. Fix directory permissions:
   ```bash
   chmod -R 755 storage logs
   ```

2. If using SELinux (RHEL/CentOS):
   ```bash
   sudo chcon -Rt svirt_sandbox_file_t storage logs
   ```

3. Grant Docker access:
   ```bash
   sudo chown -R $(id -u):$(id -g) storage logs
   ```

---

## Common Tasks

### View Live Logs

```bash
# All logs
docker compose logs -f

# Last 50 lines
docker compose logs --tail=50

# Follow new logs only
docker compose logs -f --tail=0
```

### Access Container Shell

```bash
# Enter running container
docker compose exec aldersync-server /bin/bash

# Run single command
docker compose exec aldersync-server ls -la /app
```

### Reset Admin Password

```bash
# 1. Stop container
docker compose stop

# 2. Remove database (will recreate on startup)
rm database/aldersync.db

# 3. Start container (creates new admin user)
docker compose start

# 4. Get new password from logs
docker compose logs | grep "Admin password"
```

### Check Database Size

```bash
docker compose exec aldersync-server ls -lh /app/aldersync.db
```

### Check Storage Usage

```bash
# Contemporary service
du -sh storage/Contemporary

# Traditional service
du -sh storage/Traditional

# Total
du -sh storage
```

### Export Database (for inspection)

```bash
# Database is already accessible on host via bind mount
# View with SQLite browser or CLI
sqlite3 database/aldersync.db ".tables"

# Or copy to another location
cp database/aldersync.db ./aldersync-backup.db
```

### Clean Up Old Docker Resources

```bash
# Remove stopped containers
docker compose down

# Remove unused images
docker image prune

# All data is in bind mounts, so no volumes to clean
# To remove data, manually delete the directories:
# rm -rf database storage client_downloads logs
```

### Manually Start/Stop Service

```bash
# Stop service
docker compose stop

# Start service
docker compose start

# Restart service
docker compose restart

# Stop and remove containers
docker compose down

# Start fresh containers
docker compose up -d
```

### View API Documentation

Once the server is running:
- Swagger UI: http://your-server-ip:8000/docs
- ReDoc: http://your-server-ip:8000/redoc

### Test API Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Login (get JWT token)
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"YOUR_PASSWORD\"}"

# List Contemporary files (requires token)
curl http://localhost:8000/files/Contemporary \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Security Considerations

1. **Change Admin Password**: After first login, change the auto-generated admin password through the web interface

2. **Use HTTPS**: For production deployments, place AlderSync behind a reverse proxy (nginx, Traefik) with SSL/TLS

3. **Firewall**: Restrict access to port 8000 to known client IPs:
   ```bash
   # Example using ufw
   sudo ufw deny 8000/tcp
   sudo ufw allow from 192.168.1.0/24 to any port 8000
   ```

4. **Regular Backups**: Implement automated backup procedures (see Backup Procedures section)

5. **Update Regularly**: Keep AlderSync and Docker updated to latest versions

6. **Volume Security**: Protect Docker volumes and bind mounts with appropriate file system permissions

---

## Getting Help

If you encounter issues not covered in this guide:

1. Check AlderSync logs for detailed error messages
2. Consult the project repository for known issues
3. Verify your Docker installation is up-to-date
4. Review Docker documentation for container-specific issues

For AlderSync-specific questions, refer to the main project documentation.
