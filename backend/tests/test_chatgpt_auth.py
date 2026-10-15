import base64
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.arctime.chatgpt_auth import AuthError, ChatGPTAuth

ISSUER = 'https://auth.openai.com'
SCOPE = 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct'

@pytest.fixture
def harness(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid='key', alg='RS256', use='sig')
    state = {'claims': {}, 'scope': SCOPE, 'requests': [], 'now': time.time(), 'refreshes': 0}
    def handler(req):
        state['requests'].append(req)
        if req.url.path.endswith('openid-configuration'):
            return httpx.Response(200, json={'issuer': ISSUER, 'jwks_uri': ISSUER+'/.well-known/jwks.json', 'revocation_endpoint': ISSUER+'/revoke'})
        if req.url.path.endswith('jwks.json'):
            return httpx.Response(200, json={'keys': [jwk]})
        if req.url.path == '/revoke':
            return httpx.Response(state.get('revoke_status', 200))
        if req.url.path == '/v1/models':
            assert req.headers['authorization'] == 'Bearer access-secret'
            return httpx.Response(200, json={'models': [{'slug': 'server-model', 'display_name': 'Model', 'visibility': 'list'}, {'slug': 'hidden', 'visibility': 'hidden'}]})
        form = parse_qs(req.content.decode())
        if form['grant_type'] == ['refresh_token']:
            state['refreshes'] += 1
            assert 'scope' not in form
            if state.get('refresh_error'):
                return httpx.Response(400, json={'error': state['refresh_error'], 'detail': 'secret-must-not-leak'})
            return httpx.Response(200, json={'access_token': 'rotated-access', 'refresh_token': 'rotated-refresh', 'token_type': 'Bearer', 'expires_in': 3600})
        verifier = form['code_verifier'][0]
        assert base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=') == state['query']['code_challenge'][0]
        assert form['redirect_uri'] == state['query']['redirect_uri']
        claims = {'iss': ISSUER, 'aud': 'oaiapp_test', 'sub': 'subject', 'nonce': state['query']['nonce'][0], 'iat': int(time.time()), 'exp': int(time.time())+3600, 'email': 'test@example.test'}
        claims.update(state['claims'])
        token = jwt.encode(claims, state.get('signing_key', key), algorithm='RS256', headers={'kid': 'key'})
        body = {'id_token': token, 'access_token': 'access-secret', 'refresh_token': 'refresh-secret', 'token_type': 'Bearer', 'expires_in': 3600, 'scope': state['scope']}
        body.update(state.get('response', {}))
        return httpx.Response(200, json=body)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    auth = ChatGPTAuth(tmp_path, client=client, clock=lambda: state['now'])
    def begin():
        state['query'] = parse_qs(urlsplit(auth.begin('http://127.0.0.1:8787/auth/callback')).query)
        return state['query']['state'][0]
    def login():
        auth.complete(code='code-secret', state=begin(), client_id='oaiapp_test')
    return auth, state, begin, login, tmp_path, client


def test_roundtrip_restart_models_logout(harness):
    auth, s, begin, login, root, client = harness
    login()
    assert auth.status()['connected'] and auth.status()['sharing']
    assert auth.models() == [{'slug': 'server-model', 'display_name': 'Model'}]
    assert 'secret' not in json.dumps(auth.status())
    file = root/'.chatgpt/credentials.json'
    assert file.stat().st_mode & 0o777 == 0o600
    assert file.parent.stat().st_mode & 0o777 == 0o700
    fresh = ChatGPTAuth(root, client=client)
    assert fresh.token().get_secret_value() == 'access-secret'
    old_host = json.loads(file.read_text())['host_id']
    auth.logout()
    assert not auth.status()['connected']
    saved = file.read_text()
    assert 'access-secret' not in saved and 'refresh-secret' not in saved and 'id_token' not in saved
    begin()
    assert s['query']['client_id'] == ['oaiapp_test']
    assert 'agent_name_hint' not in s['query']
    assert s['query']['ext_agent_host_id'] == [old_host]
    assert any(r.url.path == '/revoke' for r in s['requests'])

@pytest.mark.parametrize('case', ['wrong', 'expired', 'missing_client', 'denied', 'replay'])
def test_callback_rejections(harness, case):
    auth, s, begin, login, *_ = harness
    state = begin()
    args = {'code': 'code-secret', 'state': state, 'client_id': 'oaiapp_test'}
    if case == 'wrong': args['state'] = 'wrong'
    if case == 'expired': s['now'] += 601
    if case == 'missing_client': args['client_id'] = None
    if case == 'denied': args['error'] = 'access_denied'
    if case == 'replay': auth.complete(**args)
    with pytest.raises(AuthError): auth.complete(**args)
    if case != 'replay': assert not auth.status()['connected']

