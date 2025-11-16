# AlderSync Server - Portainer Deployment Package

This package contains everything needed to deploy AlderSync Server using Portainer.io.

## Package Contents

- `aldersync-server-image.tar` - Pre-built Docker image (68MB)
- `docker-compose.yml` - Stack configuration for Portainer
- `database/` - Directory for SQLite database (bind mount)
- `storage/Contemporary/` - Directory for Contemporary service files (bind mount)
- `storage/Traditional/` - Directory for Traditional service files (bind mount)
- `client_downloads/` - Directory for client executable distribution (bind mount)
- `logs/` - Directory for application logs (bind mount)

## Prerequisites

1. **Portainer.io** installed and running on your NAS/server
   - Portainer CE (Community Edition) or higher
   - Access to Portainer web interface

2. **System Requirements**:
   - Minimum 512MB RAM available
   - Minimum 1GB disk space (plus storage for files)
   - Network port 8000 available

## Deployment Instructions

### Step 1: Upload Package to NAS

1. Copy the entire `portainer-deployment` folder to your NAS
   - Recommended location: `/opt/aldersync` or similar persistent location
   - Ensure the directory structure is preserved

2. Set appropriate permissions:
   ```bash
   chmod -R 755 /opt/aldersync/portainer-deployment
   ```

### Step 2: Import Docker Image

1. Log in to your Portainer web interface

2. Navigate to **Images** in the sidebar

3. Click **Import** button

4. Upload the `aldersync-server-image.tar` file
   - This may take a few minutes depending on network speed

5. Once imported, verify the image appears in the list
   - Look for image named: `server-aldersync-server`
   - Tag: `latest`
   - Size: ~303MB (compressed tar is 68MB)

6. **IMPORTANT**: If the image name is different after import, you have two options:

   **Option A: Tag the image** (recommended)
   ```bash
   # SSH into your NAS and run:
   docker tag IMPORTED_IMAGE_NAME:TAG server-aldersync-server:latest
   ```

   **Option B: Edit docker-compose.yml**
   - Edit the `image:` line in docker-compose.yml to match the imported image name

### Step 3: Create Stack in Portainer

1. In Portainer, navigate to **Stacks** in the sidebar

2. Click **Add stack** button

3. Configure the stack:
   - **Name**: `aldersync` (or your preferred name)
   - **Build method**: Select **Upload**

4. Upload the `docker-compose.yml` file from this package

5. **IMPORTANT - Configure Volume Paths**:

   Before deploying, you need to update the volume paths in the compose file to match where you uploaded the package on your NAS.

   Find these lines in the editor:
   ```yaml
   volumes:
     - /volume1/Aldersync/database:/app/database
     - /volume1/Aldersync/storage/Contemporary:/app/storage/Contemporary
     - /volume1/Aldersync/storage/Traditional:/app/storage/Traditional
     - /volume1/Aldersync/client_downloads:/app/client_downloads
     - /volume1/Aldersync/logs:/app/logs
   ```

   Change the paths to match where you uploaded the package on your NAS.
   For example, if you uploaded to `/opt/aldersync/portainer-deployment`:
   ```yaml
   volumes:
     - /opt/aldersync/portainer-deployment/database:/app/database
     - /opt/aldersync/portainer-deployment/storage/Contemporary:/app/storage/Contemporary
     - /opt/aldersync/portainer-deployment/storage/Traditional:/app/storage/Traditional
     - /opt/aldersync/portainer-deployment/client_downloads:/app/client_downloads
     - /opt/aldersync/portainer-deployment/logs:/app/logs
   ```

6. **Environment Variables** (Optional):

   You can add or modify environment variables in the Portainer editor:
   - `LOG_LEVEL=DEBUG` - Enable debug logging
   - `DB_PATH=/app/aldersync.db` - Database location (default)

7. Click **Deploy the stack**

### Step 4: Verify Deployment

1. In Portainer, navigate to **Containers**

2. Find the `aldersync-server` container

3. Verify status shows **running** and health shows **healthy** (may take 30 seconds for health check)

4. Click on the container name to view details

5. Go to **Logs** tab and look for:
   ```
   Admin password: YOUR_GENERATED_PASSWORD
   ```
   **IMPORTANT**: Save this password immediately. You'll need it to log in.

6. Test the server is accessible:
   - Open browser to: `http://your-nas-ip:8000`
   - You should see the AlderSync login page

7. Verify health endpoint:
   ```bash
   curl http://your-nas-ip:8000/health
   ```
   Should return: `{"status":"healthy",...}`

### Step 5: Initial Configuration

1. Access the web interface: `http://your-nas-ip:8000`

2. Log in with:
   - **Username**: `admin`
   - **Password**: (from container logs)

