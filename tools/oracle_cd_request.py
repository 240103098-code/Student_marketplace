"""Actions-only restricted SSH client. Never prints key or raw SSH diagnostics."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from tools.oracle_cd import Rejected, runner_gate


def main():
    directory = None
    try:
        sha, run, attempt = runner_gate(os.environ)
        host = os.environ.get('ORACLE_DEMO_HOST', '')
        key = os.environ.get('ORACLE_DEMO_DEPLOY_KEY', '')
        trust = os.environ.get('ORACLE_DEMO_KNOWN_HOSTS', '')
        if (not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9.-]{0,251}[a-zA-Z0-9]', host)
            or '-----BEGIN OPENSSH PRIVATE KEY-----' not in key or len(key) > 16384
            or not trust or len(trust) > 16384):
            raise Rejected('missing-or-invalid-deployment-access')
        # Explicit host field; hashed hosts and wildcard patterns are not accepted.
        lines = [line.split() for line in trust.splitlines() if line.strip()]
        if (not lines or any(len(parts) != 3 or parts[0] != host or
                            parts[1] not in ('ssh-ed25519', 'ecdsa-sha2-nistp256', 'ssh-rsa')
                            for parts in lines)):
            raise Rejected('invalid-pinned-host-trust')
        directory = Path(tempfile.mkdtemp(prefix='marketplace-cd-'))
        directory.chmod(0o700)
        private = directory / 'key'
        known = directory / 'known_hosts'
        for path, value in ((private, key), (known, trust)):
            path.write_text(value, encoding='utf-8')
            path.chmod(0o600)
        command = ['ssh', '-F', '/dev/null', '-i', str(private),
                   '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
                   '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + str(known),
                   '-o', 'GlobalKnownHostsFile=/dev/null', '-o', 'ConnectTimeout=20',
                   '-o', 'ConnectionAttempts=1', '-o', 'ServerAliveInterval=15',
                   '-o', 'ServerAliveCountMax=3', '-o', 'ClearAllForwardings=yes',
                   '-o', 'RequestTTY=no', 'marketplace-deploy@' + host,
                   f'deploy {sha} {run} {attempt}']
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=3000, check=False)
        if result.returncode:
            raise Rejected('remote-deployment-failed')
        if len(result.stdout) > 4096:
            raise Rejected('remote-result-limit')
        record = json.loads(result.stdout)
        if (record.get('result') not in ('deployed', 'already-current') or
            record.get('sha') != sha):
            raise Rejected('remote-result')
        print(json.dumps({'result': record['result'], 'sha': sha}))
        return 0
    except Rejected as error:
        print(json.dumps({'result': 'FAIL', 'stage': str(error)}))
        return 1
    except Exception:
        print('{"result":"FAIL","stage":"deployment-client-error"}')
        return 1
    finally:
        if directory:
            shutil.rmtree(directory)


if __name__ == '__main__':
    raise SystemExit(main())
