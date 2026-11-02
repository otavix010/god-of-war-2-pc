"""Monta o config.toml de um jogo de PS2: o TOML do analisador do PS2Recomp (funções da SDK
reconhecidas pela assinatura, MMIO, desempenho) + os limites de função do Ghidra (CSV) + a
união das funções da biblioteca das duas listas. Caminhos absolutos; saída em <jogo>\\gerado.
uso: python monta_config.py <pasta do jogo> <executável relativo à pasta>"""
import bisect, os
import re
import sys
import tomllib


def lista_stubs(toml_txt):
    d = tomllib.loads(toml_txt)
    return list(d.get('general', {}).get('stubs', []))


def elfs_embutidos(caminho):
    """Faixas (endereço virtual) de ELFs guardados dentro do executável, como os módulos do IOP (.IRX) que o jogo manda
    por SifLoadModuleBuffer: são dados, não código do EE. O Dirge of Cerberus tem um de 11 KB e o Ghidra desmontou
    83 "funções" nele (instruções inválidas e uma função de 88 KB)."""
    import struct
    d = open(caminho, 'rb').read()
    if d[:4] != b'\x7fELF':
        return []
    phoff, = struct.unpack_from('<I', d, 0x1c)
    phent, phnum = struct.unpack_from('<HH', d, 0x2a)
    segs = []
    for k in range(phnum):
        t, of, va, pa, fs = struct.unpack_from('<5I', d, phoff + k * phent)
        if t == 1 and fs:
            segs.append((of, va, fs))
    faixas = []
    i = d.find(b'\x7fELF', 1)
    while i >= 0:
        # só cabeçalho de verdade (32 bits, little-endian, MIPS, versão 1): não uma string "\x7fELF" de um carregador
        if d[i + 4:i + 7] != b'\x01\x01\x01' or d[i + 18:i + 20] != b'\x08\x00':
            i = d.find(b'\x7fELF', i + 1)
            continue
        try:
            shoff, = struct.unpack_from('<I', d, i + 0x20)
            shent, shnum = struct.unpack_from('<HH', d, i + 0x2e)
            phoff2, = struct.unpack_from('<I', d, i + 0x1c)
            phent2, phnum2 = struct.unpack_from('<HH', d, i + 0x2a)
            fim = max(shoff + shnum * shent, phoff2 + phnum2 * phent2)
            for k in range(shnum):
                nm, tp, fl, ad, of, sz = struct.unpack_from('<6I', d, i + shoff + k * shent)
                if tp != 8:  # SHT_NOBITS não ocupa o arquivo
                    fim = max(fim, of + sz)
            for k in range(phnum2):
                t, of, va, pa, fs = struct.unpack_from('<5I', d, i + phoff2 + k * phent2)
                fim = max(fim, of + fs)
        except struct.error:
            fim = 0
        for of, va, fs in segs:
            if of <= i < of + fs and 0 < fim < 16 << 20:
                faixas.append((va + i - of, va + min(i + fim, of + fs) - of))
        i = d.find(b'\x7fELF', i + 1)
    return faixas


