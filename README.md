# God of War II — port nativo para PC

> **Projeto de fãs, sem fins lucrativos.** *God of War II* e *God of War* são marcas da Sony Interactive Entertainment; o jogo foi desenvolvido pelo Santa Monica Studio. Este projeto não tem relação com a Sony Interactive Entertainment. Este repositório **não contém o jogo**: você precisa da **sua própria cópia** do DVD (a versão americana, **SCUS-97481**).

[English summary below](#english-summary)

## O que é

Um port **nativo** do *God of War II* (PlayStation 2, 2007) para Windows. Não é um emulador: o código do jogo é **traduzido para C++ e compilado** para x86-64 (recompilação estática), em cima do [PS2Recomp](https://github.com/ran-j/PS2Recomp).

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
winget install Python.Python.3.12
winget install Microsoft.VisualStudio.2022.BuildTools --override "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.CMake.Project --add Microsoft.VisualStudio.Component.VC.Llvm.Clang --includeRecommended"
```
O resto o gerador baixa sozinho: o PS2Recomp (na versão fixada), as bibliotecas dele e, se o PC não tiver Git, o Git portátil (MinGit).

**3. Baixe este repositório** (botão *Code > Download ZIP*, ou `git clone`) e extraia numa pasta **sem espaços no caminho**, por exemplo `C:\god-of-war-2-pc`. Deixe uns 25 GB livres nesse disco (os arquivos do disco, o código traduzido e a compilação).

**4. Clique duas vezes em `gerar.cmd`** e escolha a ISO. Ele:
- confere a ISO e extrai os arquivos do disco para `trabalho\disc`;
- baixa o PS2Recomp, aplica as nossas correções (`patches\`) e compila o tradutor;
- traduz o código do jogo e os microprogramas do VU1 para C++ (só no seu PC);
- compila o jogo (de 30 minutos a 1 hora e meia, conforme o PC; precisa de 16 GB de RAM ou mais e de um processador com AVX2).

**5. Jogue com `jogar.cmd`.** O jogo lê os arquivos de `trabalho\disc` e a ISO no lugar onde ela estava na geração (se mudar a ISO de lugar, rode `gerar.cmd -RefazerDe 2`).

Depois de atualizar o port, `gerar.cmd -RefazerDe 3` aplica as correções novas, retraduz e recompila sem extrair o disco de novo. Com o componente "C++ Clang tools" do Visual Studio instalado (já incluído no comando acima), a geometria compila com o clang-cl e fica mais rápida.

## Como funciona

- **PS2Recomp** traduz o executável do PS2 (MIPS R5900, o "Emotion Engine") para C++ e compila com o runtime dele.
- **O mapa de funções** (`jogo\ghidra_funcoes.csv`) veio de uma análise com o [Ghidra](https://ghidra-sre.org/) e a extensão [ghidra-emotionengine-reloaded](https://github.com/chaoticgd/ghidra-emotionengine-reloaded): são só endereços e nomes, nada do código do jogo. `jogo\entradas_extra.txt` lista funções chamadas só por ponteiro e alvos de tabelas de salto que a análise não marcou.
- **A receita do VU1** (`jogo\vu1_receita.json`) diz onde os microprogramas de geometria ficam no executável (offsets e tamanhos, conferidos por SHA-1) e como montar a memória de código do VU1; o único trecho que não vem do executável é uma instrução de 8 bytes que o próprio jogo monta enquanto roda.
- **As nossas correções no PS2Recomp** (GPLv3 como ele), em `patches\`: no tradutor (desvios e ponto flutuante como no EE) e no runtime (o "sistema operacional" do console, leitura de setores direto da ISO, o chip de som SPU2 emulado no IOP, vídeos MPEG, o GS desenhado na placa de vídeo, o VU1 traduzido, threads por núcleo e o menu de imagem: FSR 1, NIS e FXAA).
- O modo 30 FPS usa o limitador do próprio jogo (um remendo de memória no endereço 2D80B8, como os que os jogadores usam no PCSX2), aplicado pelo runtime quando `PS2X_QPS=30`.

## Licença e créditos

- **O nosso código** (`gerar.ps1`, `gerar.cmd`, `ferramentas\`): [MIT](LICENSE).
- **PS2Recomp** (baixado pelo gerador) e **as nossas correções nele** (`patches\`): [GPLv3](https://github.com/ran-j/PS2Recomp/blob/main/LICENSE), de ran-j e colaboradores. O executável gerado no seu PC também é GPLv3.
- O NIS vem do [NVIDIA Image Scaling SDK](https://github.com/NVIDIAGameWorks/NVIDIAImageScaling) (MIT) e o FSR 1 do [AMD FidelityFX FSR](https://github.com/GPUOpen-Effects/FidelityFX-FSR) (MIT).
- *God of War II* e *God of War* são marcas da Sony Interactive Entertainment. Este é um projeto de fãs, sem fins lucrativos, sem relação com a Sony Interactive Entertainment nem o Santa Monica Studio nem endossado por eles.

## English summary

A **native PC port** of *God of War II* (PlayStation 2, 2007) made by **static recompilation** with [PS2Recomp](https://github.com/ran-j/PS2Recomp). **Beta.** It runs from the start with sound, videos and PS2-accurate graphics, at **60 FPS on current PCs**; on 4-core laptops use the **30 FPS mode**. The console's graphics chip (GS) runs on your GPU (OpenGL 4.3). Options in the launcher: 30/60 FPS, window or fullscreen (F11 / Alt+Enter), window size, upscaler (bilinear, AMD FSR 1, NVIDIA Image Scaling) and sharpness, FXAA, aspect ratio 4:3, 16:9, 21:9 and 32:9 (ultrawide).

**Bring your own game**: no game code or data here, only the function map (addresses), translation settings and the VU1 "recipe" (offsets and sizes in your executable). You need the **US** release (SCUS-97481, Redump "God of War II (USA)") as an **.iso**. Install Python 3.11+ and Visual Studio 2022 Build Tools with C++, CMake and Clang (commands above), download this repository to a path without spaces with about 25 GB free, double-click **`gerar.cmd`** (it checks your ISO, extracts the disc files, fetches the pinned PS2Recomp, applies our patches, translates the game code on your PC and builds it; 16 GB of RAM and an AVX2 CPU needed), then play with **`jogar.cmd`**.

License: our scripts are MIT; PS2Recomp and our patches to it are GPLv3. *God of War II* and *God of War* are trademarks of Sony Interactive Entertainment; this is a non-commercial fan project, not affiliated with or endorsed by Sony Interactive Entertainment or Santa Monica Studio.
