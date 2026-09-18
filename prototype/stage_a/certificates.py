"""Ephemeral local CA fixtures. Private keys never leave the temporary directory."""
from pathlib import Path
import subprocess

OPENSSL = '/usr/local/bin/openssl'


def generate(directory, kind='valid'):
    """Return server key, server certificate, trust CA for one negative/positive case."""
    if kind not in {'valid', 'wronghost', 'expired', 'untrusted'}:
        raise ValueError(kind)
    d = Path(directory) / kind
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    def run(*args):
        subprocess.run([OPENSSL, *args], cwd=d, check=True, timeout=10,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                       env={'PATH': '/usr/bin:/bin', 'HOME': str(d)})
    run('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'ca.key',
        '-out', 'ca.pem', '-days', '2', '-subj', '/CN=Stage A ephemeral CA',
        '-addext', 'basicConstraints=critical,CA:TRUE',
        '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
    run('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'server.key',
        '-out', 'server.csr', '-subj', '/CN=localhost')
    (d/'index').touch()
    (d/'serial').write_text('01\n')
    (d/'newcerts').mkdir(exist_ok=True)
    host = 'wrong.invalid' if kind == 'wronghost' else 'localhost'
    (d/'ca.cnf').write_text(f'''[ca]
default_ca = local
[local]
dir = .
database = $dir/index
new_certs_dir = $dir/newcerts
certificate = $dir/ca.pem
private_key = $dir/ca.key
serial = $dir/serial
default_md = sha256
default_days = 1
policy = policy
x509_extensions = extensions
[policy]
commonName = supplied
[extensions]
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = DNS:{host}
''')
    validity = ['-startdate','20000101000000Z','-enddate','20000102000000Z'] if kind == 'expired' else []
    run('ca', '-batch', '-config', 'ca.cnf', '-in', 'server.csr', '-out', 'server.pem', *validity)
    ca = d/'ca.pem'
    if kind == 'untrusted':
        run('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'other.key',
            '-out', 'other.pem', '-days', '2', '-subj', '/CN=Other trust root',
            '-addext', 'basicConstraints=critical,CA:TRUE',
        '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
        ca = d/'other.pem'
    for key in d.glob('*.key'):
        key.chmod(0o600)
    return d/'server.key', d/'server.pem', ca
