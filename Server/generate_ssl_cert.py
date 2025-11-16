"""
Script to generate self-signed SSL certificates for AlderSync server.
This creates cert.pem and key.pem files for HTTPS support.
"""

import os
import subprocess
import sys
from pathlib import Path


def GenerateSSLCertificate():
    """
    Generate self-signed SSL certificate and key using OpenSSL.
    Creates cert.pem and key.pem in the Server directory.
    """
    server_dir = Path(__file__).parent
    cert_path = server_dir / "cert.pem"
    key_path = server_dir / "key.pem"

    # Check if certificates already exist
    if cert_path.exists() and key_path.exists():
        print(f"SSL certificates already exist:")
        print(f"  Certificate: {cert_path}")
        print(f"  Key: {key_path}")
        response = input("Overwrite existing certificates? (y/N): ")
        if response.lower() != 'y':
            print("Certificate generation cancelled.")
            return

    print("Generating self-signed SSL certificate...")
    print("This certificate will be valid for 10 years.")

    # OpenSSL command to generate self-signed certificate
    # -x509: Output a self-signed certificate instead of a certificate request
    # -newkey rsa:2048: Generate a new RSA key of 2048 bits
    # -nodes: Don't encrypt the private key (no DES)
    # -keyout: Where to write the private key
    # -out: Where to write the certificate
    # -days: Certificate validity period
    # -subj: Certificate subject (organization details)
    cmd = [
        "openssl", "req", "-x509",
        "-newkey", "rsa:2048",
        "-nodes",
        "-keyout", str(key_path),
        "-out", str(cert_path),
        "-days", "3650",
        "-subj", "/C=US/ST=State/L=City/O=Church/CN=aldersync-server"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("\nSSL certificates generated successfully!")
        print(f"  Certificate: {cert_path}")
        print(f"  Key: {key_path}")
        print("\nThese are self-signed certificates suitable for internal use.")
        print("Clients should disable SSL verification or add the certificate to their trust store.")
    except FileNotFoundError:
        print("ERROR: OpenSSL not found.")
        print("Please install OpenSSL:")
        print("  Windows: Download from https://slproweb.com/products/Win32OpenSSL.html")
        print("  Mac: brew install openssl")
        print("  Linux: sudo apt-get install openssl")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to generate certificate")
        print(f"Command output: {e.stderr}")
        sys.exit(1)


if __name__ == "__main__":
    GenerateSSLCertificate()
