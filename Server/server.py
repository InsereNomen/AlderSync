"""
AlderSync Server - Main FastAPI Application

This module contains the main FastAPI application for the AlderSync server.
It manages REST API endpoints for file synchronization between clients and the server.
"""

import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status, Query, File as FastAPIFile, UploadFile, Form, Request, Response, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import hashlib
import shutil

from models.database import LastOperation, User, File, Operation, Setting, Role, Permission, RolePermission
from models.auth import LoginRequest, LoginResponse, ChangePasswordRequest, ChangePasswordResponse
from models.api import (
    FileMetadata,
    RestoreRevisionRequest, RestoreRevisionResponse,
    ClientFileMetadata,
    TransactionBeginRequest, TransactionBeginResponse,
    TransactionCommitResponse, TransactionRollbackResponse,
    FileUploadResponse, FileDeleteRequest, FileDeleteResponse,
    CreateUserRequest, UpdateUserStatusRequest, ResetPasswordRequest, UpdateUserRoleRequest,
    CreateRoleRequest, UpdateRoleRequest, SetRolePermissionsRequest,
    DeleteFileRequest, DeleteRevisionRequest,
    SettingsUpdateRequest
)
from managers.database_manager import DatabaseManager
from auth import CreateAccessToken, AuthenticateUser, GetCurrentActiveUser, UserHasPermission
from file_storage import InitializeStorage, ListFiles, GetFilePath, CalculateFileHash, StoreFileMetadata, GetFilePath as GetStorageFilePath, CreateRevision, GetAllRevisions, GetRevisionPath, CompareFilesForReconcile
from transactions import (
    InitializeStagingArea, AcquireLock, ReleaseLock,
    CreateTransaction, GetTransaction, CommitTransaction, RollbackTransaction,
    GetActiveLockInfo
)
from admin_sessions import (
    CreateSession, GetSession, DeleteSession, CleanupExpiredSessions,
    SESSION_COOKIE_NAME, SESSION_LIFETIME_HOURS
)
from client_downloads import (
    InitializeClientDownloads, GetClientDownloadsPath, StoreClientExecutable,
    ListClientVersions, GetCurrentClientVersion, DeleteClientVersion, SetActiveClientVersion
)

# Configure logging to write to both console and file
# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Create log filename with timestamp
log_filename = logs_dir / f"aldersync-server-{datetime.now().strftime('%Y-%m-%d')}.log"

# Configure logging with both console and file handlers
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # Console handler
        logging.StreamHandler(),
        # File handler with rotation (max 10MB per file, keep 10 backup files)
        RotatingFileHandler(
            log_filename,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10,
            encoding='utf-8'
        )
    ]
)
logger = logging.getLogger(__name__)

# Import database module for shared db_manager instance
import database


# ==================== Lifespan Events ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan event handler for startup and shutdown
    Manages database initialization and cleanup
    """
    # Startup
    logger.info("AlderSync Server starting up...")

    # Initialize database manager in database module
    database.db_manager = DatabaseManager()

    # Initialize database (creates tables if needed, but won't recreate admin if exists)
    admin_password = database.db_manager.InitializeDatabase()
    if admin_password:
        logger.warning("=" * 60)
        logger.warning("NEW ADMIN USER CREATED")
        logger.warning(f"Username: admin")
        logger.warning(f"Password: {admin_password}")
        logger.warning("SAVE THIS PASSWORD - IT WILL NOT BE SHOWN AGAIN!")
        logger.warning("=" * 60)

    logger.info("Database initialized successfully")

    # Initialize file storage
    InitializeStorage()
    logger.info("File storage initialized successfully")

    # Initialize transaction staging area
    InitializeStagingArea()
    logger.info("Transaction staging area initialized successfully")

    # Initialize client downloads folder
    InitializeClientDownloads(database.db_manager)
    logger.info("Client downloads folder initialized successfully")

    logger.info("Server startup complete")

    yield

    # Shutdown
    logger.info("AlderSync Server shutting down...")
    # Clean up resources if needed
    logger.info("Shutdown complete")


# ==================== FastAPI Application ====================

app = FastAPI(
    title="AlderSync Server",
    description="File synchronization server for ProPresenter playlists",
    version="1.0.0",
    lifespan=lifespan
)

# ==================== CORS Middleware ====================

# Allow all origins for development
# In production, this should be restricted to specific client URLs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Templates and Static Files ====================

# Get the directory where this script is located
script_dir = Path(__file__).parent

# Mount static files directory for CSS/JS assets
app.mount("/static", StaticFiles(directory=str(script_dir / "static")), name="static")

# Initialize Jinja2 templates
templates = Jinja2Templates(directory=str(script_dir / "templates"))



# ==================== Import Routers ====================

from routes import status, version, auth, files, transactions_control, transactions_files
from routes.admin import auth as admin_auth, users as admin_users, roles as admin_roles
from routes.admin import operations as admin_operations, files as admin_files
from routes.admin import settings as admin_settings, downloads as admin_downloads, docs as admin_docs


# ==================== Include Routers ====================

# Include all route modules
app.include_router(status.router)
app.include_router(version.router)
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(transactions_control.router)
app.include_router(transactions_files.router)

# Include admin route modules
app.include_router(admin_auth.router)
app.include_router(admin_users.router)
app.include_router(admin_roles.router)
app.include_router(admin_operations.router)
app.include_router(admin_files.router)
app.include_router(admin_settings.router)
app.include_router(admin_downloads.router)
app.include_router(admin_docs.router)


# ==================== Main Entry Point ====================

if __name__ == "__main__":
    """
    Run the server using uvicorn
    """
    # Initialize db_manager in database module
    import database
    from managers.database_manager import DatabaseManager
    database.db_manager = DatabaseManager()
    
    logger.info("Starting AlderSync Server...")

    # Run server with uvicorn
    # host="0.0.0.0" allows connections from other machines on the network
    # port=8000 is the default for this application
    # reload=False: Auto-reload disabled to prevent spurious log messages from
    #               file monitoring. Manually restart server after code changes.
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
