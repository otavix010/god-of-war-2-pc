# Launcher de compilação (CXX_COMPILER_LAUNCHER do ps2_runtime): os programas do VU1 traduzidos
# (vu1_programas_*.cpp) vão para o clang-cl com aliasing estrito (o MSVC supõe que qualquer escrita em s.vf pode
# mudar os campos do vu1n::Ctx e relê/regrava x.c etc. a cada par) e SEM contração em FMA (mesmo arredondamento).
# O resto passa direto para o cl.exe. O "Note: including file:" do clang vira o prefixo do cl (rules.ninja) para o
# ninja continuar vendo as dependências. PS2X_CLANG_VU1=0 no ambiente da compilação desliga.
import os
import subprocess
import sys

# clang-cl do próprio Visual Studio (componente "C++ Clang tools"): VCINSTALLDIR vem do vcvars64.bat
CLANG = os.path.join(os.environ.get('VCINSTALLDIR', ''), 'Tools', 'Llvm', 'x64', 'bin', 'clang-cl.exe')
args = sys.argv[1:]

if os.environ.get('PS2X_CLANG_VU1', '1') != '0' and os.path.exists(CLANG) and any('vu1_programas_' in a and a.endswith('.cpp') for a in args):
    prefixo = b'Note: including file:'
    for raiz in ('CMakeFiles/rules.ninja', 'rules.ninja'):
        if os.path.exists(raiz):
            for linha in open(raiz, 'rb'):
                if linha.startswith(b'msvc_deps_prefix = '):
                    prefixo = linha[len(b'msvc_deps_prefix = '):].rstrip(b'\r\n')
                    break
            break
    cmd = [CLANG] + args[1:] + ['/clang:-fstrict-aliasing', '/clang:-ffp-contract=off']
    # Otavix (02/11): /O1 (tamanho) por padrão: o código gerado do VU1 é grande e linear e, num cache pequeno (notebook
    # i5, L3 de 8 MB), o tamanho pesa: GoW 1 4,97/5,47 -> 4,69/5,24 ns/ciclo (-5%); no PC (X3D) +2,5% (60 qps igual).
    # PS2X_CLANG_VU1_EXTRA="..." troca as flags ("" = sem /O1)
    cmd += os.environ.get('PS2X_CLANG_VU1_EXTRA', '/O1').split()
    p = subprocess.run(cmd, capture_output=True)
    out = p.stdout.replace(b'Note: including file:', prefixo)
    sys.stdout.buffer.write(out)
    sys.stdout.buffer.flush()
    sys.stderr.buffer.write(p.stderr)
    sys.exit(p.returncode)

sys.exit(subprocess.run(args).returncode)
