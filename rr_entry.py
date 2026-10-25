"""Entrypoint Python multiplataforma e configuração local da CLI."""
import argparse
import contextlib
import getpass
import io
import json
import os
from pathlib import Path
import sys
import tempfile

KEYS = ('RUNRUNIT_APP_KEY', 'RUNRUNIT_USER_TOKEN', 'RUNRUNIT_USER_ID', 'RUNRUNIT_UPLOAD_URL')


def default_config_path():
    if os.name == 'nt':
        appdata = os.environ.get('APPDATA')
        base = Path(appdata) if appdata else Path.home() / 'AppData' / 'Roaming'
        return base / 'runrunit-cli' / 'env'
    return Path.home() / '.config' / 'runrunit-cli' / 'env'


def config_path():
    return Path(os.environ['RUNRUNIT_ENV_FILE']).expanduser() if os.environ.get('RUNRUNIT_ENV_FILE') else default_config_path()


def parse_config(text):
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'): continue
        if line.startswith('export '): line = line[7:]
        key, sep, value = line.partition('=')
        if sep and key.strip() in KEYS:
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                try: value = json.loads(value)
                except json.JSONDecodeError: value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"): value = value[1:-1]
            values[key.strip()] = value
    return values


def load_config():
    selected = config_path()
    if not os.environ.get('RUNRUNIT_ENV_FILE') and not selected.is_file():
        selected = Path.home() / '.hermes' / 'profiles' / 'profissional' / '.env'
    if selected.is_file():
        for key, value in parse_config(selected.read_text(encoding='utf-8-sig')).items():
            if not os.environ.get(key): os.environ[key] = value


def write_config(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replace keeps the previous file intact if validation/write fails.
    fd, temporary = tempfile.mkstemp(prefix='.rr-config-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            for key in KEYS:
                if values.get(key): stream.write(f'{key}={json.dumps(values[key], ensure_ascii=False)}\n')
        if os.name != 'nt': os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def configure(argv):
    p = argparse.ArgumentParser(prog='rr configurar', description='Configurar suas credenciais locais do Runrun.it sem exibi-las.')
    p.parse_args(argv)
    if not sys.stdin.isatty(): raise SystemExit('Configuração exige terminal interativo. Execute rr configurar em um terminal.')
    path = config_path()
    if path.exists() and input(f'Já existe configuração em {path}. Substituir? [s/N] ').strip().lower() != 's':
        print('Configuração preservada.'); return
    print('Informe suas credenciais da integração/API do Runrun.it. A entrada fica oculta.')
    key = getpass.getpass('App-Key: ').strip()
    token = getpass.getpass('User-Token: ').strip()
    if not key or not token: raise SystemExit('Credenciais vazias; configuração não alterada.')
    import runrunit_api as api
    previous = {k: os.environ.get(k) for k in ('RUNRUNIT_APP_KEY', 'RUNRUNIT_USER_TOKEN')}
    os.environ.update(RUNRUNIT_APP_KEY=key, RUNRUNIT_USER_TOKEN=token)
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            result = api.call('GET', '/users?me_first=true&limit=1')
        body = result['body']
        if result['status'] != 200 or not isinstance(body, list) or not body or not body[0].get('id'):
            raise ValueError('Resposta sem usuário')
        user_id = api.safe_id(str(body[0]['id']))
    except (SystemExit, OSError, ValueError, KeyError, TypeError):
        raise SystemExit('Não foi possível validar as credenciais e identificar o usuário. Configuração anterior preservada; confira o acesso à API e tente novamente.') from None
    finally:
        for k, value in previous.items():
            if value is None: os.environ.pop(k, None)
            else: os.environ[k] = value
    values = {'RUNRUNIT_APP_KEY': key, 'RUNRUNIT_USER_TOKEN': token, 'RUNRUNIT_USER_ID': user_id}
    if os.environ.get('RUNRUNIT_UPLOAD_URL'): values['RUNRUNIT_UPLOAD_URL'] = os.environ['RUNRUNIT_UPLOAD_URL']
    write_config(path, values)
    print(f'Configuração validada e salva em {path}. Agora execute rr minhas.')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    load_config()
    if argv and argv[0] == 'configurar': return configure(argv[1:])
    if '--version' in argv:
        from importlib.metadata import version, PackageNotFoundError
        try: value = version('runrunit-cli')
        except PackageNotFoundError: value = '0.2.0 (código-fonte)'
        print(value); return
    if argv in (['--help'], ['-h']):
        print('Configuração: rr configurar | Versão: rr --version\n')
    import rr_cli
    # The legacy API parser consumes sys.argv directly.
    previous = sys.argv
    try:
        sys.argv = ['rr', *argv]
        rr_cli.main(argv)
    finally:
        sys.argv = previous


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f'Erro local: {type(exc).__name__}. Confira configuração e permissões; se houve escrita, reconcilie antes de repetir.') from None
