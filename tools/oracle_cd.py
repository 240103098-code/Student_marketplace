"""Bounded Oracle source deployment policy. Installed independently, never self-updated."""
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
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
GENERATION = re.compile(r'[1-9][0-9]{0,14}-[1-9][0-9]{0,5}-[a-f0-9]{40}')


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
    if (type(workflow_id) is not int or workflow_id < 1 or
        run.get('id') != run_id or run.get('run_attempt') != attempt or
        run.get('workflow_id') != workflow_id or run.get('event') != 'push' or
        run.get('head_branch') != 'main' or run.get('head_sha') != sha or
        run.get('path') != WORKFLOW or
        run.get('repository', {}).get('full_name') != REPOSITORY or
        run.get('head_repository', {}).get('full_name') != REPOSITORY or
        (run.get('status'),run.get('conclusion')) not in
            (('in_progress',None),('completed','success'))):
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
    if not destination.is_dir() or any(destination.iterdir()):raise Rejected('archive-target-not-empty')
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:') as archive:
        members = archive.getmembers()
        if len(members) > 20000 or sum(member.size for member in members) > 100_000_000:
            raise Rejected('archive-limit')
        seen = set()
        for member in members:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or '\\' in member.name or ':' in member.name or
                '..' in path.parts or not path.parts or
                not (member.isdir() or member.isreg()) or
                member.mode & (stat.S_ISUID | stat.S_ISGID)):
                raise Rejected('unsafe-archive')
            if member.name in seen:raise Rejected('duplicate-archive-path')
            seen.add(member.name)
        for member in members:
            target = destination / member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True, mode=0o755)
            else:
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                with archive.extractfile(member) as source, target.open('xb') as stream:
                    shutil.copyfileobj(source, stream)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
        # mkdir's requested mode is reduced by the controller's private umask077.
        # Normalize all source descendants, including implicit parents, explicitly.
        # Keep destination itself0700; Docker COPY must retain readable source dirs.
        for path in destination.rglob('*'):
            if path.is_dir():path.chmod(0o755)


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


def prepare_release(payload, release, sha):
    marker=release/'CD-SOURCE.json'
    identity={'sha':sha,'archive_sha256':hashlib.sha256(payload).hexdigest()}
    if not release.exists():
        release.mkdir(mode=0o700)
        extract_source(payload,release)
        if marker.exists():raise Rejected('reserved-source-path')
        atomic_json(marker,identity)
        return
    protected(release,directory=True,private=True);protected(marker,private=True)
    if json.loads(marker.read_text())!=identity:raise Rejected('release-source-mismatch')
    expected=set()
    with tarfile.open(fileobj=io.BytesIO(payload),mode='r:') as archive:
        for member in archive.getmembers():
            path=release/member.name
            expected.add(path)
            expected.update(parent for parent in path.parents if parent!=release and release in parent.parents)
            if path.is_symlink():raise Rejected('release-link')
            if member.isdir():
                if not path.is_dir():raise Rejected('release-type')
                protected_source(path,0o755)
            elif member.isreg():
                if not path.is_file() or path.read_bytes()!=archive.extractfile(member).read():
                    raise Rejected('release-content')
                protected_source(path,0o755 if member.mode & 0o111 else 0o644)
            else:raise Rejected('release-type')
    if set(release.rglob('*'))!=expected|{marker}:raise Rejected('release-extra-content')


def protected_source(path,mode):
    info=path.lstat()
    if info.st_uid!=0 or path.is_symlink() or stat.S_IMODE(info.st_mode)!=mode:
        raise Rejected('release-mode-or-owner')


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


def github_gate(sha, run_id, attempt, expected_workflow_id):
    workflow = public_json('actions/workflows/implemented-ci.yml')
    if (workflow.get('path') != WORKFLOW or workflow.get('state') != 'active' or
        type(expected_workflow_id) is not int or expected_workflow_id < 1 or
        workflow.get('id') != expected_workflow_id):
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
    atomic_private(path, json.dumps(value, sort_keys=True))


