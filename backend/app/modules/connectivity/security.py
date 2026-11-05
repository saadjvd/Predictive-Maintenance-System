import os
import hashlib
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from app.modules.connectivity.models import UntrustedCertificateError


def compute_cert_fingerprint(cert_der: bytes) -> str:
    """Compute standard SHA-256 fingerprint in uppercase colon-delimited format."""
    sha256 = hashlib.sha256(cert_der).hexdigest().upper()
    return ":".join(sha256[i:i + 2] for i in range(0, len(sha256), 2))


class CertificateValidator:
    """Validates OPC UA server X.509 certificates against a strict trust list.
    
    Adheres strictly to Requirement 6: Do not automatically trust unknown certificates.
    """

    def __init__(
        self,
        trusted_fingerprints: Optional[List[str]] = None,
        trusted_certs_dir: Optional[str] = None,
        auto_trust_unknown: bool = False
    ):
        self.trusted_fingerprints = set(
            fp.strip().upper() for fp in (trusted_fingerprints or [])
        )
        self.trusted_certs_dir = trusted_certs_dir
        self.auto_trust_unknown = auto_trust_unknown
        self._load_trusted_directory()

    def _load_trusted_directory(self) -> None:
        """Load trusted certificates from the designated directory if present."""
        if not self.trusted_certs_dir or not os.path.isdir(self.trusted_certs_dir):
            return

        for filename in os.listdir(self.trusted_certs_dir):
            if filename.endswith((".der", ".cer", ".crt", ".pem")):
                filepath = os.path.join(self.trusted_certs_dir, filename)
                try:
                    with open(filepath, "rb") as f:
                        data = f.read()
                        if b"BEGIN CERTIFICATE" in data:
                            cert = x509.load_pem_x509_certificate(data)
                            fp = compute_cert_fingerprint(cert.public_bytes(serialization.Encoding.DER))
                        else:
                            fp = compute_cert_fingerprint(data)
                        self.trusted_fingerprints.add(fp)
                except Exception:
                    continue

    def validate_certificate(self, cert_der: bytes) -> bool:
        """Validate an incoming server certificate.
        
        Raises UntrustedCertificateError if unknown and not explicitly trusted.
        """
        if not cert_der:
            raise UntrustedCertificateError("No server certificate was presented for validation.")

        fingerprint = compute_cert_fingerprint(cert_der)

        if fingerprint in self.trusted_fingerprints:
            return True

        if self.auto_trust_unknown:
            # Explicitly flagged, auto-trust (testing only)
            self.trusted_fingerprints.add(fingerprint)
            return True

        raise UntrustedCertificateError(
            f"Server certificate with SHA-256 fingerprint {fingerprint} is not in the trusted certificate store. "
            f"Connection rejected to prevent man-in-the-middle attacks."
        )


def generate_self_signed_cert(
    output_dir: str,
    common_name: str = "PharmaPredict-OPCUA-Client",
    validity_days: int = 365
) -> tuple[str, str]:
    """Generate a self-signed X.509 certificate and RSA private key for testing and secure authentication.
    
    Returns (cert_path, key_path).
    """
    os.makedirs(output_dir, exist_ok=True)
    key_path = os.path.join(output_dir, f"{common_name}-key.pem")
    cert_path = os.path.join(output_dir, f"{common_name}-cert.pem")

    # Generate RSA private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "PK"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PharmaPredict AI"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=validity_days))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost"), x509.UniformResourceIdentifier(f"urn:{common_name}")]),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )

    with open(key_path, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    return cert_path, key_path

