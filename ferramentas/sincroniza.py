"""Copia o C++ gerado para o runner do PS2Recomp só onde mudou (o ninja recompila pelo
horário do arquivo: copiar tudo de novo a cada recompilação refazia dezenas de milhares de
arquivos). Apaga do runner os .cpp que não existem mais no gerado.
uso: python sincroniza.py <pasta gerado> <pasta runner> <pasta include> [pasta overrides]"""
import filecmp
import os
import shutil
import sys


def main():
    gerado, runner, include = sys.argv[1:4]
    overrides = sys.argv[4] if len(sys.argv) > 4 else ''
    novos = {}
    for pasta in [gerado] + ([overrides] if overrides and os.path.isdir(overrides) else []):
        for n in os.listdir(pasta):
            if n.endswith('.cpp'):
                novos[n] = os.path.join(pasta, n)
    copiados = apagados = 0
    for n in os.listdir(runner):
        if n.endswith('.cpp') and n not in novos:
            os.remove(os.path.join(runner, n))
            apagados += 1
    for n, src in novos.items():
        dst = os.path.join(runner, n)
        if not os.path.exists(dst) or not filecmp.cmp(src, dst, shallow=False):
            shutil.copyfile(src, dst)
            copiados += 1
    for n in os.listdir(gerado):
        if n.endswith('.h'):
            src, dst = os.path.join(gerado, n), os.path.join(include, n)
            if not os.path.exists(dst) or not filecmp.cmp(src, dst, shallow=False):
                shutil.copyfile(src, dst)
                copiados += 1
    print('sincroniza: %d copiados, %d apagados, %d no total' % (copiados, apagados, len(novos)))


if __name__ == '__main__':
    main()
