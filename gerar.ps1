<#
.SYNOPSIS
  Gera e compila o port a partir da SUA cópia do jogo (imagem .iso do DVD de PS2).
  As ferramentas vêm no motor (bin\otx_ferramentas.exe): extração da ISO, mapa HLE, CSV, tabela de funções, VU1
  e o lançador do clang-cl no build. Não precisa de Python nem de Git. Como a extração usa o exe do motor, o motor
  (etapa 3) é baixado antes da extração (etapa 2); a ISO é escolhida antes dos dois.

.DESCRIPTION
  Faz tudo em ordem, e cada etapa pula se já foi feita (use -Refazer para refazer tudo,
  ou -RefazerDe N para refazer da etapa N em diante):
    1. confere as ferramentas (Visual Studio Build Tools com C++ e CMake);
    2. confere a sua ISO e extrai os arquivos do disco para trabalho\disc;
    3. baixa o motor do port (pacote pronto do motor PS2 Otavix, conferido pelo SHA-256);
    4. traduz o código do jogo (MIPS R5900 -> C++);
    5. traduz os microprogramas de geometria (VU1) do executável do seu disco para C++;
    6. compila o jogo (só o código traduzido: o motor já vem compilado);
    7. deixa o jogar.cmd pronto.
  Os logs de cada etapa ficam em out\gerar\. Nada do jogo vem neste repositório: só o
  mapa de funções (endereços), as configurações da tradução e a "receita" do VU1 (onde os
  microprogramas ficam no executável: offsets e tamanhos, nunca os bytes).

.PARAMETER Iso
  A imagem .iso do DVD (a versão indicada no README). Sem ela, abre uma janela
  para escolher o arquivo.
.PARAMETER Jobs
  Compilações em paralelo (padrão: pela memória livre, ~3 GB por compilação).
.PARAMETER RefazerDe
  Refaz da etapa N em diante. Depois de atualizar o port, -RefazerDe 3 baixa o motor novo,
  retraduz e recompila sem extrair o disco de novo.
.PARAMETER Pacote
  (testes) o .zip do motor já baixado: a etapa 3 usa ele em vez de baixar. O SHA-256 é
  conferido do mesmo jeito (ou pelo <zip>.sha256 ao lado, para um motor ainda não publicado).
.EXAMPLE
  gerar.cmd     (clique duas vezes: pede a ISO numa janela)
.EXAMPLE
  .\gerar.ps1 -Iso "D:\ISOs\meu jogo.iso"
#>
param(
    [string]$Iso = '',
    [int]$Jobs = 0,
    [int]$RefazerDe = 0,
    [switch]$Refazer,
    [string]$Pacote = ''
)
$ErrorActionPreference = 'Stop'
$R = $PSScriptRoot
if ($R -match ' ') { throw "Coloque o projeto numa pasta sem espaços (agora: $R)" }
$JOGO = Get-Content -Raw -Encoding UTF8 (Join-Path $R 'jogo\jogo.json') | ConvertFrom-Json

# motor do port: pacote fechado (tradutor, bibliotecas do runtime, cabeçalhos e o build do jogo), um por versão
$MOTOR_VERSAO = '0.1.9'
$MOTOR_NOME = "otx-motor-ps2-$MOTOR_VERSAO"
$MOTOR_URL = "https://github.com/otavix010/otx-motor-ps2/releases/download/v$MOTOR_VERSAO/$MOTOR_NOME.zip"
# cópia no servidor do launcher (o mesmo arquivo; vem primeiro, o GitHub fica de reserva)
$MOTOR_ESPELHO = "https://otavix-launcher.otavix-launcher-servidor.workers.dev/v1/arquivos/motor/ps2/$MOTOR_NOME.zip"
$MOTOR_SHA256 = '974b172fcc3124a09805625a5b23efb6a2573d228391324f98ffe5f617701a3c'

$T = Join-Path $R 'trabalho'
$OUT = Join-Path $R 'out\gerar'
$PAC = Join-Path $R "motor\$MOTOR_NOME"   # o pacote aberto
$C = Join-Path $R 'codigo'                # o código do jogo (traduzido aqui) + o build
New-Item -ItemType Directory -Force $OUT, $T | Out-Null
function Tira-Marcas([int]$de) {
    Get-ChildItem $OUT -Filter '*.ok' | Where-Object { $_.Name -match '^\d+_' -and [int]($_.Name.Split('_')[0]) -ge $de } | Remove-Item -Force
}
if ($RefazerDe -gt 0) { Tira-Marcas $RefazerDe }

