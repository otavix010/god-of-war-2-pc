# Microprogramas do VU1 a partir do ELF do próprio usuário (nada do jogo vai no repositório).
#
#   receita: python -I extrai_vu1.py receita <pasta do dump> <ELF> <extras.txt>[,<extras2.txt>...] <receita.json>
#            (do nosso lado: descreve cada estado da memória de código do VU1 como segmentos do ELF — endereço no VU,
#            offset no ELF, tamanho — mais os pcs de início, contagens e entradas extras. Só identificação.)
#   extrai:  python -I extrai_vu1.py extrai <receita.json> <ELF> <pasta de saída>
#            (na máquina do usuário: confere o SHA-1 do ELF, monta os estados, confere o SHA-1 de cada um e grava a
#            pasta no formato do dump — vu1_<estado>.bin, inicios.txt, contagem.txt, extras.txt — para o vu1_tradutor.py)
import glob
import hashlib
import json
import os
import sys

TAM = 16384


def segmenta(st, elf, indice):
    segs, a = [], 0
    while a < len(st):
        par = st[a:a + 8]
        if par == b'\0' * 8:
            a += 8
            continue
        melhor = (0, None)
        for off in (indice.get(st[a:a + 32], []) if a + 32 <= len(st) else []):
            n = 0
            while a + n + 8 <= len(st) and off + n + 8 <= len(elf) and st[a + n:a + n + 8] == elf[off + n:off + n + 8]:
                n += 8
            if n > melhor[0]:
                melhor = (n, off)
        if not melhor[0]:
            i = elf.find(par)
            while i >= 0 and i % 8:
                i = elf.find(par, i + 1)
            if i >= 0:
                n = 8
                while a + n + 8 <= len(st) and i + n + 8 <= len(elf) and st[a + n:a + n + 8] == elf[i + n:i + n + 8]:
                    n += 8
                melhor = (n, i)
        if not melhor[0]:
            # par que o próprio jogo monta enquanto roda (por exemplo um IADDIU com uma constante antes de um
            # programa do ELF): não existe no executável, vai literal (8 bytes, formato 2)
            if segs and isinstance(segs[-1][1], str) and segs[-1][0] + len(segs[-1][1]) // 2 == a:
                segs[-1][1] += par.hex()
            else:
                segs.append([a, par.hex()])
            a += 8
            continue
        segs.append([a, melhor[1], melhor[0]])
        a += melhor[0]
    return segs


def receita(dump, elf_p, extras_ps, saida):
    elf = open(elf_p, 'rb').read()
    indice = {}
    for off in range(0, len(elf) - 32 + 1, 8):
        w = elf[off:off + 32]
        if w.count(0) <= 24:
            indice.setdefault(w, []).append(off)
    r = {'formato': 2, 'elf_sha1': hashlib.sha1(elf).hexdigest(), 'tamanho': TAM, 'estados': {}}
    for p in sorted(glob.glob(os.path.join(dump, 'vu1_*.bin'))):
        h = os.path.basename(p)[4:20]
        st = open(p, 'rb').read()
        r['estados'][h] = {'sha1': hashlib.sha1(st).hexdigest(), 'segmentos': segmenta(st, elf, indice)}
    r['inicios'] = [l.split() for l in open(os.path.join(dump, 'inicios.txt')) if l.strip()]
    cont = os.path.join(dump, 'contagem.txt')
    r['contagem'] = [l.split() for l in open(cont) if l.strip()] if os.path.exists(cont) else []
    ex = set()
    for e in extras_ps.split(','):
        for l in open(e):
            if l.strip():
                ex.add(tuple(l.split()))
    r['extras'] = sorted(ex)
    json.dump(r, open(saida, 'w'), indent=0)
    print('receita: %d estados, %d segmentos, %d inícios, %d extras -> %s' % (
        len(r['estados']), sum(len(e['segmentos']) for e in r['estados'].values()), len(r['inicios']), len(r['extras']), saida))


def extrai(rec_p, elf_p, saida):
    r = json.load(open(rec_p))
    elf = open(elf_p, 'rb').read()
    if hashlib.sha1(elf).hexdigest() != r['elf_sha1']:
        raise SystemExit('ELF diferente do esperado (SHA-1 %s); a receita do VU1 é para %s' % (hashlib.sha1(elf).hexdigest(), r['elf_sha1']))
    os.makedirs(saida, exist_ok=True)
    for h, e in r['estados'].items():
        st = bytearray(r.get('tamanho', TAM))
        for s in e['segmentos']:
            if isinstance(s[1], str):
                b = bytes.fromhex(s[1])
                st[s[0]:s[0] + len(b)] = b
            else:
                a, off, n = s
                st[a:a + n] = elf[off:off + n]
        if hashlib.sha1(st).hexdigest() != e['sha1']:
            raise SystemExit('estado %s não confere' % h)
        open(os.path.join(saida, 'vu1_%s.bin' % h), 'wb').write(st)
    with open(os.path.join(saida, 'inicios.txt'), 'w') as f:
        f.writelines('%s %s\n' % tuple(l) for l in r['inicios'])
    with open(os.path.join(saida, 'contagem.txt'), 'w') as f:
        f.writelines('%s %s %s\n' % tuple(l) for l in r['contagem'])
    with open(os.path.join(saida, 'extras.txt'), 'w') as f:
        f.writelines('%s %s\n' % tuple(l) for l in r['extras'])
    print('extraídos %d estados em %s' % (len(r['estados']), saida))


if __name__ == '__main__':
    if sys.argv[1] == 'receita':
        receita(*sys.argv[2:6])
    elif sys.argv[1] == 'extrai':
        extrai(*sys.argv[2:5])
    else:
        raise SystemExit(__doc__)
