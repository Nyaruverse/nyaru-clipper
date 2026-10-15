"""Private, atomic SIWC credential storage and cross-process serialization."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import secrets
import stat
import threading
import uuid


class AuthError(ValueError):
    """A safe message suitable for local UI display."""


class CredentialStore:
    def __init__(self, root: Path):
        self.root = Path(root).absolute()
        self._lock = threading.RLock()

    @contextmanager
    def open(self):
        # Directory-relative operations prevent replacement of the checked directory.
        with self._lock:
            directory = self.root / '.chatgpt'
            fd = lock_fd = None
            try:
                for path in [directory, *directory.parents]:
                    if path.is_symlink():
                        raise AuthError('ChatGPT credential path must not be a symbolic link.')
                directory.mkdir(mode=0o700, parents=True, exist_ok=True)
                fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                info = os.fstat(fd)
                if info.st_uid != os.getuid() or info.st_mode & 0o077:
                    raise AuthError('ChatGPT credential directory requires owner-only permissions.')
                lock_fd = os.open('lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                self._check_file(os.fstat(lock_fd))
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
                try:
                    file_fd = os.open('credentials.json', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
                except FileNotFoundError:
                    record = {'host_id': 'urn:uuid:' + str(uuid.uuid4())}
                else:
                    with os.fdopen(file_fd) as stream:
                        self._check_file(os.fstat(stream.fileno()))
                        record = json.load(stream)
                    if not isinstance(record, dict) or not isinstance(record.get('host_id'), str):
                        raise AuthError('ChatGPT credential storage is invalid.')
                self._validate_record(record)
                yield fd, record
            except (OSError, ValueError, TypeError) as exc:
                if isinstance(exc, AuthError):
                    raise
                raise AuthError('ChatGPT credential storage is unavailable or invalid.') from None
            finally:
                if lock_fd is not None:
                    os.close(lock_fd)
                if fd is not None:
                    os.close(fd)

    @staticmethod
    def _validate_record(record: dict):
        pending = record.get('pending_client_id')
        if pending is not None and (not isinstance(pending, str) or not pending.startswith('oaiapp_')):
            raise AuthError('ChatGPT pending registration is invalid.')
        registration = record.get('registration')
        session = record.get('session')
        if registration is not None and (
            not isinstance(registration, dict)
            or not all(isinstance(registration.get(key), str) and registration[key]
                       for key in ('client_id', 'subject'))
            or not registration['client_id'].startswith('oaiapp_')
            or (registration.get('email') is not None and not isinstance(registration['email'], str))
        ):
            raise AuthError('ChatGPT credential storage is invalid. Sign in again.')
        if session is not None and (
            not registration or not isinstance(session, dict)
            or not all(isinstance(session.get(key), str) and session[key]
                       for key in ('access_token', 'refresh_token', 'id_token'))
            or type(session.get('expires_at')) not in (int, float)
            or not isinstance(session.get('scopes'), list)
            or not all(isinstance(scope, str) for scope in session['scopes'])
        ):
            raise AuthError('ChatGPT credential storage is invalid. Sign in again.')

    @staticmethod
    def _check_file(info):
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
            raise AuthError('ChatGPT credential file requires a private regular file.')

    @staticmethod
    def save(fd: int, record: dict):
        CredentialStore._validate_record(record)
        name = '.pending-' + secrets.token_hex(12)
        try:
            file_fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            with os.fdopen(file_fd, 'w') as stream:
                json.dump(record, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, 'credentials.json', src_dir_fd=fd, dst_dir_fd=fd)
            os.fsync(fd)
        finally:
            try:
                os.unlink(name, dir_fd=fd)
            except FileNotFoundError:
                pass
