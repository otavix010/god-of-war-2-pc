# Novidades do port

O Otavix Launcher mostra este arquivo na página "Novidades" do jogo. Cada atualização tem um título
"## <data> · <versão>" e o texto em português (### pt), inglês (### en) e espanhol (### es). As mais novas ficam em cima.

## 13/11/2026 · 0.1.10
### pt
- **Resolução interna (2x/4x) de verdade**: a imagem final do jogo saía na resolução original ampliada, e por isso ficava pixelada mesmo em 4x. Agora sai na resolução escolhida, bem mais nítida.
- **Imagem suavizada com resolução interna**: com 2x/4x e o escalonador "Nenhum", a imagem esticada para a tela ficava serrilhada; agora é suavizada.
- **Medidor do F10 visível em tela cheia**: o medidor de desempenho não aparecia sobre o jogo em tela cheia; agora é desenhado pelo próprio jogo, no canto da imagem.
- Motor 0.1.11: na próxima geração o gerador refaz da etapa 3 sozinho (o disco extraído continua valendo).
### en
- **Real internal resolution (2x/4x)**: the final image came out at the original resolution scaled up, so it looked pixelated even at 4x. It now renders at the chosen resolution, much sharper.
- **Smoothed image with internal resolution**: with 2x/4x and the "None" scaler, the image stretched to the screen looked jagged; it is now smoothed.
- **F10 overlay visible in fullscreen**: the performance overlay did not show over the game in fullscreen; it is now drawn by the game itself, in the corner of the image.
- Engine 0.1.11: on the next generation the generator redoes it from step 3 on its own (the extracted disc is kept).
### es
- **Resolución interna (2x/4x) de verdad**: la imagen final del juego salía en la resolución original ampliada, y por eso se veía pixelada incluso en 4x. Ahora sale en la resolución elegida, mucho más nítida.
- **Imagen suavizada con resolución interna**: con 2x/4x y el escalador "Ninguno", la imagen estirada a la pantalla se veía dentada; ahora se suaviza.
- **Medidor de F10 visible en pantalla completa**: el medidor de rendimiento no aparecía sobre el juego en pantalla completa; ahora lo dibuja el propio juego, en la esquina de la imagen.
- Motor 0.1.11: en la próxima generación el generador rehace desde la etapa 3 solo (el disco extraído se mantiene).

## 13/11/2026 · 0.1.9
### pt
- **O vídeo de abertura volta a aparecer**: o ataque a Rodes, logo depois da cena do trono, era pulado e o jogo ia direto para a cidade. Agora ele toca inteiro, com som.
- **Corrigida uma causa de fechamento do jogo com o erro 0xC0000005** depois de alguns minutos de jogo: em certas cenas o motor lia memória fora do lugar ao enviar os gráficos.
- **Geração mais robusta em alguns Windows**: quando o Prompt de Comando do Windows roda um script de inicialização próprio, a extração da ISO não acontecia e o gerador dizia, por engano, que a ISO não era a certa. Agora isso não interfere mais; e se a extração parar sem motivo claro, a mensagem não acusa mais a ISO.
- Motor 0.1.10: na próxima geração o gerador refaz da etapa 3 sozinho (o disco extraído continua valendo).
### en
- **The opening video is back**: the attack on Rhodes, right after the throne scene, was skipped and the game went straight to the city. It now plays in full, with sound.
- **Fixed a cause of the game closing with error 0xC0000005** after a few minutes of play: in some scenes the engine read memory out of bounds while sending graphics.
- **More reliable generation on some Windows setups**: when the Windows Command Prompt runs a startup script of its own, the ISO was not extracted and the generator wrongly said the ISO was not the right one. This no longer interferes; and if the extraction stops for no clear reason, the message no longer blames the ISO.
- Engine 0.1.10: on the next generation the generator redoes it from step 3 on its own (the extracted disc is kept).
### es
- **El video de apertura vuelve a aparecer**: el ataque a Rodas, justo después de la escena del trono, se saltaba y el juego iba directo a la ciudad. Ahora se reproduce completo, con sonido.
- **Corregida una causa de cierre del juego con el error 0xC0000005** tras algunos minutos de juego: en ciertas escenas el motor leía memoria fuera de lugar al enviar los gráficos.
- **Generación más robusta en algunos Windows**: cuando el Símbolo del sistema de Windows ejecuta un script de inicio propio, la ISO no se extraía y el generador decía, por error, que la ISO no era la correcta. Eso ya no interfiere; y si la extracción se detiene sin un motivo claro, el mensaje ya no culpa a la ISO.
- Motor 0.1.10: en la próxima generación el generador rehace desde la etapa 3 solo (el disco extraído se mantiene).

## 12/11/2026 · 0.1.8
### pt
- **Mais fps em processadores de 6 núcleos** (como Core i5 e Ryzen 5) com outros programas abertos: o motor não prende mais as tarefas principais em núcleos fixos do processador. Num Core i5-11400F com outro jogo aberto, a média em jogo foi de ~34 para ~50 fps.
- Motor 0.1.9: na próxima geração o gerador refaz da etapa 3 sozinho (o disco extraído continua valendo).
### en
- **Higher fps on 6-core processors** (such as Core i5 and Ryzen 5) with other programs open: the engine no longer pins its main tasks to fixed cores. On a Core i5-11400F with another game open, the in-game average went from ~34 to ~50 fps.
- Engine 0.1.9: on the next generation the generator redoes it from step 3 on its own (the extracted disc is kept).
### es
- **Más fps en procesadores de 6 núcleos** (como Core i5 y Ryzen 5) con otros programas abiertos: el motor ya no fija sus tareas principales en núcleos fijos. En un Core i5-11400F con otro juego abierto, el promedio en el juego pasó de ~34 a ~50 fps.
- Motor 0.1.9: en la próxima generación el generador rehace desde la etapa 3 solo (el disco extraído se mantiene).

## 12/11/2026 · 0.1.7
### pt
- **O save fica gravado no disco**: a pasta do memory card não era criada na instalação, e o jogo salvava só enquanto estava aberto. Agora a pasta é criada e o save continua lá ao abrir o jogo de novo.
- Na primeira vez depois de uma atualização, uma mensagem avisa enquanto os gráficos são preparados (pode levar até 1 minuto).
- Motor 0.1.8: na próxima geração o gerador refaz da etapa 3 sozinho (o disco extraído continua valendo).
### en
- **Saves are kept on disk**: the memory card folder was not created on install, so the game only saved while it was open. The folder is now created and the save is still there when the game is opened again.
- The first time after an update, a message is shown while the graphics are being prepared (it may take up to 1 minute).
- Engine 0.1.8: on the next generation the generator redoes it from step 3 on its own (the extracted disc is kept).
### es
- **La partida queda grabada en el disco**: la carpeta de la memory card no se creaba en la instalación y el juego solo guardaba mientras estaba abierto. Ahora la carpeta se crea y la partida sigue ahí al abrir el juego de nuevo.
- La primera vez tras una actualización, un mensaje avisa mientras se preparan los gráficos (puede tardar hasta 1 minuto).
- Motor 0.1.8: en la próxima generación el generador rehace desde la etapa 3 solo (el disco extraído se mantiene).

## 07/11/2026 · 0.1.6
### pt
- **Memory card funciona**: o jogo agora encontra o cartão, salva nos altares e carrega o save. Também ficou mais rápido para ler e gravar.
- Motor 0.1.7: na próxima geração o gerador refaz da etapa 3 sozinho (o disco extraído continua valendo). O cartão é novo e é formatado na primeira vez.
### en
- **Memory card works**: the game now finds the card, saves at the altars and loads the save. Reading and writing are faster too.
- Engine 0.1.7: on the next generation the generator redoes it from step 3 on its own (the extracted disc is kept). The card is new and gets formatted the first time.
### es
- **La memory card funciona**: el juego ahora encuentra la tarjeta, guarda en los altares y carga la partida. También lee y graba más rápido.
- Motor 0.1.7: en la próxima generación el generador rehace desde la etapa 3 solo (el disco extraído se mantiene). La tarjeta es nueva y se formatea la primera vez.

## 06/11/2026 · 0.1.5
### pt
- **Mais fps pelo launcher**: aberto pelo launcher, o jogo deixava de usar a thread própria de desenho e esperava a placa de vídeo a cada quadro. Isso derrubava o fps, principalmente em placas de entrada (RTX 5060, por exemplo). Corrigido.
- **Sem faixa verde no fim da tela**: o efeito de brilho reduzia a imagem lendo uma linha de fora do quadro, o que deixava uma faixa esverdeada embaixo (mais visível em 21:9). Corrigido.
- Motor 0.1.2: na próxima geração o gerador refaz da etapa 3 sozinho (o disco extraído continua valendo).
### en
- **More fps from the launcher**: when opened from the launcher, the game stopped using its own drawing thread and waited for the graphics card every frame. That lowered the fps, mostly on entry-level cards (an RTX 5060, for example). Fixed.
- **No green strip at the bottom of the screen**: the glow effect shrank the picture reading a line from outside the frame, which left a greenish strip at the bottom (most visible in 21:9). Fixed.
- Engine 0.1.2: on the next generation the generator redoes it from step 3 on its own (the extracted disc is kept).
### es
- **Más fps desde el launcher**: abierto desde el launcher, el juego dejaba de usar su propio hilo de dibujo y esperaba a la tarjeta gráfica en cada fotograma. Eso bajaba los fps, sobre todo en tarjetas de entrada (una RTX 5060, por ejemplo). Corregido.
- **Sin franja verde al final de la pantalla**: el efecto de brillo reducía la imagen leyendo una línea de fuera del cuadro, lo que dejaba una franja verdosa abajo (más visible en 21:9). Corregido.
- Motor 0.1.2: en la próxima generación el generador rehace desde la etapa 3 solo (el disco extraído se mantiene).

## 06/11/2026 · 0.1.4
### pt
- **Motor próprio**: o gerador não baixa nem compila mais o PS2Recomp. Agora baixa o motor do port pronto (conferido pelo SHA-256) e compila só o código do jogo: mais rápido (de 5 a 30 minutos, conforme o PC), usa menos memória e não precisa de Git.
- **Sem Python**: as ferramentas do gerador agora vêm dentro do motor (um executável só). Basta instalar o Visual Studio Build Tools; Python e Git não são mais necessários.
- Quem já tinha o port gerado: a próxima geração apaga a pasta `ps2recomp\` antiga e refaz da etapa 3 sozinha.
### en
- **Own engine**: the generator no longer downloads or builds PS2Recomp. It now downloads the prebuilt port engine (checked by SHA-256) and builds only the game code: faster (5 to 30 minutes, depending on the PC), less memory, and no Git needed.
- **No Python**: the generator tools now ship inside the engine (a single executable). Only Visual Studio Build Tools is needed; Python and Git are no longer required.
- If you had already generated the port: the next generation deletes the old `ps2recomp\` folder and redoes it from step 3 on its own.
### es
- **Motor propio**: el generador ya no descarga ni compila PS2Recomp. Ahora descarga el motor del port ya listo (verificado por SHA-256) y compila solo el código del juego: más rápido (de 5 a 30 minutos, según el PC), usa menos memoria y no necesita Git.
- **Sin Python**: las herramientas del generador ahora vienen dentro del motor (un solo ejecutable). Solo hace falta Visual Studio Build Tools; ya no se necesitan Python ni Git.
- Si ya tenías el port generado: la próxima generación borra la carpeta `ps2recomp\` antigua y rehace desde la etapa 3 sola.

## 03/11/2026 · 0.1.3
### pt
- **Desempenho de volta**: a 0.1.2 deixava o jogo lento (menu a 20 fps e gameplay caindo para 30). Agora roda a 60 fps no menu e no gameplay.
- **Cutscenes sem travar nem cortar**: o vídeo chegava ao decodificador em dobro e misturado, o que travava a imagem e encerrava algumas cenas antes da hora.
- Atualizar o port pelo launcher não falha mais ("already exists in working directory"); o gerador também funciona em discos exFAT/FAT e baixa de novo o Git portátil se ele estiver danificado ou bloqueado.
- O ponteiro do mouse some sobre o jogo; com a janela do tamanho do monitor (ex.: 3840 × 2160 numa tela 4K), o jogo abre sem bordas em vez de sobrar para fora da tela.
### en
- **Performance is back**: 0.1.2 made the game slow (menu at 20 fps and gameplay dropping to 30). It now runs at 60 fps in the menu and in gameplay.
- **Cutscenes no longer freeze or cut short**: the video reached the decoder twice and interleaved, which froze the picture and ended some scenes early.
- Updating the port from the launcher no longer fails ("already exists in working directory"); the generator also works on exFAT/FAT drives and downloads the portable Git again if it is damaged or blocked.
- The mouse pointer hides over the game; with the window set to the monitor's size (e.g. 3840 × 2160 on a 4K screen), the game opens borderless instead of spilling off the screen.
### es
- **Vuelve el rendimiento**: la 0.1.2 dejaba el juego lento (menú a 20 fps y gameplay cayendo a 30). Ahora va a 60 fps en el menú y en el gameplay.
- **Cinemáticas sin congelarse ni cortarse**: el vídeo llegaba al decodificador duplicado y mezclado, lo que congelaba la imagen y terminaba algunas escenas antes de tiempo.
- Actualizar el port desde el launcher ya no falla ("already exists in working directory"); el generador también funciona en discos exFAT/FAT y vuelve a descargar el Git portátil si está dañado o bloqueado.
- El puntero del ratón se oculta sobre el juego; con la ventana del tamaño del monitor (p. ej. 3840 × 2160 en una pantalla 4K), el juego se abre sin bordes en lugar de salirse de la pantalla.

## 03/11/2026 · 0.1.2
### pt
- **Vídeos completos e com som**: as cutscenes em vídeo não são mais puladas e o som delas é tocado pelo próprio port.
- Efeitos que leem a profundidade (névoa, luz) agora saem como no PS2.
- **Controle novo**: Xbox (XInput), DualSense e DualShock 4 por USB ou Bluetooth e outros controles USB, com **vibração**. Corrigido o analógico que invertia no fim do curso.
- **Medidor de desempenho (F10)**: FPS, tempo de quadro, uso de CPU/GPU, temperaturas, VRAM e RAM.
- Imagem estável: o entrelaçamento agora junta os dois campos (antes a imagem tremia, principalmente em telas grandes/4K).
- A janela de depuração não abre mais junto com o jogo (F1 mostra, se precisar).
### en
- **Full videos with sound**: video cutscenes are no longer skipped and their sound is played by the port itself.
- Effects that read the depth buffer (fog, light) now look like on the PS2.
- **New controller support**: Xbox (XInput), DualSense and DualShock 4 over USB or Bluetooth and other USB pads, with **vibration**. Fixed the analog stick flipping at the end of its travel.
- **Performance meter (F10)**: FPS, frame time, CPU/GPU usage, temperatures, VRAM and RAM.
- Stable image: interlacing now weaves both fields (the image used to shake, mostly on big/4K screens).
- The debug window no longer opens with the game (F1 shows it if needed).
### es
- **Vídeos completos y con sonido**: las cinemáticas en vídeo ya no se saltan y su sonido lo reproduce el propio port.
- Los efectos que leen la profundidad (niebla, luz) ahora se ven como en PS2.
- **Mando nuevo**: Xbox (XInput), DualSense y DualShock 4 por USB o Bluetooth y otros mandos USB, con **vibración**. Corregido el analógico que se invertía al final del recorrido.
- **Medidor de rendimiento (F10)**: FPS, tiempo de cuadro, uso de CPU/GPU, temperaturas, VRAM y RAM.
- Imagen estable: el entrelazado ahora une los dos campos (antes la imagen temblaba, sobre todo en pantallas grandes/4K).
- La ventana de depuración ya no se abre con el juego (F1 la muestra si hace falta).

## 02/11/2026 · 0.1.1
### pt
- **Telas ultrawide**: a proporção da imagem agora tem 21:9, 32:9 e "Igual ao monitor", além de 4:3 e 16:9. Em tela larga o jogo abre o campo de visão para os lados, sem esticar o cenário nem os personagens, e não precisa ligar a opção WideScreen do jogo. O 21:9 se ajusta ao seu monitor (2560x1080, 3440x1440...). O HUD fica um pouco mais largo e os vídeos continuam em 4:3.
- Correções: imagens desenhadas de baixo para cima saem na posição certa; o gerador diz de que jogo é a ISO quando ela é de outro jogo ou versão.
### en
- **Ultrawide screens**: the aspect ratio now has 21:9, 32:9 and "Match monitor", besides 4:3 and 16:9. On a wide screen the game widens its field of view to the sides, without stretching the scenery or the characters, and no need to turn on the game's WideScreen option. 21:9 adjusts to your monitor (2560x1080, 3440x1440...). The HUD gets a bit wider and videos stay 4:3.
- Fixes: images drawn bottom to top now come out the right way; the generator tells which game an ISO belongs to when it is another game or version.
### es
- **Pantallas ultrawide**: la relación de aspecto ahora tiene 21:9, 32:9 e "Igual al monitor", además de 4:3 y 16:9. En pantalla ancha el juego amplía el campo de visión hacia los lados, sin estirar el escenario ni los personajes, y no hace falta activar la opción WideScreen del juego. El 21:9 se ajusta a tu monitor (2560x1080, 3440x1440...). El HUD queda un poco más ancho y los videos siguen en 4:3.
- Correcciones: las imágenes dibujadas de abajo hacia arriba salen en la posición correcta; el generador indica de qué juego es la ISO cuando es de otro juego o versión.

## 02/11/2026 · 0.1.0
### pt
- **Primeira versão (beta).** O gerador recompila o jogo a partir da sua ISO (versão americana, SCUS-97481).
- Roda do começo, com som, vídeos e a parte gráfica (GS) na placa de vídeo: 60 FPS em PCs atuais.
- **Modo 30 FPS** com o limitador do próprio jogo, para notebooks e PCs mais fracos.
- **Menu de opções** no launcher: modo de tela (janela ou tela cheia; F11 ou Alt+Enter alternam no jogo), tamanho da janela, escalonador (bilinear, AMD FSR 1 ou NVIDIA Image Scaling), nitidez, anti-serrilhamento FXAA, proporção 4:3/16:9 e predefinições Notebook / PC fraco, Equilibrado e Qualidade.
### en
- **First release (beta).** The generator rebuilds the game from your ISO (US release, SCUS-97481).
- It runs from the start, with sound, videos and the graphics chip (GS) on the GPU: 60 FPS on current PCs.
- **30 FPS mode** using the game's own limiter, for laptops and weaker PCs.
- **Options menu** in the launcher: display mode (window or fullscreen; F11 or Alt+Enter switch in game), window size, upscaler (bilinear, AMD FSR 1 or NVIDIA Image Scaling), sharpness, FXAA anti-aliasing, 4:3/16:9 aspect ratio and Laptop / weak PC, Balanced and Quality presets.
### es
- **Primera versión (beta).** El generador recompila el juego a partir de tu ISO (versión americana, SCUS-97481).
- Funciona desde el principio, con sonido, vídeos y el chip gráfico (GS) en la GPU: 60 FPS en PC actuales.
- **Modo 30 FPS** con el limitador del propio juego, para portátiles y PC más débiles.
- **Menú de opciones** en el launcher: modo de pantalla (ventana o pantalla completa; F11 o Alt+Enter alternan en el juego), tamaño de la ventana, escalador (bilineal, AMD FSR 1 o NVIDIA Image Scaling), nitidez, antialiasing FXAA, relación 4:3/16:9 y preajustes Portátil / PC débil, Equilibrado y Calidad.
