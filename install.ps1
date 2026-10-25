param(
    [string]$Source = 'https://github.com/hendrixfreire/runrunit-cli/archive/refs/heads/main.zip',
    [switch]$NoConfig,
    [switch]$Replace
)
$ErrorActionPreference = 'Stop'
# TLS para Windows PowerShell 5.1. Não altera políticas de execução.
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
function Invoke-Uv {
    param([string[]]$Arguments)
    & $script:UvPath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "uv falhou (código $LASTEXITCODE). Nenhuma confirmação de sucesso emitida." }
}
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCommand) {
    $script:UvPath = $uvCommand.Source
} else {
    $installer = Invoke-RestMethod 'https://astral.sh/uv/install.ps1'
    & ([scriptblock]::Create($installer))
    $script:UvPath = Join-Path $HOME '.local\bin\uv.exe'
    if (-not (Test-Path -LiteralPath $script:UvPath)) {
        throw 'uv não foi encontrado no diretório padrão. Abra outro terminal e execute novamente.'
    }
}
$installArgs = @('tool', 'install', '--reinstall', '--python', '3.12', '--managed-python')
if ($Replace) { $installArgs += '--force' }
$installArgs += $Source
Invoke-Uv -Arguments $installArgs
$binDir = (Invoke-Uv -Arguments @('tool', 'dir', '--bin') | Out-String).Trim()
$rr = Join-Path $binDir 'rr.exe'
if (-not (Test-Path -LiteralPath $rr)) { throw 'A instalação não criou rr.exe.' }
try { Invoke-Uv -Arguments @('tool', 'update-shell') } catch {
    Write-Warning "Não foi possível atualizar o PATH do shell automaticamente (ou ele já está configurado). O comando instalado está em $rr."
}
$env:PATH = "$binDir;$env:PATH"
& $rr --version
if ($LASTEXITCODE -ne 0) { throw 'Falha ao validar rr --version.' }
& $rr --help
if ($LASTEXITCODE -ne 0) { throw 'Falha ao validar rr --help.' }
Write-Host 'CLI instalada. Abra outro terminal para usar rr pelo PATH.'
if (-not $NoConfig) {
    if ([Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
        & $rr configurar
        if ($LASTEXITCODE -ne 0) { throw 'CLI instalada, mas a configuração não foi concluída. Execute rr configurar para tentar novamente.' }
    } else {
        Write-Host 'Sem terminal interativo: configure depois com rr configurar.'
    }
}
