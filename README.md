<h1 align="center">God of War II — port nativo para PC</h1>

<p align="center"><i>God of War II (PS2, NTSC-U SCUS-97481): port nativo para PC por recompilação estática (PS2Recomp). Gera a partir da sua ISO. Beta.</i></p>

<p align="center">
  <a href="https://github.com/otavix010/god-of-war-2-pc/commits/main"><img alt="Última atualização" src="https://img.shields.io/github/last-commit/otavix010/god-of-war-2-pc?label=%C3%BAltima%20atualiza%C3%A7%C3%A3o"></a>
  <a href="https://github.com/otavix010/otavix-launcher/releases/latest"><img alt="Baixar o Otavix Launcher" src="https://img.shields.io/badge/Otavix%20Launcher-baixar-b00020"></a>
</p>

<p align="center">
  <a href="#o-que-é">O que é</a> ·
  <a href="#estado-atual-beta">Estado atual: beta</a> ·
  <a href="#opções">Opções</a> ·
  <a href="#como-gerar">Como gerar</a> ·
  <a href="#como-funciona">Como funciona</a> ·
  <a href="#english-summary">English</a>
</p>

> **Projeto de fãs, sem fins lucrativos.** *God of War II* e *God of War* são marcas da Sony Interactive Entertainment; o jogo foi desenvolvido pelo Santa Monica Studio. Este projeto não tem relação com a Sony Interactive Entertainment. Este repositório **não contém o jogo**: você precisa da **sua própria cópia** do DVD (a versão americana, **SCUS-97481**).

