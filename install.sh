#!/bin/sh
# Instala no perfil do usuário; não requer Git, Python prévio ou sudo.
set -eu
source_url='https://github.com/hendrixfreire/runrunit-cli/archive/refs/heads/main.zip'
configure=1
replace=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --source) [ "$#" -ge 2 ] || { echo 'Falta valor para --source.' >&2; exit 2; }; source_url=$2; shift 2 ;;
        --no-config) configure=0; shift ;;
        --replace) replace=1; shift ;;
        -h|--help) echo 'Uso: sh install.sh [--source URL_OU_DIRETORIO] [--no-config] [--replace]'; exit 0 ;;
        *) echo "Opção desconhecida: $1" >&2; exit 2 ;;
    esac
done
case "$(uname -s)" in Linux|Darwin) ;; *) echo 'Use install.ps1 no Windows.' >&2; exit 1 ;; esac
# uv instala seu próprio Python gerenciado quando necessário.
if command -v uv >/dev/null 2>&1; then
    uv_bin=$(command -v uv)
else
    temp_file=$(mktemp)
    trap 'rm -f "$temp_file"' EXIT HUP INT TERM
    if command -v curl >/dev/null 2>&1; then
        curl --fail --silent --show-error --location --proto '=https' https://astral.sh/uv/install.sh -o "$temp_file"
    elif command -v wget >/dev/null 2>&1; then
        wget -q https://astral.sh/uv/install.sh -O "$temp_file"
    else
        echo 'É necessário curl ou wget para obter o instalador do uv.' >&2; exit 1
    fi
    sh "$temp_file"
    uv_bin="$HOME/.local/bin/uv"
    if [ ! -x "$uv_bin" ]; then
        echo 'uv foi instalado em um diretório personalizado. Abra outro terminal e execute novamente.' >&2; exit 1
    fi
fi
# A instalação normal não sobrescreve rr de outro programa ou um link existente.
if [ "$replace" -eq 1 ]; then
    "$uv_bin" tool install --reinstall --force --python 3.12 --managed-python "$source_url"
else
    "$uv_bin" tool install --reinstall --python 3.12 --managed-python "$source_url"
fi
bin_dir=$("$uv_bin" tool dir --bin)
rr_bin="$bin_dir/rr"
[ -x "$rr_bin" ] || { echo 'Instalação não criou o comando rr.' >&2; exit 1; }
if ! "$uv_bin" tool update-shell; then
    echo "Aviso: não foi possível atualizar o PATH do shell automaticamente (ou ele já está configurado). O comando instalado está em $rr_bin." >&2
fi
export PATH="$bin_dir:$PATH"
"$rr_bin" --version
"$rr_bin" --help
printf '\nCLI instalada. Abra outro terminal para usar rr pelo PATH.\n'
if [ "$configure" -eq 1 ]; then
    if [ -t 0 ]; then
        "$rr_bin" configurar
    elif ( : </dev/tty ) 2>/dev/null; then
        "$rr_bin" configurar </dev/tty
    else
        echo 'Sem terminal interativo: configure depois com rr configurar.'
    fi
fi