3. **IMPORTANT**: Change the admin password immediately
   - Go to Settings or Profile section
   - Update password to something secure

4. Configure additional settings as needed

## File Storage Locations

After deployment, your data will be stored in:

| Data Type | Location |
|-----------|----------|
| **Database** | `/volume1/Aldersync/database/aldersync.db` (or your configured path) |
| **Contemporary Files** | `/volume1/Aldersync/storage/Contemporary` |
| **Traditional Files** | `/volume1/Aldersync/storage/Traditional` |
| **Client Downloads** | `/volume1/Aldersync/client_downloads` |
| **Log Files** | `/volume1/Aldersync/logs` |

All data is stored in bind mounts, so you can access files directly on the NAS for inspection or backup.

## Backup Procedures

### Complete Backup

All data is now in bind mounts, making backups simple:

```bash
# Create backup directory
mkdir -p /volume1/backups/aldersync

# Stop the stack in Portainer (recommended for database consistency)

# Backup all data directories
tar -czf /volume1/backups/aldersync/aldersync-backup-$(date +%Y%m%d).tar.gz \
  -C /volume1/Aldersync \
  database storage client_downloads logs

# Or copy individually
cp -r /volume1/Aldersync/database /volume1/backups/aldersync/database-$(date +%Y%m%d)
cp -r /volume1/Aldersync/storage /volume1/backups/aldersync/storage-$(date +%Y%m%d)
```

## Updating AlderSync

When a new version is released:

### Option 1: Using Automated Script (Recommended)

If you have Python installed on your development machine:

```bash
# On your development machine, navigate to Server directory
cd /path/to/AlderSync/Server

# Build and export the new image
python update_docker_deployment.py --export --version NEW_VERSION

# This creates: portainer-deployment/aldersync-server-image-NEW_VERSION.tar
```

Then follow the manual import steps below to upload the new tar file.

### Option 2: Manual Update

1. Back up your data (database and storage)

2. In Portainer, navigate to **Images**

3. Delete the old `server-aldersync-server:latest` image

4. Import the new `aldersync-server-image.tar`

5. In **Stacks**, select your AlderSync stack

6. Click **Update the stack**

7. Choose **Re-pull image and redeploy** or **Redeploy**

8. Verify the update completed successfully

Your data will persist through the update as it's stored in volumes.

## Troubleshooting

### Container Won't Start

1. Check container logs in Portainer
2. Verify port 8000 is not in use by another service
3. Check volume paths are correct in stack configuration

### Cannot Access Web Interface

1. Verify container is running and healthy in Portainer
2. Check firewall settings on NAS allow port 8000
3. Test locally on NAS: `curl http://localhost:8000/health`

### Database Locked Errors

1. Stop the stack in Portainer
2. Wait 10 seconds
3. Start the stack again

### Storage Files Not Persisting

1. Verify bind mount paths in stack configuration
2. Check directory permissions: `ls -la /opt/aldersync/portainer-deployment/storage`
3. Ensure paths exist on the host

## Port Configuration

By default, AlderSync uses port 8000. To change:

1. Edit the stack in Portainer
2. Find the `ports:` section
3. Change `"8000:8000"` to `"YOUR_PORT:8000"`
   - Example: `"9000:8000"` uses port 9000 on host
4. Update the stack

## Resource Limits

If your NAS has limited resources, you can add resource limits:

1. Edit the stack in Portainer
2. Uncomment the `deploy:` section
3. Adjust CPU and memory limits as needed
4. Update the stack

Example:
```yaml
deploy:
  resources:
    limits:
      cpus: '1.0'
      memory: 512M
```

## Security Best Practices

1. **Change admin password** immediately after first login
2. **Limit network access** using firewall rules
3. **Regular backups** of database and storage
4. **Update regularly** when new versions are released
5. Consider using **reverse proxy with SSL/TLS** for production

## API Documentation

Once running, API documentation is available at:
- Swagger UI: `http://your-nas-ip:8000/docs`
- ReDoc: `http://your-nas-ip:8000/redoc`

## Support

For issues or questions:
- Check the main DOCKER.md for detailed Docker information
- Review container logs in Portainer for error messages
- Consult the AlderSync project documentation

## Advanced: Manual Stack Creation

If you prefer to manually create the stack instead of uploading the compose file:

1. In Portainer, create a new stack
2. Choose **Web editor**
3. Copy and paste the contents of `docker-compose.yml`
4. Update volume paths to absolute paths
5. Deploy the stack

## Clean Uninstall

To completely remove AlderSync:

1. In Portainer **Stacks**, delete the AlderSync stack
2. In **Images**, delete `server-aldersync-server:latest`
3. Remove the deployment directory: `rm -rf /volume1/Aldersync`
   (This removes all data - make sure you have backups if needed!)
