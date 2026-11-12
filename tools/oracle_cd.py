"""Bounded Oracle source deployment policy. Installed independently, never self-updated."""
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile
import time
import urllib.request

REPOSITORY = '240103098-code/Student_marketplace'
WORKFLOW = '.github/workflows/implemented-ci.yml'
REQUIRED = ('CI / implemented checks', 'CI / required gate')
SHA = re.compile(r'[a-f0-9]{40}')
REQUEST = re.compile(r'deploy ([a-f0-9]{40}) ([1-9][0-9]{0,14}) ([1-9][0-9]{0,5})')
ROOT = Path('/opt/student-marketplace-cd')
PRIVATE = Path('/etc/student-marketplace-demo')
RUNTIME = PRIVATE / 'runtime.env'
PROJECT = 'student-marketplace-oracle-demo'


class Rejected(Exception):
    """Only static failure codes cross the public boundary."""


def request(value):
    match = REQUEST.fullmatch(value)
    if not match:
        raise Rejected('invalid-request')
    sha, run, attempt = match.groups()
    return sha, int(run), int(attempt)


def runner_gate(environment):
    expected = {'GITHUB_REPOSITORY': REPOSITORY, 'GITHUB_EVENT_NAME': 'push',
                'GITHUB_REF': 'refs/heads/main', 'IMPLEMENTED_RESULT': 'success',
                'GATE_RESULT': 'success'}
    if any(environment.get(key) != value for key, value in expected.items()):
        raise Rejected('runner-gate')
    return request('deploy ' + environment.get('GITHUB_SHA', '') + ' ' +
                   environment.get('GITHUB_RUN_ID', '') + ' ' +
                   environment.get('GITHUB_RUN_ATTEMPT', ''))


def validate_run(run, jobs, sha, run_id, attempt, workflow_id):
    if (not isinstance(workflow_id, int) or workflow_id < 1 or
        run.get('id') != run_id or run.get('run_attempt') != attempt or
        run.get('workflow_id') != workflow_id or run.get('event') != 'push' or
        run.get('head_branch') != 'main' or run.get('head_sha') != sha or
        run.get('path') != WORKFLOW or
        run.get('repository', {}).get('full_name') != REPOSITORY or
        run.get('head_repository', {}).get('full_name') != REPOSITORY or
        run.get('status') not in ('in_progress', 'completed') or
        run.get('conclusion') not in (None, 'success')):
        raise Rejected('untrusted-run')
    for name in REQUIRED:
        matches = [job for job in jobs if job.get('name') == name]
        if (len(matches) != 1 or matches[0].get('status') != 'completed' or
            matches[0].get('conclusion') != 'success' or
            matches[0].get('head_sha') != sha or
            matches[0].get('run_id') != run_id or
            matches[0].get('run_attempt') != attempt):
            raise Rejected('required-job')


def check_order(sha, main, previous, ancestor):
    if sha != main:
        raise Rejected('stale-main')
    if previous != sha and not ancestor(previous, sha):
        raise Rejected('non-forward-release')


def extract_source(payload, destination):
    """Git archive only: reject links, traversal, special files and size bombs."""
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:') as archive:
        members = archive.getmembers()
        if len(members) > 20000 or sum(member.size for member in members) > 100_000_000:
            raise Rejected('archive-limit')
        for member in members:
            path = Path(member.name)
            if (path.is_absolute() or '\\' in member.name or ':' in member.name or
                '..' in path.parts or not path.parts or
                not (member.isdir() or member.isreg()) or
                member.mode & (stat.S_ISUID | stat.S_ISGID)):
                raise Rejected('unsafe-archive')
        archive.extractall(destination, filter='data')


def compatible_migrations(candidate, previous):
    def inventory(root):
        result = {}
        for prefix in ('migrations', 'migrations_sqlite'):
            directory = root / prefix
            if not directory.is_dir():
                raise Rejected('migration-inventory')
            for path in directory.rglob('*'):
                if path.is_symlink():
                    raise Rejected('migration-link')
                if path.is_file():
                    result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        for name in ('alembic.ini', 'alembic-sqlite.ini'):
            result[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
        return result
    if inventory(candidate) != inventory(previous):
        raise Rejected('migration-change-needs-manual-review')


def public_json(path):
    url = 'https://api.github.com/repos/' + REPOSITORY + '/' + path
    req = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json',
                                               'User-Agent': 'student-marketplace-cd',
                                               'X-GitHub-Api-Version': '2022-11-28'})
    with urllib.request.urlopen(req, timeout=20) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise Rejected('github-response-limit')
    return json.loads(data)


