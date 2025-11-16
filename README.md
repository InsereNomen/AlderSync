# AlderSync

A robust Client-Server file synchronization system designed specifically for church volunteers working with ProPresenter playlists and presentations. AlderSync simplifies the workflow of syncing files between home computers and a central server, with intelligent handling of Contemporary and Traditional service types.

## Features

### Client Features
- **GUI and CLI Modes**: Full-featured GUI for interactive use, plus headless CLI mode for automation
- **Pull, Push, and Reconcile**: Comprehensive sync operations with conflict resolution
- **Service Type Management**: Seamless folder swapping between Contemporary and Traditional services
- **Secure Credentials**: OS-native credential storage (Windows Credential Manager, macOS Keychain)
- **Transaction Safety**: All operations support cancellation and rollback
- **Revision Viewer**: Browse and restore previous file versions on-demand

### Server Features
- **FastAPI-based REST API**: Modern, high-performance async API
- **File Versioning**: Automatic revision tracking with configurable retention
- **User Management**: Multi-user support with role-based access control (RBAC)
- **Admin Interface**: Web-based administration for settings, users, and file management
- **Docker Deployment**: Fully containerized with Portainer support for NAS deployment
- **Health Monitoring**: Built-in health checks and logging

## Architecture

### Client
- **Technology**: Python with Tkinter GUI
- **Platform Support**: Windows, macOS, Linux
- **Authentication**: Secure credential storage via OS keychains
- **ProPresenter Integration**: Automatic folder detection and service type swapping

### Server
- **Technology**: FastAPI + SQLite
- **Authentication**: JWT tokens with bcrypt password hashing
- **Storage**: File-based with metadata tracking in SQLite
- **Deployment**: Native Python or Docker with Portainer

## Quick Start

### For End Users

#### Windows
1. Download `aldersync.exe` from your church's server
2. Run the executable
3. Enter server connection details and credentials
4. Start syncing!

#### macOS
1. Download `AlderSync.app` from your church's server
2. Right-click and select "Open" (first run only)
3. Enter server connection details and credentials
4. Start syncing!

See [Client/README_CLIENT.md](Client/README_CLIENT.md) for detailed user instructions.

### For Administrators

#### Server Setup

**Docker Deployment (Recommended for NAS)**:
See [Server/DOCKER.md](Server/DOCKER.md) and [Server/portainer-deployment/PORTAINER-README.md](Server/portainer-deployment/PORTAINER-README.md)

**Native Python Deployment**:
```bash
cd Server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python setup_server.py
python server.py
```

Access admin interface at `http://your-server:8000/admin`

## Project Structure

```
AlderSync/
├── Client/                  # Client application
│   ├── client.py            # Main entry point
│   ├── aldersync.spec       # PyInstaller build configuration
│   ├── README_CLIENT.md     # User documentation
│   └── requirements.txt
├── Server/                  # Server application
│   ├── server.py            # FastAPI application
│   ├── managers/            # Database and file management
│   ├── models/              # SQLAlchemy models
│   ├── routes/              # API endpoints
│   ├── templates/           # Jinja2 templates for web UI
│   ├── static/              # CSS, JavaScript, images
│   ├── portainer-deployment/ # Portainer deployment package
│   ├── DOCKER.md            # Docker documentation
│   └── requirements.txt
├── .github/workflows/       # GitHub Actions for automated builds
└── CLAUDE.md                # Development guidelines
```

## Development

### Building the Client

**Automated (GitHub Actions)**:
- Builds automatically run on push to master/main
- Download artifacts from Actions tab
- Supports both Windows and macOS builds

**Manual Build**:

Windows:
```bash
cd Client
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
pyinstaller aldersync.spec
# Output: dist/aldersync.exe
```

macOS:
```bash
cd Client
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller
pyinstaller aldersync.spec
# Output: dist/AlderSync.app
```

### Running the Server (Development)

```bash
cd Server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python server.py
```

Server will run at `http://localhost:8000`

### Code Standards

- Follow naming conventions in [CLAUDE.md](CLAUDE.md)
- One class per file
- Files should not exceed 500 lines
- Comprehensive docstrings for all major functions
- Cross-platform compatibility (Windows, macOS, Linux)
- ASCII-only (no Unicode characters)

## Documentation

- **[CLAUDE.md](CLAUDE.md)** - Development guidelines and architecture
- **[Client/README_CLIENT.md](Client/README_CLIENT.md)** - End-user client documentation
- **[Server/DOCKER.md](Server/DOCKER.md)** - Docker deployment guide
- **[Server/portainer-deployment/PORTAINER-README.md](Server/portainer-deployment/PORTAINER-README.md)** - Portainer deployment instructions

## Key Concepts

### Service Type Swapping
AlderSync manages ProPresenter folders by renaming them to switch between services:

**Switching from Contemporary to Traditional**:
```
ProPresenter → ProPresenter - Contemporary
ProPresenter - Traditional → ProPresenter
```

This allows ProPresenter to always see the active service in its default folder location.

### File Versioning
When files are updated:
- Old versions are renamed with revision numbers: `file.ext` → `file.0.ext`
- Configurable retention policy (keep N revisions)
- Higher revision numbers = newer versions
- Revision 0 = initial upload

### Reconcile Conflict Resolution
When the same file is modified on both client and server:
- **Newest file wins** (based on modification timestamp)
- No manual conflict dialogs
- Automatic, predictable behavior

## Security

- Passwords never stored in plain text
- Bcrypt hashing for server-side credentials
- OS credential stores for client-side storage
- JWT tokens for API authentication
- HTTPS support for production deployments

## System Requirements

### Client
- Windows 10/11 or macOS 10.14+
- 500MB free disk space
- Internet connection to server
- (Optional) ProPresenter 7+ for service folder swapping

### Server
- Python 3.9+ (native deployment)
- Docker + Docker Compose (containerized deployment)
- 512MB RAM minimum
- 1GB+ disk space (plus storage for files)

## License

Copyright (c) 2025 AlderSync Project

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

**AlderSync** - Simplifying ProPresenter file synchronization for church volunteers.
