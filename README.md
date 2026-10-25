# Runrun.it CLI

Gerencie tarefas do Runrun.it pelo terminal, com comandos em português, saída legível e JSON para automações.

```bash
rr minhas
rr hoje
rr resumo --por prazo
rr ver 123456
```

A CLI usa a API oficial do Runrun.it. É escrita em Python e instalada como um pacote com comando de terminal; não é um programa compilado. O comando instalado funciona sem Bash no Windows. Não é um produto oficial do Runrun.it.

## O que você pode fazer

- Consultar tarefas abertas, buscar por título e filtrar prazos ou contadores ativos.
- Ver descrição, comentários, arquivos, subtarefas e dependências.
- Criar, entregar, reabrir, mover e editar tarefas.
- Gerenciar responsáveis, urgência, tags e checklists.
- Iniciar/pausar trabalho, registrar horas manuais e anexar arquivos.
- Usar `--json` para integrar com scripts e agentes.

## Instalação no Linux

Cole no terminal:

```sh
curl -fsSL https://raw.githubusercontent.com/hendrixfreire/runrunit-cli/main/install.sh | sh
```

O instalador obtém o `uv` se necessário, baixa um Python 3.12 gerenciado e instala o pacote completo em um ambiente isolado do seu usuário. Não precisa instalar Git ou clonar o repositório. Linux precisa de `sh` e `curl` ou `wget`; use `wget -qO- https://raw.githubusercontent.com/hendrixfreire/runrunit-cli/main/install.sh | sh` se só tiver wget.

## Instalação no Windows

Abra o **PowerShell** e cole:

```powershell
irm https://raw.githubusercontent.com/hendrixfreire/runrunit-cli/main/install.ps1 | iex
```

Instalação nativa do Windows: obtém o `uv`, o Python 3.12 gerenciado e o comando `rr.exe`. Não precisa de WSL, Bash, Git nem Python instalado previamente. O script não altera a política de execução global do Windows. Políticas corporativas que bloqueiam downloads ou execução devem ser tratadas com o administrador do ambiente.

## Instalação no macOS

Cole no Terminal:

```sh
curl -fsSL https://raw.githubusercontent.com/hendrixfreire/runrunit-cli/main/install.sh | sh
```

Não precisa de Homebrew, Git ou Python instalado previamente. O instalador usa um Python gerenciado pelo `uv` e mantém o Python do macOS separado.

## O que acontece na instalação

1. Instala o gerenciador `uv` no seu usuário, se ele não estiver disponível.
2. Obtém um Python gerenciado, instala a CLI e as dependências, incluindo os dados de fuso horário usados no Windows.
3. Disponibiliza `rr` no diretório de ferramentas do usuário e prepara o PATH. Pode ser necessário abrir outro terminal para o novo PATH ser reconhecido.
4. Em um terminal interativo, oferece a configuração das credenciais. A instalação pode ser concluída sem configurar uma conta.

O download da CLI vem deste repositório público; o `uv` vem do instalador oficial da Astral. Os comandos acima executam scripts baixados por HTTPS: você pode inspecionar [install.sh](install.sh) ou [install.ps1](install.ps1) antes de executar.