[English summary below](#english-summary)

## O que é

Um port **nativo** do *God of War II* (PlayStation 2, 2007) para Windows. Não é um emulador: o código do jogo é **traduzido para C++ e compilado** para x86-64 (recompilação estática), com o motor PS2 próprio do projeto (Otavix).

Como o código do jogo não pode ser distribuído, **o seu PC gera e compila a parte do jogo a partir da sua ISO**. Um comando só faz tudo.

## Estado atual: beta

O jogo roda do começo, com som, vídeos e gráficos como no PlayStation 2. **Roda a 60 FPS em PCs atuais** (testado num Ryzen 7 9800X3D). Num notebook com processador de 4 núcleos (i5 de 8ª geração), use o **modo 30 FPS**, que segura o ritmo estável. A parte gráfica do console (GS) roda na placa de vídeo (OpenGL 4.3). Os microprogramas de geometria do VU1 são traduzidos para C++ na sua máquina, a partir do executável do seu disco (a etapa "VU1" do gerador).

Problemas conhecidos: em alguns PCs o vídeo de abertura pode travar de vez em quando (feche e abra de novo); uma faixa verde fina aparece nas últimas linhas da imagem em algumas telas. Relate o que encontrar pelo launcher.

## Opções

Pelo [Otavix Launcher](https://github.com/otavix010/otavix-launcher/releases/latest), no menu de opções do jogo: **30 ou 60 FPS**, janela ou **tela cheia** (no jogo, F11 ou Alt+Enter alternam), tamanho da janela, escalonador (**bilinear, AMD FSR 1 ou NVIDIA Image Scaling**) e a nitidez dele, anti-serrilhamento **FXAA**, proporção 4:3, 16:9, 21:9 e 32:9 (ultrawide) e predefinições (Notebook / PC fraco, Equilibrado, Qualidade). Sem o launcher, as mesmas opções são variáveis de ambiente: `PS2X_QPS=30`, `PS2X_TELA_CHEIA=1`, `PS2X_JANELA_TAM=1920x1080`, `PS2X_ESCALA=nenhum|bilinear|fsr|nis`, `PS2X_NITIDEZ_PCT=0..100`, `PS2X_FXAA=1`, `PS2X_ASPECTO=4:3|16:9|21:9|32:9|tela|nativo`.

## Como gerar

### Pelo Otavix Launcher

O [Otavix Launcher](https://github.com/otavix010/otavix-launcher/releases/latest) lista este port: ele baixa o port, pede a ISO, gera o jogo e abre.

### À mão

**1. O que você precisa ter:** a sua cópia do *God of War II* **americano** (SCUS-97481, "God of War II (USA)") como imagem **.iso** do DVD. O gerador confere o executável do jogo pelo hash: outras versões não servem, porque o mapa de funções é o da americana.

**2. Instale as ferramentas (uma vez só)**, num terminal:
```
winget install Microsoft.VisualStudio.2022.BuildTools --override "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.CMake.Project --add Microsoft.VisualStudio.Component.VC.Llvm.Clang --includeRecommended"
```
O resto o gerador baixa sozinho: o motor do port (pacote pronto, conferido pelo SHA-256) e o FFmpeg (LGPL). Não precisa de Python nem de Git.

**3. Baixe este repositório** (botão *Code > Download ZIP*, ou `git clone`) e extraia numa pasta **sem espaços no caminho**, por exemplo `C:\god-of-war-2-pc`. Deixe uns 15 GB livres nesse disco (os arquivos do disco, o código traduzido e a compilação).

**4. Clique duas vezes em `gerar.cmd`** e escolha a ISO. Ele:
- confere a ISO e extrai os arquivos do disco para `trabalho\disc`;
- baixa o motor do port (pacote pronto, conferido pelo SHA-256);
- traduz o código do jogo e os microprogramas do VU1 para C++ (só no seu PC);
- compila o código do jogo (de 5 a 30 minutos, conforme o PC; precisa de 16 GB de RAM ou mais).

**5. Jogue com `jogar.cmd`.** O jogo lê os arquivos de `trabalho\disc` e a ISO no lugar onde ela estava na geração (se mudar a ISO de lugar, rode `gerar.cmd -RefazerDe 2`).

Depois de atualizar o port, `gerar.cmd -RefazerDe 3` baixa o motor novo, retraduz e recompila sem extrair o disco de novo. Com o componente "C++ Clang tools" do Visual Studio instalado (já incluído no comando acima), a geometria compila com o clang-cl e fica mais rápida.

## Como funciona

- **O motor** (tradutor MIPS R5900 → C++ e runtime: GS, VU1, DMA, IOP, áudio SPU2, cartão de memória) é próprio do projeto e vem pronto (bibliotecas compiladas); o seu PC só traduz e compila o código do jogo.
- **O mapa de funções** (`jogo\ghidra_funcoes.csv`) veio de uma análise com o [Ghidra](https://ghidra-sre.org/) e a extensão ghidra-emotionengine-reloaded: são só endereços e nomes, nada do código do jogo. `jogo\entradas_extra.txt` lista funções chamadas só por ponteiro e alvos de tabelas de salto que a análise não marcou.
- **A receita do VU1** (`jogo\vu1_receita.json`) diz onde os microprogramas de geometria ficam no executável (offsets e tamanhos, conferidos por SHA-1) e como montar a memória de código do VU1; o único trecho que não vem do executável é uma instrução de 8 bytes que o próprio jogo monta enquanto roda.
- O modo 30 FPS usa o limitador do próprio jogo (um remendo de memória no endereço 2D80B8, como os que os jogadores usam no PCSX2), aplicado pelo runtime quando `PS2X_QPS=30`.

## Licença e créditos

- **O nosso código** (`gerar.ps1`, `gerar.cmd`, `ferramentas\`): [MIT](LICENSE).
- **O motor do port** (pacote `otx-motor-ps2`, baixado pronto pelo gerador) não é coberto pela licença MIT; os avisos de terceiros dele (raylib e glfw: zlib; FFmpeg: LGPL, DLLs à parte) estão no `TERCEIROS.txt` do pacote.
- O NIS vem do [NVIDIA Image Scaling SDK](https://github.com/NVIDIAGameWorks/NVIDIAImageScaling) (MIT) e o FSR 1 do [AMD FidelityFX FSR](https://github.com/GPUOpen-Effects/FidelityFX-FSR) (MIT).
- *God of War II* e *God of War* são marcas da Sony Interactive Entertainment. Este é um projeto de fãs, sem fins lucrativos, sem relação com a Sony Interactive Entertainment nem o Santa Monica Studio nem endossado por eles.

## English summary

A **native PC port** of *God of War II* (PlayStation 2, 2007) made by **static recompilation** with the project's own PS2 engine. **Beta.** It runs from the start with sound, videos and PS2-accurate graphics, at **60 FPS on current PCs**; on 4-core laptops use the **30 FPS mode**. The console's graphics chip (GS) runs on your GPU (OpenGL 4.3). Options in the launcher: 30/60 FPS, window or fullscreen (F11 / Alt+Enter), window size, upscaler (bilinear, AMD FSR 1, NVIDIA Image Scaling) and sharpness, FXAA, aspect ratio 4:3, 16:9, 21:9 and 32:9 (ultrawide).

**Bring your own game**: no game code or data here, only the function map (addresses), translation settings and the VU1 "recipe" (offsets and sizes in your executable). You need the **US** release (SCUS-97481, Redump "God of War II (USA)") as an **.iso**. Install Visual Studio 2022 Build Tools with C++, CMake and Clang (commands above), download this repository to a path without spaces with about 15 GB free, double-click **`gerar.cmd`** (it checks your ISO, extracts the disc files, downloads the prebuilt engine package (no Git needed), translates the game code on your PC and builds it, in 5 to 30 minutes; 16 GB of RAM needed), then play with **`jogar.cmd`**.

License: our scripts are MIT; the engine package is not covered by it, and its third-party notices are in its `TERCEIROS.txt`. *God of War II* and *God of War* are trademarks of Sony Interactive Entertainment; this is a non-commercial fan project, not affiliated with or endorsed by Sony Interactive Entertainment or Santa Monica Studio.