@pytest.mark.parametrize('claim,value', [('iss','https://evil.test'), ('aud','other'), ('nonce','wrong'), ('exp',1), ('sub','')])
def test_signed_invalid_claims(harness, claim, value):
    auth, s, _, login, *_ = harness
    s['claims'][claim] = value
    with pytest.raises(AuthError): login()
    assert not auth.status()['connected']


def test_signature_and_returning_identity_preserve_session(harness):
    auth, s, begin, login, root, _ = harness
    login()
    previous = (root/'.chatgpt/credentials.json').read_bytes()
    s['claims']['sub'] = 'other'
    with pytest.raises(AuthError): login()
    assert (root/'.chatgpt/credentials.json').read_bytes() == previous
    s['claims'] = {}
    s['signing_key'] = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(AuthError): login()
    assert auth.token().get_secret_value() == 'access-secret'
    with pytest.raises(AuthError): auth.complete(code='x', state=begin(), client_id='other')


def test_missing_permission_keeps_identity(harness):
    auth, s, begin, login, *_ = harness
    s['scope'] = 'openid email'
    login()
    assert auth.status()['connected'] and not auth.status()['sharing']
    with pytest.raises(AuthError): auth.token()
    begin()
    assert s['query']['prompt'] == ['consent']


def test_refresh_rotation_serialized_across_instances(harness):
    auth, s, _, login, root, client = harness
    login()
    other = ChatGPTAuth(root, client=client, clock=lambda: s['now'])
    s['now'] += 3590
    with ThreadPoolExecutor(2) as pool:
        values = list(pool.map(lambda a: a.token().get_secret_value(), [auth, other]))
    assert values == ['rotated-access', 'rotated-access']
    assert s['refreshes'] == 1
    saved = json.loads((root/'.chatgpt/credentials.json').read_text())
    assert saved['session']['refresh_token'] == 'rotated-refresh'

@pytest.mark.parametrize('error,connected', [('invalid_grant',False), ('temporarily_unavailable',True)])
def test_refresh_error_sanitized(harness, error, connected):
    auth, s, _, login, *_ = harness
    login(); s['now'] += 3590; s['refresh_error'] = error
    with pytest.raises(AuthError) as exc: auth.token()
    assert 'secret' not in str(exc.value)
    assert auth.status()['connected'] is connected

@pytest.mark.parametrize('response', [{'access_token': None}, {'expires_in': -1}, {'scope': []}, {'id_token': 'malformed-secret'}, {'token_type': 'Other'}])
def test_malformed_response(harness, response):
    auth, s, _, login, *_ = harness
    s['response'] = response
    with pytest.raises(AuthError) as exc: login()
    assert 'secret' not in str(exc.value)
    assert not auth.status()['connected']

@pytest.mark.parametrize('kind', ['directory_symlink', 'file_symlink', 'insecure_file', 'insecure_directory'])
def test_reject_unsafe_storage(tmp_path, kind):
    root = tmp_path/'root'; root.mkdir()
    directory = root/'.chatgpt'
    target = tmp_path/'target'; target.mkdir(mode=0o700)
    if kind == 'directory_symlink': directory.symlink_to(target)
    else:
        directory.mkdir(mode=0o700)
        file = directory/'credentials.json'
        if kind == 'file_symlink': file.symlink_to(target/'secret')
        elif kind == 'insecure_file': file.write_text('{}'); file.chmod(0o644)
        else: directory.chmod(0o777)
    with pytest.raises(AuthError): ChatGPTAuth(root).begin('http://127.0.0.1:8787/auth/callback')


def test_logout_unconfirmed_revocation_clears_local(harness):
    auth, s, _, login, root, _ = harness
    login(); s['revoke_status'] = 503
    auth.logout()
    assert not auth.status()['connected']
    assert auth.status()['error']
    assert 'secret' not in (root/'.chatgpt/credentials.json').read_text()

@pytest.mark.parametrize('uri', ['http://localhost:8787/auth/callback', 'https://127.0.0.1/auth/callback', 'http://127.0.0.1:8787/callback', 'http://127.0.0.1:8787/auth/callback?x=1'])
def test_only_exact_loopback_callback(harness, uri):
    with pytest.raises(AuthError): harness[0].begin(uri)