function Msg($t) { Write-Host "[gerar] $t" -ForegroundColor Cyan }
# roda um programa externo sem que o stderr dele vire exceção (Windows PowerShell 5.1 com
# ErrorActionPreference = Stop); quem chama confere o $LASTEXITCODE
function SemExcecao([scriptblock]$bloco) {
    $eap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $bloco } finally { $ErrorActionPreference = $eap }
}
# escreve no log da etapa (-Novo: do zero), compartilhando o arquivo com quem estiver lendo
# (o launcher acompanha o progresso por ele)
function Anotar([string]$arq, [string]$texto, [switch]$Novo) {
    $b = [Text.Encoding]::UTF8.GetBytes("$texto`r`n")
    for ($i = 0; ; $i++) {
        try {
            $fs = New-Object IO.FileStream($arq, $(if ($Novo) { 'Create' } else { 'Append' }), 'Write', 'ReadWrite')
            try { $fs.Write($b, 0, $b.Length) } finally { $fs.Dispose() }
            return
        } catch [IO.IOException] {
            if ($i -ge 50) { throw }
            Start-Sleep -Milliseconds 100
        }
    }
}
# roda um comando pelo cmd (stdout e stderr no log da etapa); falha = exceção com o fim do log
function Exec([string]$log, [string]$linha) {
    Anotar $log "`r`n> $linha"
    cmd /d /c "$linha >> `"$log`" 2>&1"
    if ($LASTEXITCODE -ne 0) {
        Write-Host (Get-Content $log -Tail 25 | Out-String) -ForegroundColor DarkGray
        throw "falhou (código $LASTEXITCODE): $linha`r`nlog completo: $log"
    }
}
function Etapa([string]$nome, [scriptblock]$corpo) {
    $marca = Join-Path $OUT "$nome.ok"
    if ((Test-Path $marca) -and -not $Refazer) { Msg "${nome}: já feita (pulando)"; return }
    $script:LOG = Join-Path $OUT "$nome.log"
    Anotar $script:LOG "== $nome $(Get-Date)" -Novo
    Msg "$nome ..."
    $t0 = Get-Date
    & $corpo
    Set-Content -Path $marca -Value (Get-Date) -Encoding UTF8
    Msg ("{0}: ok ({1:N0} s)" -f $nome, ((Get-Date) - $t0).TotalSeconds)
}
function Sha1([string]$arq) {
    $r = Get-FileHash -Algorithm SHA1 -LiteralPath $arq -ErrorAction SilentlyContinue
    if (-not $r) { throw "não consegui ler `"$arq`" (aberto em outro programa, ainda baixando ou só na nuvem, sem cópia local?)" }
    $r.Hash.ToLower()
}
function Sha256([string]$arq) { (Get-FileHash -Algorithm SHA256 -LiteralPath $arq).Hash.ToLower() }

