$raizProjeto = Split-Path -Parent $PSScriptRoot
Push-Location $raizProjeto

try {
$ErrorActionPreference = "Stop"

$pythonApp = $env:CHAMADOFLOW_PYTHON
if (-not $pythonApp) {
    $pythonApp = ".\.venv\Scripts\python.exe"
}

if (-not (Test-Path -LiteralPath $pythonApp)) {
    throw "Python não encontrado. Crie o ambiente .venv ou defina CHAMADOFLOW_PYTHON."
}

$versaoApp = & $pythonApp -c "from versao import VERSAO; print(VERSAO)"
$nomeRelease = "ChamadoFlow-v$versaoApp"
$pastaRelease = Join-Path "release" $nomeRelease
$arquivoZip = Join-Path "release" "$nomeRelease.zip"
$arquivoZipSemExtensao = Join-Path "release" $nomeRelease
$pastaDistTemporaria = ".release-build-dist"
$pastaWorkTemporaria = ".release-build-work"
$pastaSpecTemporaria = ".release-build-spec"

if ((Test-Path -LiteralPath $pastaRelease) -or (Test-Path -LiteralPath $arquivoZip)) {
    throw "A release $nomeRelease já existe. Atualize a versão em versao.py antes de gerar outra."
}

try {
    & $pythonApp -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --onedir `
        --name ChamadoFlow `
        --collect-data tzdata `
        --distpath $pastaDistTemporaria `
        --workpath $pastaWorkTemporaria `
        --specpath $pastaSpecTemporaria `
        main.py

    if ($LASTEXITCODE -ne 0) {
        throw "O empacotamento falhou."
    }

    New-Item -ItemType Directory -Path $pastaRelease | Out-Null
    Copy-Item -LiteralPath "$pastaDistTemporaria\ChamadoFlow\ChamadoFlow.exe" -Destination $pastaRelease
    Copy-Item -LiteralPath "$pastaDistTemporaria\ChamadoFlow\_internal" -Destination $pastaRelease -Recurse
    Copy-Item -LiteralPath "config.example.json" -Destination $pastaRelease
    Copy-Item -LiteralPath "README.md" -Destination $pastaRelease
    Set-Content -LiteralPath (Join-Path $pastaRelease "VERSAO.txt") -Value $versaoApp -Encoding utf8

    & $pythonApp -c "import shutil; shutil.make_archive(r'$arquivoZipSemExtensao', 'zip', root_dir='release', base_dir=r'$nomeRelease')"
    if ($LASTEXITCODE -ne 0) {
        throw "Não foi possível compactar a release."
    }

    Write-Host "Release gerada em: $arquivoZip"
}
finally {
    @($pastaDistTemporaria, $pastaWorkTemporaria, $pastaSpecTemporaria) |
        Where-Object { Test-Path -LiteralPath $_ } |
        ForEach-Object { Remove-Item -LiteralPath $_ -Recurse -Force }
}
}
finally {
    Pop-Location
}