@pytest.mark.parametrize('body', [{'session': []}, {'session': {'expires_at': 'secret'}}, {'registration': []}])
def test_corrupt_storage_is_safe_and_actionable(harness, body):
    auth, _, _, login, root, _ = harness
    login()
    path = root/'.chatgpt/credentials.json'
    record = json.loads(path.read_text()); record.update(body)
    path.write_text(json.dumps(record))
    status = auth.status()
    assert status['connected'] is False and status['error']
    assert 'secret' not in json.dumps(status)
    with pytest.raises(AuthError): auth.token()

@pytest.mark.parametrize('value', [None, [], 7])
def test_token_type_malformed_never_escapes(harness, value):
    auth, s, _, login, *_ = harness
    s['response'] = {'token_type': value}
    with pytest.raises(AuthError): login()


def test_callback_failure_visible_without_credentials(harness):
    auth, _, begin, _, *_ = harness
    with pytest.raises(AuthError):
        auth.complete(code='secret', state=begin(), error='access_denied')
    assert auth.status()['error']
    assert 'secret' not in json.dumps(auth.status())


def test_reauthorization_without_callback_client_id(harness):
    auth, s, begin, login, *_ = harness
    login()
    auth.complete(code='code-secret', state=begin())
    assert auth.status()['sharing']


def test_new_registration_parameters(harness):
    auth, s, begin, *_ = harness
    begin(); first = s['query']
    begin(); second = s['query']
    assert first['client_id'] == ['dynamic_agent_client']
    assert first['agent_name_hint'] == ['Nyaru Clipper']
    assert first['ext_agent_host_id'] == second['ext_agent_host_id']
    assert first['state'] != second['state'] and first['nonce'] != second['nonce']
    assert first['code_challenge'] != second['code_challenge']
    assert first['resource'] == ['https://api.openai.com/v1']


def test_failed_first_exchange_retains_issued_client_for_retry(harness):
    auth, s, begin, login, *_ = harness
    s['response'] = {'id_token': 'invalid'}
    with pytest.raises(AuthError): login()
    begin()
    assert s['query']['client_id'] == ['oaiapp_test']
    assert not auth.status()['connected']


def test_failed_exchange_issued_client_survives_restart(harness):
    auth, s, begin, login, root, client = harness
    s['response'] = {'id_token': 'invalid'}
    with pytest.raises(AuthError): login()
    other = ChatGPTAuth(root, client=client)
    query = parse_qs(urlsplit(other.begin('http://127.0.0.1:8787/auth/callback')).query)
    assert query['client_id'] == ['oaiapp_test']
    record = json.loads((root/'.chatgpt/credentials.json').read_text())
    assert record['pending_client_id'] == 'oaiapp_test'
    assert 'session' not in record and 'registration' not in record
    assert not other.status()['connected']


def test_close_only_owned_client(tmp_path):
    auth = ChatGPTAuth(tmp_path)
    auth.close()
    assert auth.client.is_closed
    external = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    other = ChatGPTAuth(tmp_path, client=external)
    other.close()
    assert not external.is_closed
    external.close()


def test_wrong_state_does_not_cancel_matching_callback(harness):
    auth, s, begin, _, *_ = harness
    state = begin()
    with pytest.raises(AuthError):
        auth.complete(code='unrelated-code', state='unrelated-state', client_id='oaiapp_test')
    assert not any(r.url.path.endswith('/oauth/token') for r in s['requests'])
    auth.complete(code='code-secret', state=state, client_id='oaiapp_test')
    assert auth.status()['connected'] and auth.status()['sharing']
    with pytest.raises(AuthError):
        auth.complete(code='code-secret', state=state, client_id='oaiapp_test')


@pytest.mark.parametrize('email', [123, [], {'secret': 'invalid'}])
def test_signed_invalid_email_preserves_verified_session(harness, email):
    auth, s, _, login, root, client = harness
    login()
    path = root/'.chatgpt/credentials.json'
    previous = path.read_bytes()
    s['claims']['email'] = email
    with pytest.raises(AuthError):
        login()
    assert path.read_bytes() == previous
    assert auth.status()['connected'] and auth.status()['sharing']
    assert auth.token().get_secret_value() == 'access-secret'
    restarted = ChatGPTAuth(root, client=client)
    assert restarted.status()['connected']
    assert restarted.token().get_secret_value() == 'access-secret'