def github_gate(sha, run_id, attempt):
    workflow = public_json('actions/workflows/implemented-ci.yml')
    if workflow.get('path') != WORKFLOW or workflow.get('state') != 'active':
        raise Rejected('workflow-identity')
    run = public_json(f'actions/runs/{run_id}/attempts/{attempt}')
    jobs = []
    for page in range(1, 11):
        body = public_json(f'actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100&page={page}')
        batch = body.get('jobs')
        if not isinstance(batch, list):
            raise Rejected('github-jobs')
        jobs.extend(batch)
        if len(jobs) >= body.get('total_count', -1):
            break
    else:
        raise Rejected('github-jobs-limit')
    if len(jobs) != body.get('total_count'):
        raise Rejected('github-jobs-count')
    validate_run(run, jobs, sha, run_id, attempt, workflow.get('id'))


def execute(arguments, timeout=60, input_bytes=None, allow_failure=False):
    result = subprocess.run(arguments, input=input_bytes, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout, check=False,
                            env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': '/root',
                                 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
                                 'GIT_TERMINAL_PROMPT': '0'})
    if result.returncode and not allow_failure:
        raise Rejected('subprocess-failed')
    return result


def protected(path, directory=False, private=False):
    info = path.lstat()
    if (info.st_uid != 0 or info.st_mode & 0o022 or path.is_symlink() or
        (not stat.S_ISDIR(info.st_mode) if directory else not stat.S_ISREG(info.st_mode))):
        raise Rejected('unsafe-installed-path')
    if private and stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600):
        raise Rejected('private-mode')


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.new')
    with temporary.open('x', encoding='utf-8') as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def replace_image(data, image):
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', image):
        raise Rejected('invalid-image-id')
    lines = data.splitlines()
    if sum(line.startswith('MARKETPLACE_IMAGE=') for line in lines) != 1:
        raise Rejected('image-config')
    return '\n'.join('MARKETPLACE_IMAGE=' + image if line.startswith('MARKETPLACE_IMAGE=')
                     else line for line in lines) + '\n'


def activate(adapter, candidate, previous):
    """Failure never turns into success merely because recovery succeeded."""
    try:
        adapter.backup()
        adapter.select(candidate)
        adapter.migrate()
        adapter.start()
        adapter.verify()
    except Exception as failure:
        try:
            adapter.select(previous)
            adapter.start()
            adapter.verify()
        except Exception:
            raise Rejected('activation-failed-rollback-failed') from failure
        raise Rejected('activation-failed-rollback-restored') from failure


class Host:
    def __init__(self, state):
        self.state = state
        self.before = RUNTIME.read_text()
        self.snapshot = None

    def compose(self, *args, timeout=180):
        command = ['docker', 'compose', '--project-name', PROJECT,
                   '--project-directory', str(ROOT / 'template'),
                   '--env-file', str(RUNTIME)]
        if (PRIVATE / 'smtp.env').exists():
            protected(PRIVATE / 'smtp.env', private=True)
            command += ['--env-file', str(PRIVATE / 'smtp.env')]
        command += ['-f', str(ROOT / 'template/compose.yaml'), '-f',
                    str(ROOT / 'template/ops/oracle/compose.https.yaml')]
        return execute(command + list(args), timeout=timeout)

    def retained(self):
        # No identities or contents leave the container: only ordered state hashes.
        script = (
            'import hashlib,json,pathlib;from backend.config import Settings;'
            'from sqlalchemy import create_engine,text;'
            's=Settings();e=create_engine(s.database_url.get_secret_value());'
            'c=e.connect();d={};'
            'tables=("users","listings","listing_photos","refresh_sessions",'
            '"email_codes","categories","listing_reports");'
            'd["db"]={t:hashlib.sha256("\\n".join(sorted(r[0] for r in '
            'c.execute(text("SELECT row_to_json(x)::text FROM "+t+" x")))).encode()).hexdigest() '
            'for t in tables};'
            'p=pathlib.Path("/data/uploads");'
            'd["files"]=sorted(hashlib.sha256(f.read_bytes()).hexdigest() '
            'for f in p.rglob("*") if f.is_file());'
            'print(json.dumps(d,sort_keys=True))'
        )
        return self.compose('exec', '-T', 'app', 'python', '-c', script).stdout

    def backup(self):
        # Installed original95 script uses installed stable operations, not candidate.
        try:
            self.compose('stop', 'proxy')
            self.snapshot = self.retained()
            self.compose('stop', 'app')
            execute(['/bin/bash', str(ROOT / 'backup.sh')], timeout=180)
        except Exception:
            self.start()
            raise

    def select(self, image):
        data = replace_image(self.before, image)
        temporary = RUNTIME.with_name('runtime.env.cd-new')
        with temporary.open('x', encoding='utf-8') as stream:
            os.chmod(temporary, 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, RUNTIME)

    def migrate(self):
        self.compose('run', '--rm', '--no-deps', 'migrate', timeout=180)

    def start(self):
        self.compose('up', '--detach', '--no-build', '--no-deps', '--force-recreate',
                     '--wait', '--wait-timeout', '120', 'app', 'proxy')

    def verify(self):
        # Hostname is a private installed input, never a request argument.
        config = json.loads((ROOT / 'config.json').read_text())
        hostname = config['hostname']
        if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,251}[a-z0-9]', hostname):
            raise Rejected('hostname-config')
        for path, marker in (('/health/ready', b''), ('/', b'<html')):
            expected = 'https://' + hostname + path
            with urllib.request.urlopen(expected, timeout=20) as response:
                if (response.geturl() != expected or response.status != 200 or
                    marker not in response.read(1_000_000).lower()):
                    raise Rejected('public-health')
        if self.snapshot is not None and self.retained() != self.snapshot:
            raise Rejected('retained-state-changed')


