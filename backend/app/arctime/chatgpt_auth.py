"""Official public-client SIWC authorization with a protected local token store."""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import secrets
import time
from typing import Callable
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
from pydantic import SecretStr

from .chatgpt_credentials import AuthError, CredentialStore

ISSUER = 'https://auth.openai.com'
AUTHORIZE = ISSUER + '/api/accounts/authorize'
TOKEN = ISSUER + '/api/accounts/oauth/token'
RESOURCE = 'https://api.openai.com/v1'
PLAN_SCOPE = 'chatgpt.tokens.use.direct'
SCOPES = 'openid profile email offline_access resource.invoke ' + PLAN_SCOPE
MANAGE_URL = 'https://chatgpt.com/settings/usage'
TERMINAL_REFRESH = {'invalid_grant', 'invalid_refresh_token', 'token_expired', 'refresh_token_expired', 'refresh_token_invalidated', 'refresh_token_reused'}


class ChatGPTAuth:
    def __init__(self, root: Path, *, client: httpx.Client | None = None,
                 clock: Callable[[], float] = time.time):
        self.store = CredentialStore(root)
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=20, follow_redirects=False)
        self.clock = clock
        self._pending: dict | None = None
        self._error: str | None = None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _json(self, method: str, url: str, **kwargs) -> dict:
        try:
            response = self.client.request(method, url, timeout=20, follow_redirects=False, **kwargs)
            body = response.json()
            if not response.is_success or not isinstance(body, dict):
                raise AuthError('ChatGPT authorization service is unavailable. Try again.')
            return body
        except (httpx.HTTPError, ValueError):
            raise AuthError('ChatGPT authorization service is unavailable. Try again.') from None

    def status(self) -> dict:
        result = dict(connected=False, sharing=False, account_label=None, error=self._error, manage_url=MANAGE_URL,
                      authorization_pending=False)
        try:
            with self.store.open() as (_, record):
                result['authorization_pending'] = bool(self._pending and self._pending['expires'] > self.clock())
                session = record.get('session')
                registration = record.get('registration', {})
                if isinstance(session, dict):
                    result.update(connected=True, sharing=PLAN_SCOPE in session.get('scopes', []), account_label=registration.get('email') or 'ChatGPT')
                    if not result['sharing']:
                        result['error'] = 'ChatGPT plan usage permission is not enabled.'
        except AuthError as exc:
            result['error'] = str(exc)
        return result

    def begin(self, redirect_uri: str) -> str:
        uri = urlsplit(redirect_uri)
        if (uri.scheme != 'http' or uri.hostname != '127.0.0.1' or uri.path != '/auth/callback'
                or uri.username or uri.password or uri.query or uri.fragment):
            raise AuthError('ChatGPT requires the local 127.0.0.1 authorization callback.')
        with self.store.open() as (fd, record):
            registration = record.get('registration', {})
            state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
            client_id = registration.get('client_id') or record.get('pending_client_id') or 'dynamic_agent_client'
            self._pending = dict(state=state, nonce=nonce, verifier=verifier, redirect_uri=redirect_uri,
                                 client_id=client_id, subject=registration.get('subject'), expires=self.clock()+600)
            self.store.save(fd, record)
            query = dict(client_id=client_id, ext_agent_host_id=record['host_id'], response_type='code',
                         redirect_uri=redirect_uri, scope=SCOPES, resource=RESOURCE, state=state, nonce=nonce,
                         code_challenge_method='S256', code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='))
            if client_id == 'dynamic_agent_client':
                query['agent_name_hint'] = 'Nyaru Clipper'
            elif PLAN_SCOPE not in record.get('session', {}).get('scopes', []):
                query['prompt'] = 'consent'
            self._error = None
            return AUTHORIZE + '?' + urlencode(query)

    def _verify(self, encoded: str, client_id: str, nonce: str | None) -> dict:
        try:
            jwks = self._json('GET', ISSUER + '/.well-known/jwks.json')
            header = jwt.get_unverified_header(encoded)
            keys = [key for key in jwks['keys'] if key.get('kid') == header.get('kid')]
            if len(keys) != 1 or header.get('alg') != 'RS256':
                raise ValueError()
            key = jwt.PyJWK.from_dict(keys[0], algorithm='RS256')
            claims = jwt.decode(encoded, key.key, algorithms=['RS256'], issuer=ISSUER, audience=client_id,
                                options={'require': ['iss', 'aud', 'sub', 'exp', 'iat']})
            if not claims['sub'] or (nonce is not None and claims.get('nonce') != nonce):
                raise ValueError()
            if 'azp' in claims and claims['azp'] != client_id:
                raise ValueError()
            if isinstance(claims['aud'], list) and len(claims['aud']) > 1 and claims.get('azp') != client_id:
                raise ValueError()
            return claims
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise AuthError('ChatGPT identity could not be verified. Sign in again.') from None

    def _session(self, body: dict, old: dict | None = None) -> dict:
        old = old or {}
        access = body.get('access_token')
        refresh = body.get('refresh_token', old.get('refresh_token'))
        expiry = body.get('expires_in')
        scope = body.get('scope')
        if (not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh
                or not isinstance(body.get('token_type'), str) or body['token_type'].lower() != 'bearer' or type(expiry) not in (int, float)
                or not 0 < expiry <= 31536000 or (scope is not None and not isinstance(scope, str))):
            raise AuthError('ChatGPT returned an invalid token response.')
        return dict(access_token=access, refresh_token=refresh, expires_at=self.clock()+expiry,
                    scopes=scope.split() if scope is not None else old.get('scopes', []),
                    id_token=body.get('id_token', old.get('id_token')))

    def complete(self, *, code: str, state: str, client_id: str | None = None, error: str | None = None) -> None:
        try:
            self._complete(code=code, state=state, client_id=client_id, error=error)
        except AuthError as exc:
            self._error = str(exc)
            raise

    def _complete(self, *, code: str, state: str, client_id: str | None, error: str | None) -> None:
        with self.store.open() as (fd, record):
            pending = self._pending
            if not pending or not secrets.compare_digest(pending['state'], state):
                raise AuthError('ChatGPT sign-in could not be verified.')
            self._pending = None
            if pending['expires'] <= self.clock():
                raise AuthError('ChatGPT sign-in expired. Start again.')
            if error is not None or not code:
                raise AuthError('ChatGPT sign-in was not completed. Try again.')
            issued = client_id or pending['client_id']
            if issued == 'dynamic_agent_client' or not issued.startswith('oaiapp_'):
                raise AuthError('ChatGPT registration did not return an issued client ID.')
            if pending['client_id'] != 'dynamic_agent_client' and issued != pending['client_id']:
                raise AuthError('ChatGPT registration did not match the selected account.')
            if not record.get('registration'):
                record['pending_client_id'] = issued
                self.store.save(fd, record)
            body = self._json('POST', TOKEN, data=dict(grant_type='authorization_code', client_id=issued,
                              code=code, code_verifier=pending['verifier'], redirect_uri=pending['redirect_uri'], resource=RESOURCE))
            claims = self._verify(body.get('id_token', ''), issued, pending['nonce'])
            if pending['subject'] and claims['sub'] != pending['subject']:
                raise AuthError('ChatGPT identity did not match the selected account.')
            session = self._session(body)
            record.pop('pending_client_id', None)
            record.update(registration=dict(client_id=issued, subject=claims['sub'], email=claims.get('email')), session=session)
            self.store.save(fd, record)
            self._error = None

    def token(self) -> SecretStr:
        with self.store.open() as (fd, record):
            session = record.get('session')
            if not session or PLAN_SCOPE not in session.get('scopes', []):
                raise AuthError('Sign in and enable ChatGPT plan usage first.')
            if session['expires_at'] <= self.clock()+60:
                issued = record['registration']['client_id']
                try:
                    response = self.client.post(TOKEN, data=dict(grant_type='refresh_token', client_id=issued,
                                                refresh_token=session['refresh_token'], resource=RESOURCE), timeout=20, follow_redirects=False)
                    body = response.json()
                    if not isinstance(body, dict):
                        raise ValueError()
                    if not response.is_success:
                        if body.get('error') in TERMINAL_REFRESH:
                            record.pop('session', None)
                            self.store.save(fd, record)
                            self._error = 'ChatGPT session expired. Sign in again.'
                        raise AuthError(self._error or 'ChatGPT refresh is unavailable. Try again.')
                    renewed = self._session(body, session)
                    if 'id_token' in body:
                        claims = self._verify(body['id_token'], issued, None)
                        if claims['sub'] != record['registration']['subject']:
                            raise AuthError('ChatGPT refreshed identity did not match.')
                    record['session'] = renewed
                    self.store.save(fd, record)
                    session = renewed
                except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
                    if isinstance(exc, AuthError):
                        raise
                    raise AuthError('ChatGPT refresh is unavailable. Try again.') from None
            if PLAN_SCOPE not in session['scopes']:
                raise AuthError('ChatGPT plan usage permission is not enabled.')
            return SecretStr(session['access_token'])

    def models(self) -> list[dict[str, str]]:
        body = self._json('GET', RESOURCE+'/models', headers={'Authorization': 'Bearer '+self.token().get_secret_value()})
        models = body.get('models')
        if not isinstance(models, list):
            raise AuthError('ChatGPT returned an invalid model catalog.')
        result = []
        for model in models:
            if not isinstance(model, dict):
                raise AuthError('ChatGPT returned an invalid model catalog.')
            if model.get('visibility') == 'list':
                if not all(isinstance(model.get(field), str) and model[field] for field in ('slug', 'display_name')):
                    raise AuthError('ChatGPT returned an invalid model catalog.')
                result.append({field: model[field] for field in ('slug', 'display_name')})
        return result

    def logout(self) -> None:
        with self.store.open() as (fd, record):
            self._pending = None
            session = record.get('session')
            confirmed = not session
            if session:
                try:
                    discovery = self._json('GET', ISSUER+'/.well-known/openid-configuration')
                    endpoint = discovery['revocation_endpoint']
                    url = urlsplit(endpoint)
                    if discovery.get('issuer') != ISSUER or url.scheme != 'https' or url.netloc != 'auth.openai.com' or url.fragment or url.username:
                        raise ValueError()
                    for attempt in range(2):
                        try:
                            response = self.client.post(endpoint, data=dict(token=session['refresh_token'], token_type_hint='refresh_token', client_id=record['registration']['client_id']), timeout=20, follow_redirects=False)
                            confirmed = response.status_code == 200
                            if confirmed or response.status_code < 500:
                                break
                        except httpx.HTTPError:
                            pass
                        if attempt == 0:
                            time.sleep(0.2)
                except (AuthError, ValueError, KeyError, TypeError):
                    pass
            record.pop('session', None)
            self.store.save(fd, record)
            self._error = None if confirmed else 'Signed out locally; remote revocation was not confirmed. Disconnect in ChatGPT Settings.'
