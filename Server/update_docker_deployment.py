#!/usr/bin/env python3
"""
AlderSync Server - Docker Deployment Updater

This script automates the process of building and deploying the AlderSync Server Docker image.

Usage:
    python update_docker_deployment.py [options]

Options:
    --build-only          Build the image but don't export or deploy
    --export              Export the image to a tar file for manual Portainer import
    --portainer-url URL   Portainer URL (e.g., http://nas:9000)
    --portainer-token TOKEN  Portainer API token
    --stack-name NAME     Name of the stack in Portainer (default: aldersync-server)
    --endpoint-id ID      Portainer endpoint ID (default: 1)
    --version VERSION     Version tag for the image (default: latest)

Examples:
    # Build and export for manual upload to Portainer
    python update_docker_deployment.py --export

    # Build and deploy via Portainer API
    python update_docker_deployment.py --portainer-url http://nas:9000 --portainer-token YOUR_TOKEN

    # Build with custom version tag
    python update_docker_deployment.py --export --version 1.2.0
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    requests = None


class DockerDeploymentUpdater:
    """Handles building and deploying AlderSync Server Docker images."""

    def __init__(self, version: str = "latest"):
        """
        Initialize the deployment updater.

        Args:
            version: Version tag for the Docker image
        """
        self.version = version
        self.image_name = "server-aldersync-server"
        self.image_tag = f"{self.image_name}:{version}"
        self.server_dir = Path(__file__).parent.absolute()
        self.export_filename = f"aldersync-server-image-{version}.tar"

    def log(self, message: str, level: str = "INFO"):
        """
        Print a formatted log message.

        Args:
            message: The message to log
            level: Log level (INFO, SUCCESS, WARNING, ERROR)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = {
            "INFO": "[INFO]",
            "SUCCESS": "[SUCCESS]",
            "WARNING": "[WARNING]",
            "ERROR": "[ERROR]"
        }.get(level, "[INFO]")

        print(f"{timestamp} {prefix} {message}")

    def run_command(self, command: list, capture_output: bool = False) -> Optional[str]:
        """
        Run a shell command and handle errors.

        Args:
            command: Command as a list of strings
            capture_output: If True, return output; if False, stream to console

        Returns:
            Command output if capture_output is True, None otherwise

        Raises:
            SystemExit: If command fails
        """
        self.log(f"Running: {' '.join(command)}")

        try:
            if capture_output:
                result = subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=self.server_dir
                )
                return result.stdout
            else:
                subprocess.run(command, check=True, cwd=self.server_dir)
                return None

        except subprocess.CalledProcessError as e:
            self.log(f"Command failed: {e}", "ERROR")
            if capture_output and e.stderr:
                self.log(f"Error output: {e.stderr}", "ERROR")
            sys.exit(1)

        except FileNotFoundError:
            self.log(f"Command not found: {command[0]}", "ERROR")
            self.log("Make sure Docker is installed and in your PATH", "ERROR")
            sys.exit(1)

    def check_docker(self):
        """Verify Docker is installed and running."""
        self.log("Checking Docker installation...")

        try:
            self.run_command(["docker", "--version"], capture_output=True)
            self.run_command(["docker", "info"], capture_output=True)
            self.log("Docker is available and running", "SUCCESS")
        except SystemExit:
            self.log("Docker is not available. Please install Docker and ensure it's running.", "ERROR")
            raise

    def build_image(self):
        """Build the Docker image from the Dockerfile."""
        self.log(f"Building Docker image: {self.image_tag}")
        self.log("This may take several minutes on first build...")

        # Build with both version tag and 'latest' tag
        command = [
            "docker", "build",
            "-t", self.image_tag,
            "-t", f"{self.image_name}:latest",
            "-f", "Dockerfile",
            "."
        ]

        self.run_command(command)
        self.log(f"Successfully built image: {self.image_tag}", "SUCCESS")

    def export_image(self) -> Path:
        """
        Export the Docker image to a tar file.

        Returns:
            Path to the exported tar file
        """
        export_path = self.server_dir / "portainer-deployment" / self.export_filename
        export_path.parent.mkdir(exist_ok=True)

        self.log(f"Exporting image to: {export_path}")

        command = [
            "docker", "save",
            "-o", str(export_path),
            self.image_tag
        ]

        self.run_command(command)

        # Check file size
        size_mb = export_path.stat().st_size / (1024 * 1024)
        self.log(f"Successfully exported image ({size_mb:.1f} MB): {export_path}", "SUCCESS")

        return export_path

    def update_portainer_via_api(
        self,
        portainer_url: str,
        api_token: str,
        stack_name: str,
        endpoint_id: int
    ):
        """
        Update the Portainer stack via API.

        Args:
            portainer_url: Base URL of Portainer instance
            api_token: Portainer API token
            stack_name: Name of the stack to update
            endpoint_id: Portainer endpoint ID

        Raises:
            SystemExit: If API requests fail
        """
        if requests is None:
            self.log("The 'requests' library is required for Portainer API updates", "ERROR")
            self.log("Install it with: pip install requests", "ERROR")
            sys.exit(1)

        self.log(f"Connecting to Portainer: {portainer_url}")

        headers = {
            "X-API-Key": api_token,
            "Content-Type": "application/json"
        }

        # Get stack ID
        self.log(f"Finding stack: {stack_name}")
        try:
            response = requests.get(
                f"{portainer_url}/api/stacks",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            stacks = response.json()

            stack = next((s for s in stacks if s["Name"] == stack_name), None)
            if not stack:
                self.log(f"Stack '{stack_name}' not found in Portainer", "ERROR")
                self.log("Available stacks: " + ", ".join(s["Name"] for s in stacks), "INFO")
                sys.exit(1)

            stack_id = stack["Id"]
            self.log(f"Found stack ID: {stack_id}", "SUCCESS")

        except requests.exceptions.RequestException as e:
            self.log(f"Failed to connect to Portainer: {e}", "ERROR")
            sys.exit(1)

        # Pull the updated image (if using a registry)
        # Note: For local images, this step may not be necessary
        self.log("Triggering stack update...")

        try:
            # Redeploy the stack to use the new image
            response = requests.put(
                f"{portainer_url}/api/stacks/{stack_id}",
                headers=headers,
                params={"endpointId": endpoint_id},
                json={
                    "pullImage": False,  # We built locally, not pulling from registry
                    "prune": True  # Remove old containers
                },
                timeout=30
            )
            response.raise_for_status()
            self.log("Stack update triggered successfully", "SUCCESS")

        except requests.exceptions.RequestException as e:
            self.log(f"Failed to update stack: {e}", "ERROR")
            sys.exit(1)

        self.log("Waiting for stack to restart...")
        time.sleep(5)
        self.log("Deployment update complete", "SUCCESS")

    def generate_instructions(self, export_path: Optional[Path] = None):
        """
        Generate instructions for manual deployment.

        Args:
            export_path: Path to exported tar file (if applicable)
        """
        print("\n" + "=" * 80)
        print("MANUAL DEPLOYMENT INSTRUCTIONS")
        print("=" * 80)

        if export_path:
            print(f"\n1. The Docker image has been exported to:")
            print(f"   {export_path}")
            print(f"\n2. Upload this file to your NAS server")
            print(f"\n3. In Portainer, go to: Images")
            print(f"\n4. Click 'Import' and upload: {export_path.name}")
            print(f"\n5. Tag the imported image as: {self.image_name}:latest")

        print(f"\n6. In Portainer, go to your AlderSync stack")
        print(f"\n7. Click 'Update the stack'")
        print(f"\n8. Enable 'Re-pull image and redeploy'")
        print(f"\n9. Click 'Update'")
        print(f"\n10. Wait for the stack to restart with the new image")
        print("\n" + "=" * 80 + "\n")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Build and deploy AlderSync Server Docker image",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Build the image but don't export or deploy"
    )

    parser.add_argument(
        "--export",
        action="store_true",
        help="Export the image to a tar file for manual Portainer import"
    )

    parser.add_argument(
        "--portainer-url",
        type=str,
        help="Portainer URL (e.g., http://nas:9000)"
    )

    parser.add_argument(
        "--portainer-token",
        type=str,
        help="Portainer API token"
    )

    parser.add_argument(
        "--stack-name",
        type=str,
        default="aldersync-server",
        help="Name of the stack in Portainer (default: aldersync-server)"
    )

    parser.add_argument(
        "--endpoint-id",
        type=int,
        default=1,
        help="Portainer endpoint ID (default: 1)"
    )

    parser.add_argument(
        "--version",
        type=str,
        default="latest",
        help="Version tag for the image (default: latest)"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.portainer_url and not args.portainer_token:
        parser.error("--portainer-token is required when using --portainer-url")

    if args.portainer_token and not args.portainer_url:
        parser.error("--portainer-url is required when using --portainer-token")

    # If no action specified, default to export
    if not args.build_only and not args.export and not args.portainer_url:
        args.export = True

    # Create updater instance
    updater = DockerDeploymentUpdater(version=args.version)

    try:
        # Check Docker availability
        updater.check_docker()

        # Build the image
        updater.build_image()

        export_path = None

        # Export if requested
        if args.export:
            export_path = updater.export_image()

        # Update via Portainer API if credentials provided
        if args.portainer_url and args.portainer_token:
            updater.update_portainer_via_api(
                portainer_url=args.portainer_url,
                api_token=args.portainer_token,
                stack_name=args.stack_name,
                endpoint_id=args.endpoint_id
            )

        # Generate instructions for manual deployment
        if not args.portainer_url:
            updater.generate_instructions(export_path)

        updater.log("All tasks completed successfully!", "SUCCESS")

    except KeyboardInterrupt:
        updater.log("\nOperation cancelled by user", "WARNING")
        sys.exit(1)

    except Exception as e:
        updater.log(f"Unexpected error: {e}", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