def atomic_private(path, data):
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.new.')
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            os.chmod(temporary, 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def deployment_lock():
    import fcntl
    path = ROOT / 'deploy.lock'
    if path.exists():protected(path, private=True)
    with path.open('a') as lock:
        os.chmod(path, 0o600)
        deadline = time.monotonic() + 300
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:raise Rejected('deployment-busy')
                time.sleep(1)
        yield


def installed():
    if os.geteuid() != 0:raise Rejected('root-controller-required')
    os.umask(0o077)
    for directory in (Path('/'),Path('/opt'), ROOT, ROOT / 'template', ROOT / 'template/ops',
                      ROOT / 'template/ops/oracle', ROOT / 'releases',
                      Path('/etc'), PRIVATE):
        protected(directory, directory=True)
    protected(PRIVATE, directory=True, private=True)
    protected(RUNTIME, private=True)
    for path in (ROOT / 'config.json', ROOT / 'state.json', ROOT / 'backup.sh', ROOT / 'compose.sh',
                 ROOT / 'template/compose.yaml', ROOT / 'template/ops/oracle/compose.https.yaml',
                 ROOT / 'template/ops/oracle/Caddyfile', Path(__file__).resolve()):
        protected(path)


def arm_recovery(host, state, candidate_sha, candidate_image, generation):
    if not GENERATION.fullmatch(generation):raise Rejected('recovery-generation')
    if (ROOT / 'pending.json').exists():raise Rejected('pending-recovery')
    atomic_private(ROOT / 'pending-runtime.env', host.before)
    atomic_json(ROOT / 'pending.json', {'generation': generation, 'previous': state,
                                      'candidate': candidate_sha,'candidate_image':candidate_image})
    execute(['systemd-run', '--unit', 'marketplace-cd-recover-' + generation,
             '--on-active=10m', '--timer-property=AccuracySec=1s', '/usr/bin/python3',
             '-I', str(ROOT / 'controller.py'), 'recover', generation], timeout=20)


def disarm_recovery(generation):
    execute(['systemctl', 'stop', 'marketplace-cd-recover-' + generation + '.timer'], timeout=20)
    # A previous timer can never affect a later generation; recovery rechecks nonce.
    for name in ('pending.json', 'pending-runtime.env', 'pending-retained.json'):
        path = ROOT / name
        if path.exists():
            protected(path, private=True)
            path.unlink()


def recover_generation(generation):
    installed()
    if not GENERATION.fullmatch(generation):raise Rejected('recovery-generation')
    with deployment_lock():
        pending_path = ROOT / 'pending.json'
        if not pending_path.exists():return {'result': 'no-pending-recovery'}
        protected(pending_path, private=True)
        pending = json.loads(pending_path.read_text())
        if pending['generation'] != generation:return {'result': 'obsolete-recovery'}
        state = json.loads((ROOT / 'state.json').read_text())
        if state['sha'] == pending['candidate']:
            # Commit already succeeded; delayed timer must not undo that release.
            host = Host(state)
            retained = ROOT / 'pending-retained.json'
            if retained.exists():
                protected(retained, private=True);host.snapshot = retained.read_bytes()
            host.verify()
            disarm_recovery(generation)
            return {'result': 'committed-release-preserved'}
        previous = pending['previous']
        host = Host(previous)
        host.allowed_images.add(pending['candidate_image'])
        protected(ROOT / 'pending-runtime.env', private=True)
        host.before = (ROOT / 'pending-runtime.env').read_text()
        retained = ROOT / 'pending-retained.json'
        if retained.exists():
            protected(retained, private=True)
            host.snapshot = retained.read_bytes()
        host.select(previous['image'])
        host.start()
        host.verify()
        atomic_json(ROOT / 'state.json', previous)
        disarm_recovery(generation)
        return {'result': 'previous-release-recovered', 'sha': previous['sha']}


def replace_image(data, image):
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', image):
        raise Rejected('invalid-image-id')
    matches=list(re.finditer(r'(?m)^MARKETPLACE_IMAGE=[^\r\n]*',data))
    if len(matches) != 1:
        raise Rejected('image-config')
    match=matches[0]
    return data[:match.start()]+'MARKETPLACE_IMAGE='+image+data[match.end():]


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


def commit_release(host, previous, record):
    try:
        atomic_json(ROOT / 'state.json', record)
    except Exception:
        try:
            host.select(previous['image'])
            host.start()
            host.verify()
        except Exception:
            raise Rejected('state-write-failed-rollback-failed') from None
        raise Rejected('state-write-failed-rollback-restored') from None


class Host:
    def __init__(self, state):
        self.state = state
        self.expected_image = state['image']
        self.allowed_images = {state['image']}
        self.generation = None
        self.candidate_sha = None
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
            'p=pathlib.Path("/data/uploads");files=list(p.rglob("*"));'
            'assert not any(f.is_symlink() for f in files);'
            'd["files"]=sorted((str(f.relative_to(p)),hashlib.sha256(f.read_bytes()).hexdigest()) '
            'for f in files if f.is_file());'
            'print(json.dumps(d,sort_keys=True))'
        )
        return self.compose('exec', '-T', 'app', 'python', '-c', script).stdout

    def backup(self):
        # Installed original95 script uses installed stable operations, not candidate.
        try:
            self.compose('stop', 'proxy')
            self.snapshot = self.retained()
            atomic_private(ROOT / 'pending-retained.json', self.snapshot.decode())
            self.compose('stop', 'app')
            execute(['/bin/bash', str(ROOT / 'backup.sh')], timeout=180)
        except Exception:
            self.start()
            raise

    def select(self, image):
        data = replace_image(self.before, image)
        atomic_private(RUNTIME, data)
        self.expected_image = image
        self.allowed_images.add(image)

    def migrate(self):
        self.compose('run', '--rm', '--no-deps', 'migrate', timeout=180)

    def start(self):
        identifier=self.compose('ps','-aq','app').stdout.decode().strip()
        if identifier:
            if not re.fullmatch(r'[a-f0-9]{12,64}',identifier):raise Rejected('app-container')
            actual=json.loads(execute(['docker','inspect',identifier]).stdout)[0]
            labels=actual.get('Config',{}).get('Labels',{})
            if labels.get('com.docker.compose.project')!=PROJECT or labels.get('com.docker.compose.service')!='app':
                raise Rejected('app-ownership')
            if actual.get('State',{}).get('Paused'):
                if actual.get('Image') not in self.allowed_images:raise Rejected('paused-image-ownership')
                execute(['docker','unpause',identifier],timeout=20)
        self.compose('up', '--detach', '--no-build', '--no-deps', '--force-recreate',
                     '--wait', '--wait-timeout', '120', 'app', 'proxy')
        marker=ROOT/'health-drill.json'
        if self.generation and self.expected_image!=self.state['image'] and marker.exists():
            validate_drill_marker(self.candidate_sha,self.generation)
            consumed=ROOT/('health-drill-consumed-'+self.generation+'.json')
            if consumed.exists():raise Rejected('drill-already-consumed')
            marker.rename(consumed)
            self.confirm_image()
            identifier=self.compose('ps','-q','app').stdout.decode().strip()
            execute(['docker','pause',identifier],timeout=20)

    def verify(self):
        self.confirm_image()
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

    def confirm_image(self):
        identifier = self.compose('ps', '-q', 'app').stdout.decode().strip()
        if not re.fullmatch(r'[a-f0-9]{12,64}', identifier):raise Rejected('app-container')
        actual = json.loads(execute(['docker', 'inspect', identifier]).stdout)[0]
        if (actual.get('Image') != self.expected_image or
            actual.get('Config', {}).get('Labels', {}).get('com.docker.compose.project') != PROJECT or
            actual.get('Config', {}).get('Labels', {}).get('com.docker.compose.service') != 'app'):
            raise Rejected('previous-image-mismatch')


