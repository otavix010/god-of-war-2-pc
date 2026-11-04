<#
.SYNOPSIS
  Gera e compila o port a partir da SUA cópia do jogo (imagem .iso do DVD de PS2).

.DESCRIPTION
  Faz tudo em ordem, e cada etapa pula se já foi feita (use -Refazer para refazer tudo,
  ou -RefazerDe N para refazer da etapa N em diante):
    1. confere as ferramentas (Visual Studio Build Tools com C++ e CMake, Python, Git);
    2. confere a sua ISO e extrai os arquivos do disco para trabalho\disc;
    3. baixa o PS2Recomp na versão fixada, aplica as nossas correções e compila o tradutor;
    4. traduz o código do jogo (MIPS R5900 -> C++);
    5. traduz os microprogramas de geometria (VU1) do executável do seu disco para C++;
    6. compila o jogo;
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
  Refaz da etapa N em diante. Depois de atualizar o port, -RefazerDe 3 aplica as correções
  novas, retraduz e recompila sem extrair o disco de novo.
.EXAMPLE
  gerar.cmd     (clique duas vezes: pede a ISO numa janela)
.EXAMPLE
  .\gerar.ps1 -Iso "D:\ISOs\meu jogo.iso"
#>
param(
    [string]$Iso = '',
    [int]$Jobs = 0,
    [int]$RefazerDe = 0,
    [switch]$Refazer
)
$ErrorActionPreference = 'Stop'
$R = $PSScriptRoot
if ($R -match ' ') { throw "Coloque o projeto numa pasta sem espaços (agora: $R)" }
$JOGO = Get-Content -Raw -Encoding UTF8 (Join-Path $R 'jogo\jogo.json') | ConvertFrom-Json
$PS2RECOMP_URL = 'https://github.com/ran-j/PS2Recomp.git'
$PS2RECOMP_SHA = 'e5636981a1c9de368f6b71e819c3dc188dfedbf4'
$MINGIT_URL = 'https://github.com/git-for-windows/git/releases/download/v2.56.0.windows.3/MinGit-2.56.0.3-64-bit.zip'
$T = Join-Path $R 'trabalho'
$OUT = Join-Path $R 'out\gerar'
New-Item -ItemType Directory -Force $OUT, $T | Out-Null
if ($RefazerDe -gt 0) {
    Get-ChildItem $OUT -Filter '*.ok' | Where-Object { [int]($_.Name.Split('_')[0]) -ge $RefazerDe } | Remove-Item -Force
}

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
    cmd /c "$linha >> `"$log`" 2>&1"
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

# ---------------------------------------------------------------------------- ferramentas
function Achar-VS {
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path $vswhere)) { return $null }
    $p = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 Microsoft.VisualStudio.Component.VC.CMake.Project -property installationPath
    if ($p) { return ($p | Select-Object -First 1) }
    return $null
}
# o git só vale se rodar (um MinGit incompleto ou barrado pelo antivírus sai com 0xC0000135): o portátil quebrado é
# apagado para a etapa 1 baixar de novo
function Git-Roda([string]$exe) {
    try { $o = & $exe --version 2>$null; return ($LASTEXITCODE -eq 0 -and "$o" -match 'git version') } catch { return $false }
}
function Achar-Git {
    $g = Get-Command git.exe -ErrorAction SilentlyContinue
    if ($g -and (Git-Roda $g.Source)) { return $g.Source }
    $m = Join-Path $R 'dl\mingit\cmd\git.exe'
    if (Test-Path -LiteralPath $m) {
        if (Git-Roda $m) { return $m }
        Remove-Item -LiteralPath (Join-Path $R 'dl\mingit') -Recurse -Force -ErrorAction SilentlyContinue
    }
    return $null
}
function Baixa-MinGit {
    Msg "baixando o Git portátil (MinGit) de $MINGIT_URL"
    $zip = Join-Path $R 'dl\mingit.zip'
    New-Item -ItemType Directory -Force (Join-Path $R 'dl') | Out-Null
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $MINGIT_URL -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath (Join-Path $R 'dl\mingit') -Force
    Remove-Item $zip
    if (-not (Achar-Git)) { throw 'o Git portátil não roda (dl\mingit\cmd\git.exe). Se o antivírus bloqueou, libere a pasta do port e gere de novo.' }
}
Etapa '1_ferramentas' {
    $falta = @()
    # "python" pode ser o atalho da Microsoft Store (abre a loja, não roda nada)
    $v = ''
    try { $v = (cmd /c 'python -c "import sys; print(sys.version_info[0]*100+sys.version_info[1])" 2>nul') } catch { }
    if (-not ($v -match '^\d+$')) { $falta += 'Python 3.11 ou mais novo (winget install Python.Python.3.12) -- e feche/abra o terminal depois' }
    elseif ([int]$v -lt 311) { $falta += 'Python 3.11 ou mais novo (winget install Python.Python.3.12)' }
    if (-not (Achar-VS)) {
        $falta += 'Visual Studio 2022 Build Tools com C++ e "C++ CMake tools":' +
                  "`r`n    winget install Microsoft.VisualStudio.2022.BuildTools --override `"--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.CMake.Project --add Microsoft.VisualStudio.Component.VC.Llvm.Clang --includeRecommended`""
    }
    if ($falta) { throw ("Falta instalar:`r`n  - " + ($falta -join "`r`n  - ")) }
    if (-not (Achar-Git)) { Baixa-MinGit }
}
$VS = Achar-VS
if (-not $VS) { throw 'Visual Studio Build Tools com C++ e CMake não encontrado (rode de novo a etapa 1: -RefazerDe 1)' }
$GIT = Achar-Git
if (-not $GIT) { Baixa-MinGit; $GIT = Achar-Git } # o portátil sumiu ou quebrou depois da etapa 1
# o CMake baixa as dependências do PS2Recomp com o git: o portátil precisa estar no PATH
$env:PATH = (Split-Path $GIT) + ';' + $env:PATH
# o vcvars64.bat procura o vswhere.exe no PATH
$env:PATH = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer;" + $env:PATH
$VCVARS = Join-Path $VS 'VC\Auxiliary\Build\vcvars64.bat'
# temporários do compilador na pasta do projeto (o C++ traduzido gera arquivos grandes)
$TMPC = Join-Path $R 'out\tmp'
New-Item -ItemType Directory -Force $TMPC | Out-Null
function ComVS([string]$linha) { "call `"$VCVARS`" >nul && set `"TEMP=$TMPC`" && set `"TMP=$TMPC`" && $linha" }
# sem o Windows SDK o CMake falha em "Detecting C compiler ABI" (RC Pass 1 failed, CMAKE_MT-NOTFOUND): avisa antes
cmd /c (ComVS 'where rc.exe mt.exe') *> $null
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
Etapa '2_disco' {
    if (-not $Iso) {
        $Iso = Escolher-Iso "Escolha a ISO do $($JOGO.nome) ($($JOGO.versao))"
        if (-not $Iso) { throw 'sem a ISO do jogo' }
    }
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
    Exec $LOG "python -I `"$R\ferramentas\extrai_iso.py`" `"$Iso`" `"$T\disc`" --elf `"$($JOGO.elf)`""
    if (-not (Test-Path -LiteralPath $ELF)) {
        # diz de que jogo a ISO é (o SYSTEM.CNF aponta o executável, cujo nome é o serial): ISO do jogo errado é o caso comum
        $cnf = Join-Path $T 'disc\SYSTEM.CNF'
        $qual = ''
        if ((Test-Path -LiteralPath $cnf) -and ((Get-Content -Raw -LiteralPath $cnf) -match 'BOOT2\s*=\s*cdrom0?:\\?([^;\r\n]+)')) {
            $serial = [IO.Path]::GetFileName($Matches[1].Trim()) -replace '_', '-' -replace '\.', ''
            $qual = " Essa ISO é de outro jogo ou versão (serial $serial)."
        }
        throw "o executável $($JOGO.elf) não está nessa ISO.$qual Escolha a ISO do $($JOGO.nome), versão $($JOGO.versao)."
    }
    $he = Sha1 $ELF
    if ($JOGO.elf_sha1 -notcontains $he) {
        throw "o executável do jogo não é o da versão suportada ($($JOGO.versao), $($JOGO.serial)). SHA-1 dele: $he"
    }
    # o jogo lê setores direto do disco: o jogar.cmd entrega a ISO ao runtime
    # UTF-8 sem BOM: o jogar.cmd lê com chcp 65001 (um BOM viraria parte do caminho)
    [IO.File]::WriteAllText((Join-Path $T 'iso.txt'), $Iso, (New-Object Text.UTF8Encoding $false))
}

# ---------------------------------------------------------------------------- PS2Recomp
$P = Join-Path $R 'ps2recomp'
Etapa '3_ps2recomp' {
    if (Test-Path -LiteralPath (Join-Path $P '.git')) {
        Msg 'PS2Recomp já baixado'
    } else {
        if (Test-Path -LiteralPath $P) { Remove-Item -LiteralPath $P -Recurse -Force }
        Msg "baixando o PS2Recomp ($PS2RECOMP_URL)"
        Exec $LOG "`"$GIT`" -c safe.directory=* clone --quiet $PS2RECOMP_URL `"$P`""
    }
    # --force descarta as correções antigas: elas são aplicadas de novo logo abaixo
    Exec $LOG "`"$GIT`" -c safe.directory=* -C `"$P`" -c advice.detachedHead=false checkout --force --quiet $PS2RECOMP_SHA"
    Exec $LOG "`"$GIT`" -c safe.directory=* -C `"$P`" clean -fdq ps2xRuntime ps2xIOP"
    foreach ($pt in Get-ChildItem (Join-Path $R 'patches') -Filter '*.patch' | Sort-Object Name) {
        Msg "aplicando patches\$($pt.Name)"
        Exec $LOG "`"$GIT`" -c safe.directory=* -C `"$P`" apply --whitespace=nowarn `"$($pt.FullName)`""
    }
    Msg 'compilando o tradutor (ps2_recomp)'
    $b = Join-Path $P 'out\ferramentas'
    Exec $LOG (ComVS "cmake -S `"$P`" -B `"$b`" -G Ninja -DCMAKE_BUILD_TYPE=Release -DPS2X_AVX2=OFF -DPS2X_BUILD_RUNTIME=OFF -DPS2X_BUILD_TEST=OFF -DPS2X_BUILD_STUDIO=OFF -DPS2X_BUILD_ANALYZER=OFF")
    Exec $LOG (ComVS "cmake --build `"$b`" --target ps2_recomp")
}
$RECOMP = Get-ChildItem (Join-Path $P 'out\ferramentas') -Recurse -Filter 'ps2_recomp.exe' -ErrorAction SilentlyContinue | Select-Object -First 1

# ---------------------------------------------------------------------------- tradução
Etapa '4_traduzir' {
    if (-not $RECOMP) { throw 'o ps2_recomp.exe não foi compilado (rode -RefazerDe 3)' }
    foreach ($a in 'analisador.toml', 'ghidra_config.toml', 'ghidra_funcoes.csv', 'entradas_extra.txt', 'stubs_extra.txt', 'stubs_tirar.txt', 'remendos.txt') {
        $o = Join-Path $R "jogo\$a"
        if (Test-Path -LiteralPath $o) { Copy-Item -LiteralPath $o $T -Force }
    }
    Exec $LOG "python `"$R\ferramentas\monta_config.py`" `"$T`" `"disc/$($JOGO.elf.Replace('\', '/'))`""
    $g = Join-Path $T 'gerado'
    if (Test-Path -LiteralPath $g) { Remove-Item -LiteralPath $g -Recurse -Force }
    New-Item -ItemType Directory -Force $g | Out-Null
    Msg 'traduzindo o código do jogo (alguns minutos)'
    Exec $LOG "`"$($RECOMP.FullName)`" `"$T\config.toml`""
    Exec $LOG "python `"$R\ferramentas\sincroniza.py`" `"$g`" `"$P\ps2xRuntime\src\runner`" `"$P\ps2xRuntime\include`""
}

# ---------------------------------------------------------------------------- VU1 (geometria)
# Os microprogramas do VU1 ficam dentro do executável do jogo. A receita (jogo\vu1_receita.json) só diz onde
# (offsets e tamanhos) e como montar a memória de código; o extrai_vu1.py monta a partir do SEU executável
# (confere o SHA-1) e o vu1_tradutor.py gera o C++. Sem receita ou se algo falhar, o VU1 fica no interpretador:
# o jogo roda igual, só que bem mais devagar.
Etapa '5_vu1' {
    $vu = Join-Path $P 'ps2xRuntime\src\lib\vu'
    $dv = Join-Path $T 'vu1'
    if (Test-Path -LiteralPath $dv) { Remove-Item -LiteralPath $dv -Recurse -Force }
    $rec = Join-Path $R 'jogo\vu1_receita.json'
    $ok = $false
    if (Test-Path -LiteralPath $rec) {
        try {
            Exec $LOG "python -I `"$R\ferramentas\extrai_vu1.py`" extrai `"$rec`" `"$ELF`" `"$dv`""
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
    Exec $LOG "python -I `"$R\ferramentas\vu1_tradutor.py`" `"$vu\vu1_programas.cpp`" `"$dv`" --extras `"$dv\extras.txt`""
}

# ---------------------------------------------------------------------------- compilar
# AVX2 só se a CPU tiver (o código traduzido fica mais rápido com ele)
Add-Type -Namespace Otavix -Name Cpu -MemberDefinition '[DllImport("kernel32.dll")] public static extern bool IsProcessorFeaturePresent(uint f);'
$avx2 = [Otavix.Cpu]::IsProcessorFeaturePresent(40)
if (-not $Jobs) {
    # cada pedaço do código traduzido usa de 1 a 3 GB de memória para compilar
    $livre = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
    $Jobs = [math]::Max(1, [math]::Min([Environment]::ProcessorCount, [math]::Floor($livre / 3)))
}
$BJ = Join-Path $P 'out\jogo'
Etapa '6_compilar' {
    $arch = if ($avx2) { '/arch:AVX2 ' } else { '' }
    # os microprogramas do VU1 compilam com o clang-cl do Visual Studio se ele estiver instalado (mais rápido);
    # sem ele, com o próprio MSVC
    $lancador = (Join-Path $R 'ferramentas\otx_lanca.py').Replace('\', '/')
    Msg "compilando o jogo ($Jobs compilações em paralelo$(if ($avx2) { ', AVX2' }); de 20 min a 1 h)"
    $cfg = "-DCMAKE_BUILD_TYPE=RelWithDebInfo `"-DCMAKE_CXX_FLAGS_RELWITHDEBINFO=/O2 /Ob2 /Oi /DNDEBUG $arch/GS- /bigobj`" `"-DCMAKE_C_FLAGS_RELWITHDEBINFO=/O2 /DNDEBUG`" " +
           "`"-DCMAKE_EXE_LINKER_FLAGS_RELWITHDEBINFO=/INCREMENTAL:NO`" -DPS2X_ENABLE_AGRESSIVE_LOGS=OFF -DPS2X_ENABLE_IOP_RPC_TRACE=OFF " +
           "-DPS2X_SHOW_WINDOWS_CONSOLE=OFF -DPS2X_BUILD_TEST=OFF -DPS2X_BUILD_STUDIO=OFF -DPS2X_BUILD_ANALYZER=OFF " +
           "`"-DPS2X_VU1_LANCADOR=$lancador`""
    Exec $LOG (ComVS "cmake -S `"$P`" -B `"$BJ`" -G Ninja $cfg")
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
