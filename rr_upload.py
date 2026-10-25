"""Upload multipart e conferência por SHA-256, usando somente stdlib."""
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid
import runrunit_api as api

# Destino vigente no exemplo oficial (Oracle), conferido em 23/10/2026:
# https://github.com/Runrunit/api_examples/blob/main/upload_file_to_task.py
DEFAULT_UPLOAD_URL = 'https://gryvnagsfedj.compat.objectstorage.sa-saopaulo-1.oraclecloud.com/runrunit'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def https_url(url):
    p = urlparse(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password:
        raise SystemExit('URL de storage inválida: é necessário HTTPS sem credenciais na URL.')
    return url


def digest(stream):
    h = hashlib.sha256()
    while chunk := stream.read(1024 * 1024): h.update(chunk)
    return h.hexdigest()


def download_hash(document_id):
    url = api.BASE_URL + '/documents/' + api.safe_id(str(document_id)) + '/download'
    app_key, token = api.credentials()
    headers = {'App-Key': app_key, 'User-Token': token}
    opener = build_opener(NoRedirect())
    for _ in range(6):
        try:
            with opener.open(Request(https_url(url), headers=headers), timeout=60) as response:
                return digest(response)
        except HTTPError as exc:
            if exc.code not in (301, 302, 303, 307, 308) or not exc.headers.get('Location'):
                raise SystemExit(f'Falha ao conferir download: HTTP {exc.code}.') from None
            url = https_url(urljoin(url, exc.headers['Location']))
            # Nunca encaminhar as credenciais do Runrun.it para o storage.
            headers = {}
        except URLError:
            raise SystemExit('Falha de rede ao conferir o download; reconcilie o documento antes de repetir.') from None
    raise SystemExit('Redirecionamentos demais ao conferir download.')


def multipart(fields, name, source):
    boundary = 'rr-' + uuid.uuid4().hex
    body = tempfile.TemporaryFile()
    for key, value in fields.items():
        if not re.fullmatch(r'[\w.-]+', key): raise SystemExit('Nome de campo multipart inválido.')
        body.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    safe_name = name.replace('"', '_').replace('\r', '_').replace('\n', '_').replace('\\', '_')
    content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
    body.write(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{safe_name}"\r\nContent-Type: {content_type}\r\n\r\n'.encode())
    shutil.copyfileobj(source, body)
    body.write(f'\r\n--{boundary}--\r\n'.encode())
    size = body.tell(); body.seek(0)
    return body, boundary, size


def attach(args, task, confirm, preview, checked):
    path = args.arquivo.expanduser().resolve()
    if not path.is_file(): raise SystemExit('Arquivo local não encontrado.')
    # Congela bytes usados na prévia e no upload para evitar mudanças concorrentes.
    with path.open('rb') as source, tempfile.TemporaryFile() as snapshot:
        shutil.copyfileobj(source, snapshot)
        size = snapshot.tell(); snapshot.seek(0); sha = digest(snapshot); snapshot.seek(0)
        plan = {'task_id': args.id, 'file_name': path.name, 'file_size': size, 'sha256': sha,
                'steps': ['criar documento', 'upload multipart', 'mark_as_uploaded', 'download e SHA-256']}
        if not confirm(args, task, plan): return preview(plan)
        document_id = None
        try:
            created = api.call('POST', f'/documents?task_id={args.id}', {'document': {
                'data_file_name': path.name, 'data_file_size': size, 'warning_duplicate': True}})['body']
            document_id = api.safe_id(str(created['id']))
            fields = created['fields']
            # Use destino retornado quando disponível, com fallback ao exemplo oficial atual.
            url = https_url(created.get('upload_url') or created.get('action_url') or os.environ.get('RUNRUNIT_UPLOAD_URL') or DEFAULT_UPLOAD_URL)
            body, boundary, length = multipart(fields, path.name, snapshot)
            with body:
                req = Request(url, data=body, headers={
                    'Content-Type': 'multipart/form-data; boundary=' + boundary,
                    'Content-Length': str(length)}, method='POST')
                with build_opener(NoRedirect()).open(req, timeout=120) as response:
                    if response.status not in (200, 201, 204): raise SystemExit('Storage recusou upload.')
            api.call('POST', f'/documents/{document_id}/mark_as_uploaded')
            result = api.call('GET', f'/documents/{document_id}')
            b = result['body']
            checked(result, b.get('transfered') is True and str(b.get('attachable_id')) == args.id and b.get('file_size', b.get('data_file_size')) == size)
            remote_sha = download_hash(document_id)
            checked(result, remote_sha == sha)
            result['sha256'] = sha
            return result
        except (SystemExit, OSError, KeyError, TypeError, ValueError) as exc:
            print(f'Upload interrompido; documento={document_id or "não confirmado"}. Reconcilie antes de reenviar; nenhuma repetição automática.', file=sys.stderr)
            if isinstance(exc, (HTTPError, URLError)):
                raise SystemExit('Falha no storage ou na rede; detalhes de assinatura omitidos.') from None
            raise
