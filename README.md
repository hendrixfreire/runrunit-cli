# Runrun.it CLI

CLI em português para gerenciar tarefas do Runrun.it. O código-fonte é mantido neste repositório; o comando `~/.local/bin/rr` é um link para `rr` daqui.

## Executar

Requer Python 3.10+ e Bash, com `realpath` disponível no sistema.

```bash
./rr --help
./rr minhas
./rr resumo --por prazo
```

A instalação local existente mantém as credenciais fora deste repositório. O wrapper usa `RUNRUNIT_APP_KEY` e `RUNRUNIT_USER_TOKEN` do ambiente ou lê a configuração existente em `~/.hermes/profiles/profissional/.env`. `RUNRUNIT_ENV_FILE` permite indicar outro arquivo local. Nunca adicione esse arquivo ou os valores das credenciais ao Git. Para outro usuário, configure seu próprio par de credenciais e use `--usuario ID` nos comandos de listagem, ou `RUNRUNIT_USER_ID`.

## Estrutura

- `rr`: executável e carregamento da configuração local.
- `rr_cli.py`: comandos em português.
- `runrunit_api.py`: cliente HTTP e comandos técnicos.
- `rr_upload.py`: envio e conferência de anexos.
- `test_rr_cli.py` e `test_rr_extended.py`: testes locais com mocks.
- [COMANDOS.md](COMANDOS.md): sintaxe de consultas e alterações.

## Testar

```bash
python3 -m unittest discover -s . -p 'test_rr*.py'
```

Escritas têm prévia e confirmação. Use `--dry-run` para revisar sem alterar tarefas. Os testes simulam escritas e storage.

## Desenvolver e versionar

Edite os arquivos deste diretório, execute os testes e registre cada mudança coesa em um commit. Na instalação local por link, as alterações entram em uso na próxima execução de `rr`.

Este projeto foi separado da instalação anterior sem mudar o comportamento da CLI. Os caminhos antigos em `~/.claude/skills/runrunit-api/scripts/` permanecem como links de compatibilidade para os arquivos daqui.

O repositório é local: não há publicação no GitHub, pacote PyPI ou release. Distribuição por pacote e suporte validado em outros sistemas operacionais são etapas futuras.
