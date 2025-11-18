"""
Script to generate self-signed SSL certificates for AlderSync server.
This creates cert.pem and key.pem files for HTTPS support.
Uses Python's cryptography library, no external OpenSSL binary required.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization


def GenerateSSLCertificate():
    """
    Generate self-signed SSL certificate and key using cryptography library.
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

    try:
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Certificate subject and issuer (same for self-signed)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"State"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, u"City"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Church"),
            x509.NameAttribute(NameOID.COMMON_NAME, u"aldersync-server"),
        ])

        # Build the certificate
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.now(timezone.utc)
        ).not_valid_after(
            datetime.now(timezone.utc) + timedelta(days=3650)  # 10 years
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(u"localhost"),
                x509.DNSName(u"aldersync-server"),
            ]),
            critical=False,
        ).sign(private_key, hashes.SHA256())

        # Write private key to file
        with open(key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))

        # Write certificate to file
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        print("\nSSL certificates generated successfully!")
        print(f"  Certificate: {cert_path}")
        print(f"  Key: {key_path}")
        print("\nThese are self-signed certificates suitable for internal use.")
        print("Clients should disable SSL verification or add the certificate to their trust store.")

    except Exception as e:
        print(f"ERROR: Failed to generate certificate: {e}")
        sys.exit(1)


if __name__ == "__main__":
    GenerateSSLCertificate()