def main():
    pasta, elf = sys.argv[1], sys.argv[2]
    embutidos = elfs_embutidos(os.path.join(pasta, elf))
    dentro_embutido = lambda a: any(x <= a < y for x, y in embutidos)
    if embutidos:
        print('  ~ %d ELFs embutidos (dados, não código): %s' % (len(embutidos), ' '.join('0x%X-0x%X' % f for f in embutidos)))
    an = open(os.path.join(pasta, 'analisador.toml'), encoding='utf-8').read()
    gh = open(os.path.join(pasta, 'ghidra_config.toml'), encoding='utf-8').read()
    s_an, s_gh = lista_stubs(an), lista_stubs(gh)
    # stubs_extra.txt: "handler@0xENDERECO  # motivo", um por linha (ex.: ret1 no player de vídeo
    # para pular FMV); ganha de qualquer outro nome no mesmo endereço
    s_ex = []
    extra_st = os.path.join(pasta, 'stubs_extra.txt')
    if os.path.exists(extra_st):
        for linha in open(extra_st, encoding='utf-8'):
            linha = linha.split('#', 1)[0].strip()
            if linha:
                s_ex.append(linha.split()[0])
    # um endereço só uma vez: o nome do analisador (base de símbolos da SDK) ganha
    por_end = {}
    sem_end = []
    for s in s_gh + s_an + s_ex:
        if '@' in s:
            por_end[s.split('@', 1)[1].lower()] = s
        elif s not in sem_end:
            sem_end.append(s)
    stubs = sem_end + sorted(por_end.values(), key=lambda s: int(s.split('@', 1)[1], 16))
    # as funções de double da libm (sem o "f") NÃO podem virar stub: os do runtime são as versões de
    # float (argumentos em f12/f14, resultado em f0), e no toolchain do PS2 o double é ponto flutuante
    # por software em registrador de 64 bits (a0/a1 -> v0). Com o stub, o pow do Spawn devolvia lixo:
    # a tabela de gama saturava em 255 e todas as paletas ficavam brancas. Roda o código do jogo.
    LIBM_DOUBLE = {'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'atan2', 'sinh', 'cosh', 'tanh', 'pow',
                   'exp', 'log', 'log10', 'sqrt', 'floor', 'ceil', 'fabs', 'fmod', 'ldexp', 'frexp', 'modf',
                   'hypot', 'round', 'trunc'}
    tirados = [s for s in stubs if s.split('@', 1)[0] in LIBM_DOUBLE]
    stubs = [s for s in stubs if s.split('@', 1)[0] not in LIBM_DOUBLE]
    if tirados:
        print('  - %d stubs de double da libm tirados (roda o código do jogo): %s' % (len(tirados), ' '.join(s.split('@')[0] for s in tirados)))
    # stubs_tirar.txt: nomes (um por linha, "# comentário" ignorado) de stubs que voltam a rodar o
    # código do jogo. O 10kB tem um gerenciador de memória próprio que pergunta o tamanho dos blocos
    # ao alocador; com a família malloc trocada pelo heap do runtime, o tamanho vinha de um cabeçalho
    # inexistente e um memset de crescimento de vetor apagava objetos. A newlib do jogo usa o sbrk dele.
    arq_tirar = os.path.join(pasta, 'stubs_tirar.txt')
    if os.path.exists(arq_tirar):
        tirar = set()
        for linha in open(arq_tirar, encoding='utf-8'):
            linha = linha.split('#', 1)[0].strip()
            if linha:
                tirar.add(linha)
        fora = [s for s in stubs if s.split('@', 1)[0] in tirar]
        stubs = [s for s in stubs if s.split('@', 1)[0] not in tirar]
        if fora:
            print('  - %d stubs tirados por stubs_tirar.txt (roda o código do jogo): %s' % (len(fora), ' '.join(s.split('@')[0] for s in fora)))

    def troca(chave, valor, txt):
        novo, n = re.subn(r'(?m)^%s\s*=.*$' % chave, '%s = %s' % (chave, valor), txt, count=1)
        if n != 1:
            raise SystemExit('chave %s não encontrada' % chave)
        return novo

    q = lambda p: '"' + p.replace('\\', '/') + '"'
    an = troca('input', q(os.path.join(pasta, elf)), an)
    an = troca('output', q(os.path.join(pasta, 'gerado')), an)
    # CSV do Ghidra limpo: função com um pedaço distante (salto de cauda / bloco solto) vem com End
    # muito além do tamanho real (10kB: FUN_00576448, End +1,3 MB para 60 bytes) e o tradutor gerava
    # 107 MB de C++ numa função só (9,7 GB de RAM para compilar). End passa a Start + Size nesses casos.
    # Também: nenhuma função pode passar por cima do endereço de um stub. O 10kB tinha FUN_00670D28
    # (3780 bytes) engolindo o _calloc_r da newlib; o "j _calloc_r" virava rótulo interno, rodava o
    # código original em vez do stub e lia o cabeçalho de um bloco do malloc do runtime → memset(-4).
    limpo = os.path.join(pasta, 'ghidra_funcoes_ok.csv')
    corrigidas = []
    cortadas_stub = []
    end_stubs = sorted(int(s.split('@', 1)[1], 16) for s in stubs if '@' in s)
    nome_stub = {int(s.split('@', 1)[1], 16): s.split('@', 1)[0] for s in stubs if '@' in s}
    extras_stub = []
    tiradas_emb = []
    tiradas_grandes = []
    inicios_csv = set()
    with open(os.path.join(pasta, 'ghidra_funcoes.csv'), encoding='utf-8') as ent:
        for linha in ent:
            c = linha.split(',')
            if len(c) > 1 and c[1].startswith('0x'):
                inicios_csv.add(int(c[1], 16))
    with open(os.path.join(pasta, 'ghidra_funcoes.csv'), encoding='utf-8') as ent, \
            open(limpo, 'w', encoding='utf-8', newline='\n') as sai:
        for i, linha in enumerate(ent):
            partes = linha.rstrip('\r\n').split(',')
            if i and len(partes) >= 4 and partes[1].startswith('0x') and partes[3].strip().isdigit():
                ini, fim, tam = int(partes[1], 16), int(partes[2], 16), int(partes[3])
                if dentro_embutido(ini):
                    tiradas_emb.append(partes[0])
                    continue
                # "entry_" do Ghidra (criada a partir de um ponteiro, sem símbolo) com mais de 64 KB: é dado desmontado.
                # Onimusha 3: entry_00508340 (89 KB, até o fim exato do segmento) e entry_004fb930 (51 KB… essa fica)
                # levaram um cl.exe a 18 GB. A maior função de verdade dos jogos testados tem 34 KB
                if partes[0].startswith('entry_') and fim - ini > 0x10000:
                    tiradas_grandes.append('%s (%d KB)' % (partes[0], (fim - ini) // 1024))
                    continue
                for x, y in embutidos:
                    if ini < x < fim:
                        fim = x
                        partes[2] = '0x%08X' % fim
                if tam > 0 and fim - ini > 4 * tam + 4096:
                    corrigidas.append('%s (%d→%d bytes)' % (partes[0], fim - ini, tam))
                    fim = ini + tam
                    partes[2] = '0x%08X' % fim
                i_st = bisect.bisect_right(end_stubs, ini)
                if i_st < len(end_stubs) and end_stubs[i_st] < fim:
                    partes[2] = '0x%08X' % end_stubs[i_st]
                    cortadas_stub.append('%s→0x%X' % (partes[0], end_stubs[i_st]))
                    # o stub também precisa de uma linha própria no CSV, senão o endereço dele não vira
                    # função e o salto cai em missing-target (10kB: sceVu0CopyMatrix no meio de FUN_005ebf40)
                    ini_st = end_stubs[i_st]
                    fim_st = end_stubs[i_st + 1] if i_st + 1 < len(end_stubs) and end_stubs[i_st + 1] < fim else fim
                    extras_stub.append('%s,0x%08X,0x%08X,%d' % (nome_stub[ini_st], ini_st, fim_st, fim_st - ini_st))
            sai.write(','.join(partes) + '\n')
        inicios = set()
        for e in extras_stub:
            a = int(e.split(',')[1], 16)
            if a not in inicios and a not in inicios_csv:
                inicios.add(a)
                sai.write(e + '\n')
    if tiradas_emb:
        print('  - %d funções do Ghidra dentro de ELFs embutidos tiradas' % len(tiradas_emb))
    if tiradas_grandes:
        print('  - %d "entry_" do Ghidra com mais de 64 KB tiradas (dado desmontado): %s' % (len(tiradas_grandes), ' '.join(tiradas_grandes)))
    if corrigidas:
        print('  ~ %d funções com o fim inflado no CSV do Ghidra: %s' % (len(corrigidas), '; '.join(corrigidas)))
    if cortadas_stub:
        print('  ~ %d funções cortadas no início de um stub: %s' % (len(cortadas_stub), ' '.join(cortadas_stub[:12]) + (' …' if len(cortadas_stub) > 12 else '')))
    an = troca('ghidra_output', q(limpo), an)
    # o bloco stubs = [ ... ] do [general]
    m = re.search(r'(?ms)^stubs\s*=\s*\[.*?^\]', an)
    if not m:
        raise SystemExit('bloco stubs não encontrado')
    bloco = 'stubs = [\n' + ''.join('  "%s",\n' % s for s in stubs) + ']'
    an = an[:m.start()] + bloco + an[m.end():]
    # entradas_extra.txt: um endereço por linha (alvos de chamadas indiretas que caem no meio de
    # uma função do Ghidra e precisam de entrada própria); "# comentário" é ignorado
    extra = os.path.join(pasta, 'entradas_extra.txt')
    ends = []
    if os.path.exists(extra):
        for linha in open(extra, encoding='utf-8'):
            linha = linha.split('#', 1)[0].strip()
            if linha:
                ends.append(int(linha.split()[0], 16))
    # funções que o analisador achou sozinho (sub_XXXXXXXX, p.ex. na lista de desempenho) e que o
    # Ghidra não criou: sem entrada própria viram "guest-branch:missing-target" (Ghost Rider 0x2C8080)
    inicios_gh = set()
    fim_gh = 0
    for linha in open(os.path.join(pasta, 'ghidra_funcoes.csv'), encoding='utf-8'):
        partes = linha.split(',')
        if len(partes) > 2 and partes[1].startswith('0x'):
            inicios_gh.add(int(partes[1], 16))
            if partes[2].startswith('0x'):
                fim_gh = max(fim_gh, int(partes[2], 16))
    ja = set(ends) | set(int(e, 16) for e in re.findall(r'@0x([0-9A-Fa-f]+)', an))
    subs = sorted(set(int(s, 16) for s in re.findall(r'\bsub_([0-9A-F]{8})\b', an)) - inicios_gh - ja)
    # Otavix (02/11): nada de "função" do analisador que iria mais de 64 KB até o próximo início conhecido: é dado.
    # No Blade II ele "achou" funções em 0x25C310/0x404040 (área de dados, numa seção executável só) e cada uma virou
    # 1 MB de dado traduzido como código (um cl.exe com 19 GB). A maior função de verdade dos jogos testados tem 34 KB
    inicios = sorted(inicios_gh | set(ends) | set(subs))
    fora = []
    for s in subs:
        i = bisect.bisect_right(inicios, s)
        prox = inicios[i] if i < len(inicios) else max(fim_gh, s)
        if prox - s > 0x10000:
            fora.append(s)
    if fora:
        print('  - %d funções do analisador ignoradas (mais de 64 KB até o próximo início, é dado): %s' % (
            len(fora), ' '.join('0x%X' % s for s in fora)))
        subs = [s for s in subs if s not in fora]
    if subs:
        print('  + %d funções só do analisador: %s' % (len(subs), ' '.join('0x%X' % s for s in subs)))
        ends += subs
    if embutidos:
        n = len(ends)
        ends = [e for e in ends if not dentro_embutido(e)]
        if len(ends) < n:
            print('  - %d entradas dentro de ELFs embutidos tiradas' % (n - len(ends)))
    if ends:
        m = re.search(r'(?ms)^entry_points\s*=\s*\[', an)
        if not m:
            raise SystemExit('bloco entry_points não encontrado')
        novos = ''.join('  "otavix_%08X@0x%08X",\n' % (e, e) for e in ends)
        an = an[:m.end()] + '\n' + novos + an[m.end():].lstrip('\n')
        print('  + %d entradas extras' % len(ends))
    # Otavix (30/10): o analisador troca por NOP toda "sw" seguida de j/jal cujo endereço cai em "código" — e, sem tabela
    # de seções (God of War), o segmento inteiro conta como código, .data/.bss inclusive. Eram 73 escritas normais em
    # variáveis globais apagadas (ex.: 0x26c808, o "pendente" da fila do 989snd: os callbacks dos pedidos nunca rodavam
    # e o carregador travava). Código automodificável de verdade é raro e o runtime não depende disso: tira todos.
    automod = re.findall(r'(?m)^\s*\{[^}\n]*\}\s*,?\s*# Potential self-modifying code\s*$\n?', an)
    if automod:
        an = re.sub(r'(?m)^\s*\{[^}\n]*\}\s*,?\s*# Potential self-modifying code\s*$\n?', '', an)
        print('  - %d NOPs de "código automodificável" do analisador tirados (eram escritas em dados)' % len(automod))
    # Otavix (02/11): remendos.txt = "<end hex> <instrução hex>  # comentário" por linha, trocados antes da tradução
    # (Spawn: a constante 16/9 do modo widescreen vira leitura da palavra 0x7FF00 que o runtime grava = proporção da tela)
    arq_rem = os.path.join(pasta, 'remendos.txt')
    if os.path.exists(arq_rem):
        rem = []
        for linha in open(arq_rem, encoding='utf-8-sig'):
            linha = linha.split('#', 1)[0].strip()
            if linha:
                e, v = linha.split()[:2]
                rem.append('  { address = "0x%08X", value = "0x%08X" },\n' % (int(e, 16), int(v, 16)))
        m = re.search(r'(?ms)^\[patches\]\s*\ninstructions\s*=\s*\[\s*\n?', an)
        if m:
            an = an[:m.end()] + ''.join(rem) + an[m.end():]
        else:
            an = an.rstrip('\n') + '\n\n[patches]\ninstructions = [\n' + ''.join(rem) + ']\n'
        print('  + %d remendos de instrução' % len(rem))
    tomllib.loads(an)   # confere que continua TOML válido
    open(os.path.join(pasta, 'config.toml'), 'w', encoding='utf-8', newline='\n').write(an)
    print('%s: %d stubs (analisador %d, ghidra %d)' % (os.path.basename(pasta), len(stubs), len(s_an), len(s_gh)))


if __name__ == '__main__':
    main()