A instalação não inclui credenciais de ninguém. Você precisa de uma conta Runrun.it com acesso à API e permissões para as operações desejadas. O acesso depende das condições da sua conta; veja a [documentação oficial](https://runrun.it/api/documentation).

Se já houver um comando `rr` de outra instalação no destino, o instalador deve preservar esse arquivo e informar o conflito. A instalação antiga por clone/link continua disponível e não precisa ser substituída para você usar o projeto.

## Configurar sua conta

Se você pulou a configuração inicial, rode:

```text
rr configurar
```

O assistente pede App-Key e User-Token sem mostrar seus valores, valida o acesso e identifica seu usuário pela API. Só grava a configuração após a validação. Você não precisa descobrir seu ID manualmente nem editar o código.

A configuração fica fora do projeto e do ambiente instalado:

- **Linux/macOS:** `~/.config/runrunit-cli/env`.
- **Windows:** `%APPDATA%\runrunit-cli\env`.

Use suas próprias credenciais. O User-Token define em nome de quem a CLI atua. Mantenha esse arquivo local; não envie valores ao GitHub ou em mensagens.

Para uso avançado, a CLI aceita `RUNRUNIT_APP_KEY`, `RUNRUNIT_USER_TOKEN`, `RUNRUNIT_USER_ID` e `RUNRUNIT_UPLOAD_URL` no ambiente. `RUNRUNIT_ENV_FILE` seleciona um arquivo alternativo. A configuração antiga do Hermes continua como fallback para usuários existentes; Hermes não é necessário para instalar ou usar a CLI.

Depois de configurar:

```text
rr minhas
rr resumo --por projeto
```

## Uso diário

```bash
# Suas tarefas abertas e com assignment ativo
rr minhas

# Buscar texto no título dessas tarefas
rr buscar "Relatório"

# Prazos e contadores
rr hoje
rr atrasadas
rr trabalhando

# Panorama por projeto, prazo ou urgência
rr resumo --por projeto
rr resumo --por prazo
rr resumo --por urgencia

# Detalhes e colaboração; substitua 123456 por um ID real
rr ver 123456
rr comentarios 123456
rr arquivos 123456
rr subtarefas 123456
rr dependencias 123456
rr checklist 123456
rr abrir 123456
```

`buscar` procura somente no título das suas tarefas abertas atribuídas, sem distinguir maiúsculas; não é uma busca global. `hoje` e `atrasadas` consideram o dia do prazo em `America/Sao_Paulo`, e não o horário vencido dentro do dia atual. As consultas continuam sujeitas às permissões do usuário na API.

## Alterar tarefas com prévia e confirmação

Para revisar uma operação sem executá-la, use `--dry-run`:

```bash
rr prazo 123456 2026-12-15 --dry-run
rr editar 123456 --titulo "Título revisado" --dry-run
rr entregar 123456 --dry-run
rr comentar 123456 "Revisão concluída" --dry-run
```

Sem `--dry-run`, a CLI mostra a tarefa e a operação e pede que você digite o ID para confirmar:

```bash
rr prazo 123456 2026-12-15
rr iniciar 123456
rr pausar 123456
```

Em execução sem terminal interativo, é preciso passar a confirmação explicitamente, após revisar a operação:

```bash
rr prazo 123456 2026-12-15 --confirmar 123456
```

Para criar tarefa, consulte os IDs das referências e revise a proposta:

```bash
rr quadros
rr tipos
rr projetos
rr etapas --quadro 111
rr criar "Revisar relatório" --quadro 111 --tipo 222 --projeto 333 --dry-run
```

Os números acima são exemplos. Use IDs reais e válidos da sua conta. A criação usa a confirmação `CRIAR` no terminal ou `--confirmar CRIAR` em automação.

Mais exemplos:

```bash
rr reabrir 123456 --dry-run
rr mover 123456 --etapa 444 --dry-run
rr urgente 123456 --dry-run
rr atribuir 123456 --usuario outro-usuario --equipe 555 --dry-run
rr tags 123456 --adicionar revisao --dry-run
rr checklist 123456 --adicionar "Conferir totais" --dry-run
rr horas 123456 --duracao 1h30 --data 2026-12-15 --motivo "Revisão" --dry-run
rr anexar 123456 relatorio.md --dry-run
```

O checklist precisa existir antes de adicionar itens; crie com `rr checklist 123456 --criar "Validações"`. Veja todas as opções em [COMANDOS.md](COMANDOS.md) ou com `rr COMANDO --help`.

A CLI não repete escritas automaticamente. Após timeout ou divergência na verificação, consulte o estado antes de reenviar: a operação pode ter sido concluída. Editar título e descrição juntos envolve duas requisições e pode terminar parcialmente.

## JSON, paginação e automações

```bash
rr minhas --json
rr minhas --max-pages 20 --max-items 2000 --json
rr comentarios 123456 --json
```

Coleções usam, por padrão, no máximo 10 páginas e 1.000 itens. `truncated: true` indica resultado parcial; aumente os limites antes de tratar a lista ou o resumo como completo. O limite é aplicado aos itens recebidos da API antes dos filtros locais, portanto o total exibido pode ser menor.

JSON é escrito em stdout; prévias e diagnósticos usam stderr. Escritas exigem a confirmação mesmo com `--json`. Os comandos técnicos `request`, `task` e `paginate` continuam disponíveis, mas não possuem a confirmação interativa da interface em português: use-os com atenção, principalmente em alterações.

## Atualizar

Execute novamente o mesmo comando de instalação do seu sistema para atualizar a instalação gerenciada pelo `uv`, mantendo as credenciais separadas. Veja o resultado informado pelo instalador e confira:

```text
rr --help
```

Se você usa a instalação antiga por clone/link, continue atualizando a pasta com `git pull --ff-only` depois de revisar e guardar suas alterações locais. A instalação por pacote e a instalação de desenvolvimento por link são modalidades diferentes.

## Desinstalar

Para a instalação gerenciada pelo `uv`:

```text
uv tool uninstall runrunit-cli
```

Isso remove a ferramenta e seu ambiente isolado; suas credenciais permanecem no diretório de configuração. Remova-as separadamente se não quiser mais usá-las. O `uv` e o Python gerenciado podem ser usados por outras ferramentas e não são removidos por esse comando.

Para a instalação antiga por link, confira o destino de `~/.local/bin/rr` antes de remover o link e apagar o clone.

## Desenvolvimento e testes

Arquivos principais:

- `rr_entry.py`: ponto de entrada multiplataforma, configuração e assistente de credenciais.
- `pyproject.toml`: pacote instalável e dependências.
- `install.sh` / `install.ps1`: instaladores Linux/macOS e Windows.
- `rr`: wrapper compatível com a instalação antiga por clone/link.
- `rr_cli.py`: comandos em português.
- `runrunit_api.py`: cliente HTTP e comandos técnicos.
- `rr_upload.py`: envio multipart e conferência de anexos por SHA-256.
- `test_rr_cli.py` e `test_rr_extended.py`: testes com mocks, sem alterar tarefas reais.

Execute na raiz do projeto:

```bash
python -m pip install .
python -m unittest discover -s . -p 'test*.py'
```

Para contribuir, crie uma branch, implemente uma mudança coesa, rode os testes e abra um pull request. Nunca inclua arquivos de credenciais ou respostas reais com dados privados em fixtures.

## Problemas comuns

- **`rr: command not found`**: confira o link e o PATH; tente `./rr --help` na pasta do projeto.
- **Falha no download de uv/Python/pacote**: confira conexão, proxy e as restrições do ambiente; a instalação precisa acessar GitHub e os servidores de distribuição do uv/Python.
- **`python3` ausente na instalação antiga por link**: essa modalidade exige Python disponível no PATH. A instalação por pacote obtém seu próprio Python gerenciado.
- **Credenciais ausentes / HTTP 401**: execute `rr configurar` ou confira a configuração avançada, sem imprimir seus valores.
- **HTTP 403**: a conta pode não ter permissão para a operação ou recurso.
- **HTTP 404**: confira o ID e o acesso ao recurso. A consulta de checklist ausente é tratada como `body: null`.
- **Tarefas de outro usuário ou lista vazia inesperada**: execute `rr configurar` para identificar sua conta, ou configure `RUNRUNIT_USER_ID` / `--usuario ID` explicitamente.
- **HTTP 429**: aguarde o período indicado pela API; novas tentativas imediatas não resolvem o limite.
- **Upload interrompido**: reconcilie o ID do documento informado antes de reenviar; o registro pode ter sido criado mesmo sem upload completo.

## Limitações e validação

Os instaladores instalam um pacote Python com runtime gerenciado; não geram um binário independente. Não há pacote publicado no PyPI: a instalação baixa o código diretamente do GitHub.

Testes locais simulam escritas e storage, sem alterar tarefas reais. A automação deste repositório testa pacote, comandos e instaladores em Linux, macOS e Windows; consulte o [resultado dos testes](https://github.com/hendrixfreire/runrunit-cli/actions) para o estado atual. Políticas de rede e particularidades de cada PC podem afetar a instalação.

O destino padrão de upload segue o exemplo oficial e pode exigir atualização se o provedor mudar; consulte `COMANDOS.md` para configuração.

## Referências

- [API oficial do Runrun.it](https://runrun.it/api/documentation)
- [Exemplos oficiais de upload](https://github.com/Runrunit/api_examples)
- [Referência completa dos comandos](COMANDOS.md)