def controller(value):
    if os.geteuid() != 0:
        raise Rejected('root-controller-required')
    os.umask(0o077)
    sha, run_id, attempt = request(value)
    for directory in (ROOT, ROOT / 'template', ROOT / 'releases', PRIVATE):
        protected(directory, directory=True)
    protected(PRIVATE, directory=True, private=True)
    protected(RUNTIME, private=True)
    for path in (ROOT / 'config.json', ROOT / 'state.json', ROOT / 'backup.sh',
                 ROOT / 'template/compose.yaml',
                 ROOT / 'template/ops/oracle/compose.https.yaml',
                 ROOT / 'template/ops/oracle/Caddyfile', RUNTIME):
        protected(path)
    protected(Path(__file__).resolve())
    import fcntl
    with (ROOT / 'deploy.lock').open('a') as lock:
        deadline = time.monotonic() + 300
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise Rejected('deployment-busy')
                time.sleep(1)
        github_gate(sha, run_id, attempt)
        state = json.loads((ROOT / 'state.json').read_text())
        previous = state['sha']
        if (not SHA.fullmatch(previous) or
            not re.fullmatch(r'sha256:[a-f0-9]{64}', state['image'])):
            raise Rejected('previous-source')
        repository = ROOT / 'source.git'
        protected(repository, directory=True)
        git = ['git', '--git-dir', str(repository)]
        execute(git + ['fetch', '--no-tags', '--no-recurse-submodules',
                       'https://github.com/' + REPOSITORY + '.git',
                       '+refs/heads/main:refs/heads/main'], timeout=120)
        def current_main():
            public_main = public_json('git/ref/heads/main')['object']['sha']
            local_main = execute(git + ['rev-parse', 'refs/heads/main']).stdout.decode().strip()
            if public_main != local_main:
                raise Rejected('main-changed')
            return public_main
        def ancestor(old, new):
            return execute(git + ['merge-base', '--is-ancestor', old, new], allow_failure=True).returncode == 0
        check_order(sha, current_main(), previous, ancestor)
        if sha == previous:
            Host(state).verify()
            return {'result': 'already-current', 'sha': sha}
        release = ROOT / 'releases' / sha
        if release.exists():
            raise Rejected('existing-uncommitted-release')
        release.mkdir(mode=0o700)
        payload = execute(git + ['archive', '--format=tar', sha], timeout=60).stdout
        extract_source(payload, release)
        compatible_migrations(release, ROOT / 'releases' / previous)
        tag = 'student-marketplace-cd:' + sha
        execute(['docker', 'build', '--platform', 'linux/arm64', '--memory', '2g',
                 '--label', 'org.opencontainers.image.revision=' + sha,
                 '--tag', tag, str(release)], timeout=1800)
        image = json.loads(execute(['docker', 'image', 'inspect', tag]).stdout)[0]
        if (image['Architecture'] != 'arm64' or image['Config']['Labels'].get(
            'org.opencontainers.image.revision') != sha):
            raise Rejected('image-provenance')
        check_order(sha, current_main(), previous, ancestor)
        github_gate(sha, run_id, attempt)
        host = Host(state)
        host.verify()
        running = host.compose('images', '-q', 'app').stdout.decode().strip()
        if execute(['docker', 'image', 'inspect', running, '--format', '{{.Id}}']).stdout.decode().strip() != state['image']:
            raise Rejected('previous-image-mismatch')
        activate(host, image['Id'], state['image'])
        try:
            atomic_json(ROOT / 'state.json', {'sha': sha, 'image': image['Id'],
                                             'previous_sha': previous, 'run': run_id,
                                             'attempt': attempt})
        except Exception:
            try:
                host.select(state['image'])
                host.start()
                host.verify()
            except Exception:
                raise Rejected('state-write-failed-rollback-failed')
            raise Rejected('state-write-failed-rollback-restored')
        return {'result': 'deployed', 'sha': sha, 'image': image['Id']}


def main():
    try:
        value = sys.stdin.buffer.read(257)
        if len(value) > 256:
            raise Rejected('request-limit')
        result = controller(value.decode('ascii'))
        print(json.dumps(result, sort_keys=True))
        return 0
    except Rejected as error:
        print(json.dumps({'result': 'FAIL', 'stage': str(error)}))
        return 1
    except Exception:
        print('{"result":"FAIL","stage":"controller-error"}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