def validate_drill_marker(sha,generation):
    marker=ROOT/'health-drill.json'
    if not marker.exists():return
    protected(marker,private=True)
    if json.loads(marker.read_text())!={'sha':sha,'generation':generation}:
        raise Rejected('drill-marker-mismatch')


def controller(value):
    sha, run_id, attempt = request(value)
    installed()
    with deployment_lock():
        if (ROOT / 'pending.json').exists():raise Rejected('pending-recovery')
        config = json.loads((ROOT / 'config.json').read_text())
        github_gate(sha, run_id, attempt, config['workflow_id'])
        state = json.loads((ROOT / 'state.json').read_text())
        previous = state['sha']
        if (not SHA.fullmatch(previous) or
            not re.fullmatch(r'sha256:[a-f0-9]{64}', state['image'])):
            raise Rejected('previous-source')
        repository = ROOT / 'source.git'
        protected(repository, directory=True)
        git = ['git', '-c', 'core.hooksPath=/dev/null', '--git-dir', str(repository)]
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
            host = Host(state);host.confirm_image();host.verify()
            return {'result': 'already-current', 'sha': sha}
        if shutil.disk_usage(ROOT).free < 6 * 1024**3:raise Rejected('disk-margin')
        release = ROOT / 'releases' / sha
        if not release.exists() and len(list((ROOT / 'releases').iterdir())) >= 8:raise Rejected('release-retention-limit')
        images = execute(['docker', 'image', 'ls', '--filter',
                          'label=marketplace.cd.owner=' + PROJECT, '--quiet']).stdout.splitlines()
        if len(set(images)) >= 8:raise Rejected('image-retention-limit')
        payload = execute(git + ['archive', '--format=tar', sha], timeout=60).stdout
        prepare_release(payload,release,sha)
        compatible_migrations(release, ROOT / 'releases' / previous)
        tag = 'student-marketplace-cd:' + sha
        execute(['docker', 'build', '--platform', 'linux/arm64', '--memory', '2g',
                 '--label', 'marketplace.cd.owner=' + PROJECT,
                 '--label', 'org.opencontainers.image.revision=' + sha,
                 '--tag', tag, str(release)], timeout=1800)
        image = json.loads(execute(['docker', 'image', 'inspect', tag]).stdout)[0]
        if (image['Architecture'] != 'arm64' or image['Config'].get('User') != '10001:10001' or image['Config']['Labels'].get(
            'org.opencontainers.image.revision') != sha):
            raise Rejected('image-provenance')
        check_order(sha, current_main(), previous, ancestor)
        github_gate(sha, run_id, attempt, config['workflow_id'])
        host = Host(state)
        host.verify()
        host.confirm_image()
        generation = f'{run_id}-{attempt}-{sha}'
        validate_drill_marker(sha,generation)
        host.generation=generation;host.candidate_sha=sha
        arm_recovery(host, state, sha, image['Id'], generation)
        try:
            activate(host, image['Id'], state['image'])
        except Rejected as failure:
            if str(failure) == 'activation-failed-rollback-restored':disarm_recovery(generation)
            raise
        commit_release(host, state, {'sha': sha, 'image': image['Id'],
                                     'previous_sha': previous, 'run': run_id,
                                     'attempt': attempt})
        disarm_recovery(generation)
        return {'result': 'deployed', 'sha': sha, 'image': image['Id']}


def main():
    try:
        if len(sys.argv) != 1:
            if len(sys.argv) == 3 and sys.argv[1] == 'recover':
                result = recover_generation(sys.argv[2]);print(json.dumps(result, sort_keys=True));return 0
            raise Rejected('unsupported-controller-arguments')
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
    def interrupted(_number, _frame):raise Rejected('controller-interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    raise SystemExit(main())
