"""Extrai uma imagem de DVD/CD de PS2 (ISO9660, setores de 2048 bytes) para uma pasta, sem
programas externos. Os nomes perdem o ";1" do ISO9660. Arquivos que já existem com o mesmo
tamanho são pulados (dá para rodar de novo depois de uma interrupção).
uso: python extrai_iso.py <imagem.iso> <pasta de destino>"""
import os
import struct
import sys

SETOR = 2048


def le(f, setor, n=SETOR):
    f.seek(setor * SETOR)
    return f.read(n)


def registros(f, setor, tamanho):
    """registros de diretório (ignorando . e ..) de um diretório que começa em <setor>"""
    dados = le(f, setor, tamanho)
    i = 0
    while i < len(dados):
        n = dados[i]
        if n == 0:
            # o resto do setor está vazio: pula para o próximo setor
            i = (i // SETOR + 1) * SETOR
            continue
        ext = struct.unpack_from('<I', dados, i + 2)[0]
        tam = struct.unpack_from('<I', dados, i + 10)[0]
        flags = dados[i + 25]
        ln = dados[i + 32]
        nome = dados[i + 33:i + 33 + ln]
        i += n
        if nome in (b'\x00', b'\x01'):
            continue
        nome = nome.decode('latin-1').split(';', 1)[0].rstrip('.')
        yield nome, ext, tam, bool(flags & 2)


def extrai(f, setor, tamanho, destino, total):
    os.makedirs(destino, exist_ok=True)
    for nome, ext, tam, eh_dir in registros(f, setor, tamanho):
        alvo = os.path.join(destino, nome)
        if eh_dir:
            extrai(f, ext, tam, alvo, total)
            continue
        if os.path.exists(alvo) and os.path.getsize(alvo) == tam:
            total[0] += tam
            continue
        with open(alvo, 'wb') as s:
            f.seek(ext * SETOR)
            falta = tam
            while falta:
                bloco = f.read(min(falta, 8 << 20))
                if not bloco:
                    raise SystemExit('imagem truncada em %s' % alvo)
                s.write(bloco)
                falta -= len(bloco)
        total[0] += tam
        print('  %s (%.1f MB)' % (os.path.relpath(alvo, total[1]), tam / 1048576), flush=True)


def main():
    iso, destino = sys.argv[1], sys.argv[2]
    with open(iso, 'rb') as f:
        pvd = le(f, 16)
        if pvd[1:6] != b'CD001' or pvd[0] != 1:
            raise SystemExit('não é uma imagem ISO9660 (descritor primário não achado no setor 16)')
        raiz = pvd[156:156 + 34]
        ext = struct.unpack_from('<I', raiz, 2)[0]
        tam = struct.unpack_from('<I', raiz, 10)[0]
        total = [0, os.path.abspath(destino)]
        extrai(f, ext, tam, os.path.abspath(destino), total)
    print('extraído: %.1f MB em %s' % (total[0] / 1048576, destino))


if __name__ == '__main__':
    main()