# geração antiga (até a 0.4.x: PS2Recomp clonado e compilado aqui) ou motor de outra versão: refaz da etapa 3
# (o disco já extraído continua valendo)
if (-not (Test-Path -LiteralPath (Join-Path $PAC 'VERSAO.txt'))) {
    if (Get-ChildItem $OUT -Filter '*.ok' | Where-Object { $_.Name -match '^[3-7]_' }) {
        Msg "motor novo ($MOTOR_NOME): refazendo da etapa 3 (o disco extraído continua valendo)"
    }
    Tira-Marcas 3
    Remove-Item (Join-Path $OUT '3_ps2recomp.log') -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------- ferramentas
function Achar-VS {
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path $vswhere)) { return $null }
    $p = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 Microsoft.VisualStudio.Component.VC.CMake.Project -property installationPath
    if ($p) { return ($p | Select-Object -First 1) }
    return $null
}
Etapa '1_ferramentas' {
    $falta = @()
    $vs = Achar-VS
    if (-not $vs) {
        $falta += 'Visual Studio 2022 Build Tools com C++ e "C++ CMake tools":' +
                  "`r`n    winget install Microsoft.VisualStudio.2022.BuildTools --override `"--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.CMake.Project --add Microsoft.VisualStudio.Component.VC.Llvm.Clang --includeRecommended`""
    }
    if ($falta) { throw ("Falta instalar:`r`n  - " + ($falta -join "`r`n  - ")) }
    Anotar $LOG "Visual Studio em $vs"
    # opcional: com o clang-cl do Visual Studio a geometria (VU1) compila com ele e roda um pouco mais rápido
    if (Test-Path (Join-Path $vs 'VC\Tools\Llvm\x64\bin\clang-cl.exe')) { Anotar $LOG 'clang-cl: sim' }
    else { Msg 'sem o "C++ Clang tools" do Visual Studio: a geometria compila com o MSVC (funciona igual, um pouco mais lenta)' }
}
$VS = Achar-VS
if (-not $VS) { throw 'Visual Studio Build Tools com C++ e CMake não encontrado (rode de novo a etapa 1: -RefazerDe 1)' }
# entradas do PATH entre aspas (ex.: "C:\Program Files (x86)\...") quebram o vcvars64.bat
# com "\Microsoft foi inesperado neste momento" (report 967): tira as aspas
$env:PATH = ($env:PATH -split ';' | ForEach-Object { $_.Trim().Trim('"') } | Where-Object { $_ }) -join ';'
# o vcvars64.bat procura o vswhere.exe no PATH
$env:PATH = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer;" + $env:PATH
$VCVARS = Join-Path $VS 'VC\Auxiliary\Build\vcvars64.bat'
# temporários do compilador na pasta do projeto (o C++ traduzido gera arquivos grandes)
$TMPC = Join-Path $R 'out\tmp'
New-Item -ItemType Directory -Force $TMPC | Out-Null
function ComVS([string]$linha) { "call `"$VCVARS`" >nul && set `"TEMP=$TMPC`" && set `"TMP=$TMPC`" && $linha" }
# sem o Windows SDK o CMake falha em "Detecting C compiler ABI" (RC Pass 1 failed, CMAKE_MT-NOTFOUND): avisa antes
SemExcecao { cmd /d /c (ComVS 'where rc.exe mt.exe') *> $null }
if ($LASTEXITCODE -ne 0) { throw 'falta o Windows SDK (rc.exe/mt.exe) no Visual Studio Build Tools. Abra o Visual Studio Installer > Modificar > marque "SDK do Windows 11" (ou 10) e gere de novo.' }

# ---------------------------------------------------------------------------- disco
function Escolher-Iso([string]$texto) {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $d = New-Object System.Windows.Forms.OpenFileDialog
        $d.Title = $texto
        $d.Filter = 'Imagem de DVD (*.iso)|*.iso|Todos os arquivos (*.*)|*.*'
        if ($d.ShowDialog() -eq 'OK') { return $d.FileName }
        return ''
    } catch { return (Read-Host $texto) }
}
$ELF = Join-Path $T ('disc\' + $JOGO.elf)
# a extração (etapa 2) usa o otx_ferramentas.exe, que vem no motor: o motor (etapa 3) é baixado antes dela. A ISO é
# escolhida já aqui, antes do download (ninguém espera o motor baixar para ver a janela da ISO).
if (-not $Iso -and ($Refazer -or -not (Test-Path (Join-Path $OUT '2_disco.ok')))) {
    $Iso = Escolher-Iso "Escolha a ISO do $($JOGO.nome) ($($JOGO.versao))"
    if (-not $Iso) { throw 'sem a ISO do jogo' }
}

# ---------------------------------------------------------------------------- motor
# baixa um arquivo (curl.exe do Windows; senão Invoke-WebRequest), por um .part, com o tamanho baixado no log da
# etapa a cada 3 s (é a linha que o launcher mostra)
function Curl-Com-Progresso([string]$exe, [string]$url, [string]$part, [string]$extra) {
    $si = New-Object Diagnostics.ProcessStartInfo
    $si.FileName = $exe
    $si.Arguments = "-L --fail --retry 3 --silent --show-error $extra -o `"$part`" `"$url`""
    $si.UseShellExecute = $false; $si.CreateNoWindow = $true; $si.RedirectStandardError = $true
    $p = [Diagnostics.Process]::Start($si)
    $err = $p.StandardError.ReadToEndAsync()
    $nome = Split-Path -Leaf ($part -replace '\.part$', '')
    $ultimo = -1
    while (-not $p.WaitForExit(3000)) {
        $mb = 0; try { $mb = [int]((Get-Item -LiteralPath $part -ErrorAction Stop).Length / 1MB) } catch { }
        if ($mb -ne $ultimo) {
            $ultimo = $mb
            if ($script:LOG) { Anotar $script:LOG "baixando $nome... $mb MB" }
        }
    }
    $p.WaitForExit()
    $e = $err.Result
    if ($e -and $script:LOG) { Anotar $script:LOG $e.Trim() }
    return $p.ExitCode
}
function Baixar([string]$url, [string]$destino) {
    New-Item -ItemType Directory -Force (Split-Path $destino) | Out-Null
    $part = "$destino.part"
    Remove-Item $part -ErrorAction SilentlyContinue
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    $erroCurl = $null
    if ($curl) {
        # antivírus ou política do Windows podem barrar o curl.exe: aí vai pelo próprio PowerShell, abaixo
        try {
            $cod = Curl-Com-Progresso $curl.Source $url $part ''
            # curl 35 (CRYPT_E_NO_REVOCATION_CHECK): a rede ou o antivírus não deixa consultar a revogação do
            # certificado; de novo sem essa consulta (o certificado continua conferido)
            if ($cod -eq 35) { $cod = Curl-Com-Progresso $curl.Source $url $part '--ssl-no-revoke' }
            if ($cod -ne 0) { $erroCurl = "curl $cod" }
        } catch {
            $erroCurl = "o curl.exe não pôde rodar: $($_.Exception.Message)"
        }
    }
    if (-not $curl -or $erroCurl) {
        if ($erroCurl) { Msg "download pelo curl falhou ($erroCurl); tentando pelo PowerShell" }
        Remove-Item $part -ErrorAction SilentlyContinue
        $ProgressPreference = 'SilentlyContinue'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        try { Invoke-WebRequest -Uri $url -OutFile $part -UseBasicParsing }
        catch { throw "falhou o download de $url ($(if ($erroCurl) { "$erroCurl; " })PowerShell: $($_.Exception.Message))" }
    }
    Move-Item $part $destino -Force
}
Etapa '3_motor' {
    # o que a geração antiga deixou (PS2Recomp clonado e compilado, Git portátil): não serve mais e ocupa vários GB
    foreach ($velho in 'ps2recomp', 'dl\mingit') {
        $v = Join-Path $R $velho
        if (Test-Path -LiteralPath $v) {
            Msg "apagando $velho\ (da geração antiga, não é mais usado)"
            Remove-Item -LiteralPath $v -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    if ($Pacote) {
        if (-not (Test-Path -LiteralPath $Pacote -PathType Leaf)) { throw "o pacote do motor não existe: $Pacote" }
        $zip = (Resolve-Path -LiteralPath $Pacote).Path
        Msg "motor: usando $zip (sem baixar)"
        $h = Sha256 $zip
        if ($h -ne $MOTOR_SHA256) {
            $lado = "$zip.sha256"
            if ((Test-Path -LiteralPath $lado) -and (((Get-Content -LiteralPath $lado -TotalCount 1) -split '\s+')[0].ToLower() -eq $h)) {
                Msg "AVISO: esse pacote não é o $MOTOR_NOME publicado; conferido pelo .sha256 ao lado"
            } else { throw "o SHA-256 do pacote não confere ($h; esperado $MOTOR_SHA256)" }
        }
    } else {
        $zip = Join-Path $R "dl\$MOTOR_NOME.zip"
        $ok = $false
        foreach ($url in $MOTOR_ESPELHO, $MOTOR_URL) {
            Msg "baixando o motor ($MOTOR_NOME) de $url"
            try {
                Baixar $url $zip
                $h = Sha256 $zip
                if ($h -ne $MOTOR_SHA256) { throw "SHA-256 diferente ($h)" }
                $ok = $true; break
            } catch {
                Anotar $LOG "não veio de $url`: $($_.Exception.Message)"
                Msg "não veio de $url ($($_.Exception.Message))"
                Remove-Item $zip -ErrorAction SilentlyContinue
            }
        }
        if (-not $ok) { throw "não consegui baixar o motor ($MOTOR_NOME). Confira a internet e se o antivírus não está bloqueando o download, e gere de novo." }
    }
    Anotar $LOG "SHA-256 do motor: $h"
    # abre numa pasta à parte e só então põe no lugar (um pacote aberto pela metade nunca fica como bom)
    $base = Join-Path $R 'motor'
    $abre = Join-Path $base '_abrindo'
    if (Test-Path -LiteralPath $abre) { Remove-Item -LiteralPath $abre -Recurse -Force }
    New-Item -ItemType Directory -Force $abre | Out-Null
    try { Expand-Archive -LiteralPath $zip -DestinationPath $abre -Force }
    catch { throw "o motor baixou inteiro (conferido), mas não foi extraído: $($_.Exception.Message). Confira o espaço livre no disco e se o antivírus não está bloqueando a pasta do jogo, e gere de novo." }
    $dentro = Join-Path $abre $MOTOR_NOME
    foreach ($a in 'VERSAO.txt', 'bin\otx_tradutor.exe', 'bin\otx_ferramentas.exe', 'cmake\CMakeLists.txt', 'ferramentas\hle_fora.txt',
                   'include\ps2xRuntime\ps2_call_list.h', 'lib\avx2\ps2_runtime.lib', 'lib\sse4\ps2_runtime.lib') {
        if (-not (Test-Path -LiteralPath (Join-Path $dentro $a))) { throw "o pacote do motor está incompleto (falta $a)" }
    }
    # motores de versões anteriores saem
    Get-ChildItem $base -Directory | Where-Object { $_.Name -ne '_abrindo' } | Remove-Item -Recurse -Force
    Move-Item -LiteralPath $dentro $PAC
    Remove-Item -LiteralPath $abre -Recurse -Force -ErrorAction SilentlyContinue
    if (-not $Pacote) { Remove-Item $zip -ErrorAction SilentlyContinue }
    Anotar $LOG (Get-Content (Join-Path $PAC 'VERSAO.txt') -TotalCount 1 -Encoding UTF8)
}
if (-not (Test-Path -LiteralPath (Join-Path $PAC 'bin\otx_tradutor.exe'))) { throw "o motor não está em $PAC (rode -RefazerDe 3)" }
# ferramentas (as dos .py num executável só: extração da ISO, mapa HLE, CSV, tabela de funções, VU1, lançador do clang-cl)
$FERR = Join-Path $PAC 'bin\otx_ferramentas.exe'
if (-not (Test-Path -LiteralPath $FERR)) { throw "o motor em $PAC não tem bin\otx_ferramentas.exe (pacote anterior a ele): use o gerar.ps1 ou um motor mais novo (-RefazerDe 3)" }
# exe de um motor anterior à extração da ISO e ao lançador (sem os subcomandos extrai_iso e lanca)
$usoFerr = SemExcecao { & $FERR 2>&1 | Out-String }
if ($usoFerr -notmatch 'extrai_iso' -or $usoFerr -notmatch '\blanca\b') { throw "o bin\otx_ferramentas.exe do motor em $PAC é de uma versão antiga: gere de novo a partir do motor (-RefazerDe 3)" }

# ---------------------------------------------------------------------------- disco (extração)
Etapa '2_disco' {
    if (Test-Path -LiteralPath $Iso -PathType Container) { throw "$Iso é uma pasta, não a ISO: escolha o arquivo .iso do jogo (imagem do DVD original, $($JOGO.serial); cópias ripadas/dubladas em pasta não servem)" }
    if (-not (Test-Path -LiteralPath $Iso -PathType Leaf)) { throw "a ISO não existe: $Iso (escolha o arquivo .iso de novo)" }
    $Iso = (Resolve-Path -LiteralPath $Iso).Path
    $tam = (Get-Item -LiteralPath $Iso).Length
    if ($tam -lt 100MB) { throw "a ISO tem só $([math]::Round($tam / 1MB, 1)) MB: arquivo incompleto ou não é a ISO do jogo (escolha o arquivo .iso de novo)" }
    Msg "conferindo a ISO ($([math]::Round($tam / 1GB, 2)) GB)"
    $h = Sha1 $Iso
    Anotar $LOG "SHA-1 da ISO: $h"
    if ($JOGO.iso_sha1 -notcontains $h) {
        Msg "AVISO: a ISO não é a cópia testada (SHA-1 $h). Vou conferir o executável do jogo."
    }
    Msg 'extraindo os arquivos do disco para trabalho\disc'
    Exec $LOG "`"$FERR`" extrai_iso `"$Iso`" `"$T\disc`" --elf `"$($JOGO.elf)`""
    if (-not (Test-Path -LiteralPath $ELF)) {
        # diz de que jogo a ISO é (o SYSTEM.CNF aponta o executável, cujo nome é o serial): ISO do jogo errado é o caso comum
        $cnf = Join-Path $T 'disc\SYSTEM.CNF'
        $qual = ''
        if ((Test-Path -LiteralPath $cnf) -and ((Get-Content -Raw -LiteralPath $cnf) -match 'BOOT2\s*=\s*cdrom0?:\\?([^;\r\n]+)')) {
            $serial = [IO.Path]::GetFileName($Matches[1].Trim()) -replace '_', '-' -replace '\.', ''
            $qual = " Essa ISO é de outro jogo ou versão (serial $serial)."
        }
        if (-not $qual -and -not (Select-String -LiteralPath $LOG -Pattern '^extra.do: ' -Quiet)) {
            # a extração não chegou ao fim e não disse por quê (ISO de outra versão o extrai_iso acusa antes, com a lista do que
            # ela tem): não é ISO errada. Report 1140: um script de inicialização do Prompt de Comando (AutoRun) que encerrava o cmd
            throw "a extração da ISO não chegou ao fim e o motivo não apareceu (não parece ser ISO errada). Confira o espaço livre no disco e se o antivírus não está bloqueando a pasta $T, e gere de novo. Se repetir, mande o log: $LOG"
        }
        throw "o executável $($JOGO.elf) não está nessa ISO.$qual Escolha a ISO do $($JOGO.nome), versão $($JOGO.versao)."
    }
    $he = Sha1 $ELF
    if ($JOGO.elf_sha1 -notcontains $he) {
        # o extrai_iso pula arquivo que já existe com o mesmo tamanho: um executável estragado de uma extração interrompida ficaria; extrai de novo
        Msg 'o executável extraído não confere: extraindo ele de novo'
        Remove-Item -LiteralPath $ELF -Force
        Exec $LOG "`"$FERR`" extrai_iso `"$Iso`" `"$T\disc`" --elf `"$($JOGO.elf)`""
        $he = Sha1 $ELF
    }
    if ($JOGO.elf_sha1 -notcontains $he) {
        # diz ao jogador por que não serve (pt/en/es): o serial do SYSTEM.CNF diferente do suportado = outra edição (região ou
        # versão); o mesmo serial com outro executável = executável modificado (patch, tradução, hack) ou outra tiragem do disco
        $serial = ''
        $cnf = Join-Path $T 'disc\SYSTEM.CNF'
        if ((Test-Path -LiteralPath $cnf) -and ((Get-Content -Raw -LiteralPath $cnf) -match 'BOOT2\s*=\s*cdrom0?:\\?([^;\r\n]+)')) {
            $serial = [IO.Path]::GetFileName($Matches[1].Trim()) -replace '_', '-' -replace '\.', ''
        }
        $suportado = ($JOGO.serial -replace '[^A-Za-z0-9]', '').ToUpper()
        $lido = ($serial -replace '[^A-Za-z0-9]', '').ToUpper()
        $txtSerial = if ($serial) { $serial } else { '?' }
        if ($lido -and $lido -ne $suportado) {
            $pt = "Edição diferente (outra região/versão): o disco é $txtSerial e o port suporta só $($JOGO.serial) ($($JOGO.versao))."
            $en = "Different edition (another region/version): the disc is $txtSerial and this port only supports $($JOGO.serial)."
            $es = "Edición diferente (otra región/versión): el disco es $txtSerial y este port solo admite $($JOGO.serial)."
        } else {
            $pt = "Executável modificado: o disco é $txtSerial, mas o executável não é o original da versão suportada ($($JOGO.versao)). Pode ser uma cópia com patch, tradução ou hack, ou outra tiragem do disco."
            $en = "Modified executable: the disc is $txtSerial, but its executable is not the original one of the supported version. It may be a patched, translated or hacked copy, or another print of the disc."
            $es = "Ejecutable modificado: el disco es $txtSerial, pero su ejecutable no es el original de la versión admitida. Puede ser una copia con parche, traducción o hack, u otra tirada del disco."
        }
        Anotar $LOG "serial do disco: $txtSerial (suportado: $($JOGO.serial)); SHA-1 do executável: $he"
        throw "o executável do jogo não é o da versão suportada.`r`n  $pt`r`n  $en`r`n  $es`r`n  (SHA-1 do executável: $he)"
    }
    # o jogo lê setores direto do disco: o jogar.cmd entrega a ISO ao runtime
    # UTF-8 sem BOM: o jogar.cmd lê com chcp 65001 (um BOM viraria parte do caminho)
    [IO.File]::WriteAllText((Join-Path $T 'iso.txt'), $Iso, (New-Object Text.UTF8Encoding $false))
}

# ---------------------------------------------------------------------------- tradução
# remendos.txt do jogo ("<endereço hex> <instrução hex>  # comentário"): instruções trocadas só no código traduzido,
# numa cópia do executável (o do disco fica como está)
function Remendar-Elf([string]$origem, [string]$destino, [string]$arqRem) {
    $b = [IO.File]::ReadAllBytes($origem)
    $phoff = [BitConverter]::ToUInt32($b, 0x1C); $phtam = [BitConverter]::ToUInt16($b, 0x2A); $phnum = [BitConverter]::ToUInt16($b, 0x2C)
    $n = 0
    foreach ($linha in [IO.File]::ReadAllLines($arqRem)) {
        $l = $linha.Split('#')[0].Trim()
        if (-not $l) { continue }
        $c = $l -split '\s+'
        $end = [Convert]::ToUInt32($c[0], 16); $val = [Convert]::ToUInt32($c[1], 16)
        $pos = -1
        for ($i = 0; $i -lt $phnum; $i++) {
            $ph = [int]($phoff + $i * $phtam)
            if ([BitConverter]::ToUInt32($b, $ph) -ne 1) { continue }   # só PT_LOAD
            $off = [BitConverter]::ToUInt32($b, $ph + 4); $va = [BitConverter]::ToUInt32($b, $ph + 8); $tam = [BitConverter]::ToUInt32($b, $ph + 16)
            if ($end -ge $va -and ($end + 4) -le ($va + $tam)) { $pos = [int]($off + ($end - $va)); break }
        }
        if ($pos -lt 0) { throw ("remendo fora do executável: {0:X8} (jogo\remendos.txt)" -f $end) }
        [Array]::Copy([BitConverter]::GetBytes($val), 0, $b, $pos, 4)
        $n++
    }
    New-Item -ItemType Directory -Force (Split-Path $destino) | Out-Null
    [IO.File]::WriteAllBytes($destino, $b)
    return $n
}
$RUNNER = Join-Path $C 'src\runner'
$HLE = Join-Path $T 'hle.txt'
Etapa '4_traduzir' {
    New-Item -ItemType Directory -Force $C | Out-Null
    if (Test-Path -LiteralPath $RUNNER) { Remove-Item -LiteralPath $RUNNER -Recurse -Force }
    New-Item -ItemType Directory -Force $RUNNER | Out-Null
    Copy-Item (Join-Path $PAC 'cmake\CMakeLists.txt') (Join-Path $C 'CMakeLists.txt') -Force
    $elfT = $ELF
    $rem = Join-Path $R 'jogo\remendos.txt'
    if (Test-Path -LiteralPath $rem) {
        $elfT = Join-Path $T ('traduzir\' + (Split-Path -Leaf $JOGO.elf))
        $n = Remendar-Elf $ELF $elfT $rem
        Anotar $LOG "$n remendos de instrução (jogo\remendos.txt)"
    }
    Msg 'mapa das funções do sistema (HLE)'
    Exec $LOG "`"$FERR`" mapa_hle_proprio `"$R\jogo`" `"$HLE`" --elf `"$ELF`" --lista `"$PAC\include\ps2xRuntime\ps2_call_list.h`" --fora `"$PAC\ferramentas\hle_fora.txt`""
    $g = Join-Path $T 'gerado'
    if (Test-Path -LiteralPath $g) { Remove-Item -LiteralPath $g -Recurse -Force }
    New-Item -ItemType Directory -Force $g | Out-Null
    $extras = Join-Path $R 'jogo\entradas_extra.txt'
    if (-not (Test-Path -LiteralPath $extras)) { $extras = '-' }
    Msg 'traduzindo o código do jogo (alguns minutos)'
    # fins inflados do CSV do Ghidra corrigidos pelo tamanho (senão uma função engole megabytes de código)
    $csvT = Join-Path $T 'funcoes.csv'
    Exec $LOG "`"$FERR`" limpa_csv `"$R\jogo\ghidra_funcoes.csv`" `"$csvT`""
    Exec $LOG "`"$PAC\bin\otx_tradutor.exe`" `"$elfT`" `"$csvT`" `"$extras`" `"$g`" 400 --hle `"$HLE`""
    Copy-Item (Join-Path $g '*') $RUNNER -Force
    Copy-Item (Join-Path $PAC 'include\abi\*.h') $RUNNER -Force
    # o código gerado fala com o runtime pela ABI atual do motor
    $jh = Join-Path $RUNNER 'otx_jogo.h'
    $txt = [IO.File]::ReadAllText($jh)
    [IO.File]::WriteAllText($jh, $txt.Replace('#include "otx_abi.h"', "#define OTX_ABI_RUNTIME_ATUAL`n#include `"otx_abi.h`""))
    Msg 'tabela de funções'
    Exec $LOG "`"$FERR`" tabela_propria `"$RUNNER\otx_jogo_tabela.cpp`" `"$RUNNER\register_functions.cpp`" `"$R\jogo`" --elf `"$ELF`" --hle `"$HLE`""
    Remove-Item (Join-Path $RUNNER 'otx_jogo_tabela.cpp') -Force
    Remove-Item -LiteralPath $g -Recurse -Force
    Anotar $LOG "$((Get-ChildItem $RUNNER -File).Count) arquivos em codigo\src\runner"
}

# ---------------------------------------------------------------------------- VU1 (geometria)
# Os microprogramas do VU1 ficam dentro do executável do jogo. A receita (jogo\vu1_receita.json) só diz onde
# (offsets e tamanhos) e como montar a memória de código; o otx_ferramentas extrai_vu1 monta a partir do SEU
# executável (confere o SHA-1) e o otx_ferramentas vu1_tradutor gera o C++. Sem receita ou se algo falhar, o VU1 fica no interpretador:
# o jogo roda igual, só que bem mais devagar.
Etapa '5_vu1' {
    $vu = Join-Path $C 'src\vu'
    if (Test-Path -LiteralPath $vu) { Remove-Item -LiteralPath $vu -Recurse -Force }
    New-Item -ItemType Directory -Force $vu | Out-Null
    $dv = Join-Path $T 'vu1'
    if (Test-Path -LiteralPath $dv) { Remove-Item -LiteralPath $dv -Recurse -Force }
    $rec = Join-Path $R 'jogo\vu1_receita.json'
    $ok = $false
    if (Test-Path -LiteralPath $rec) {
        try {
            Exec $LOG "`"$FERR`" extrai_vu1 extrai `"$rec`" `"$ELF`" `"$dv`""
            $ok = $true
        } catch {
            Msg "AVISO: não deu para montar o VU1 nativo; a geometria fica no interpretador (mais lento). $($_.Exception.Message)"
        }
    }
    if (-not $ok) {
        New-Item -ItemType Directory -Force $dv | Out-Null
        [IO.File]::WriteAllText((Join-Path $dv 'inicios.txt'), '')
        [IO.File]::WriteAllText((Join-Path $dv 'extras.txt'), '')
    }
    # programas mais executados: as operações de ponto flutuante em linha (compila mais devagar, roda mais rápido)
    if ($JOGO.vu1_quentes) { $env:PS2X_VU1_QUENTES = ($JOGO.vu1_quentes -join ',') }
    Msg 'traduzindo os microprogramas do VU1'
    Exec $LOG "`"$FERR`" vu1_tradutor `"$vu\vu1_programas.cpp`" `"$dv`" --extras `"$dv\extras.txt`""
}

# ---------------------------------------------------------------------------- compilar
# bibliotecas do motor com AVX2 só se a CPU tiver (o código traduzido fica mais rápido com ele); senão as SSE4
Add-Type -Namespace Otavix -Name Cpu -MemberDefinition '[DllImport("kernel32.dll")] public static extern bool IsProcessorFeaturePresent(uint f);'
$avx2 = [Otavix.Cpu]::IsProcessorFeaturePresent(40)
$VARIANTE = if ($avx2) { 'avx2' } else { 'sse4' }
# teste: OTX_VARIANTE=sse4 força as bibliotecas sem AVX2 num PC que tem AVX2
if ($env:OTX_VARIANTE -in 'avx2', 'sse4') { $VARIANTE = $env:OTX_VARIANTE }
if (-not $Jobs) {
    # cada pedaço do código traduzido usa de 1 a 3 GB de memória para compilar
    $livre = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
    $Jobs = [math]::Max(1, [math]::Min([Environment]::ProcessorCount, [math]::Floor($livre / 3)))
}
$BJ = Join-Path $C 'out\jogo'
Etapa '6_compilar' {
    # os microprogramas do VU1 compilam com o clang-cl do Visual Studio se ele estiver instalado (mais rápido);
    # sem ele, com o próprio MSVC. O lançador é o otx_ferramentas.exe do motor (subcomando lanca; sem Python)
    $lancador = $FERR.Replace('\', '/')
    $pac = $PAC.Replace('\', '/')
    Msg "compilando o jogo ($Jobs compilações em paralelo, motor $VARIANTE; de 5 a 30 min)"
    $cfg = "`"-DOTX_PACOTE=$pac`" -DOTX_VARIANTE=$VARIANTE `"-DPS2X_VU1_LANCADOR=$lancador`""
    Exec $LOG (ComVS "cmake -S `"$C`" -B `"$BJ`" -G Ninja $cfg")
    Exec $LOG (ComVS "cmake --build `"$BJ`" --target ps2EntryRunner --parallel $Jobs")
    if (-not (Test-Path (Join-Path $BJ 'ps2xRuntime\ps2EntryRunner.exe'))) { throw "o executável não foi gerado (veja $LOG)" }
}

# ---------------------------------------------------------------------------- jogar.cmd
Etapa '7_jogar' {
    $bin = Join-Path $R 'bin'
    New-Item -ItemType Directory -Force $bin | Out-Null
    Copy-Item (Join-Path $BJ 'ps2xRuntime\ps2EntryRunner.exe') (Join-Path $bin $JOGO.exe) -Force
    Copy-Item (Join-Path $BJ 'ps2xRuntime\*.dll') $bin -Force
    # variáveis do jogo (jogo.json "ambiente") ao lado do exe: o runtime lê ao abrir, sem passar por cima das que já
    # vierem definidas (assim o launcher, que abre o exe direto, e o jogar.cmd rodam o jogo do mesmo jeito)
    $ambTxt = @('# gerado pelo gerar.ps1 a partir do jogo\jogo.json ("ambiente"): NOME=valor')
    if ($JOGO.ambiente) { foreach ($v in $JOGO.ambiente.PSObject.Properties) { $ambTxt += "$($v.Name)=$($v.Value)" } }
    [IO.File]::WriteAllLines((Join-Path $bin 'ambiente.txt'), [string[]]$ambTxt, (New-Object Text.UTF8Encoding $false))
    $raizCd = if ($JOGO.cd_root) { "%RAIZ%trabalho\disc\$($JOGO.cd_root)" } else { '%RAIZ%trabalho\disc' }
    # variáveis do jogo (jogo.json "ambiente"), sem passar por cima das que o jogador já definiu
    $amb = @()
    if ($JOGO.ambiente) { foreach ($v in $JOGO.ambiente.PSObject.Properties) { $amb += "if not defined $($v.Name) set `"$($v.Name)=$($v.Value)`"" } }
    $linhas = @(
        '@echo off',
        'rem Gerado pelo gerar.ps1: abre o jogo com a ISO indicada na geracao (trabalho\iso.txt).',
        'setlocal',
        'chcp 65001 >nul',
        'set "RAIZ=%~dp0"',
        'set /p ISO=<"%RAIZ%trabalho\iso.txt"',
        'if not exist "%ISO%" (echo A ISO nao esta mais em "%ISO%". Rode o gerar de novo com -RefazerDe 2. & pause & exit /b 1)',
        'set "PS2X_CD_IMAGE=%ISO%"',
        "set `"PS2X_CD_ROOT=$raizCd`"",
        'if not exist "%RAIZ%out" mkdir "%RAIZ%out"')
    $linhas += $amb
    $linhas += "cd /d `"$raizCd`""
    $linhas += "`"%RAIZ%bin\$($JOGO.exe)`" `"%RAIZ%trabalho\disc\$($JOGO.elf)`" > `"%RAIZ%out\jogo.log`" 2>&1"
    Set-Content -Path (Join-Path $R 'jogar.cmd') -Encoding ASCII -Value $linhas
}
Msg "pronto. Para jogar: $R\jogar.cmd  (log em out\jogo.log)"
