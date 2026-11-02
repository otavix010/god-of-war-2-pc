# Tradutor AOT dos microprogramas do VU1: lê um ou mais dumps (patch_vu1_dump.py, PS2X_VU1_DUMP) e gera C++ com
# uma função por programa (vu1n::Ctx, ver vu1_nativo/ps2_vu1_nativo.h) mais a tabela hash -> função.
# Semântica: a do interpretador do ps2xRuntime (ver VU1_TRADUTOR.md). Programa = pares alcançáveis a partir do pc
# inicial (vu1_comum.programa); o runtime calcula o mesmo hash e escolhe a função.
# uso: python vu1_tradutor.py <saida.cpp> <pasta de dump> [<pasta de dump> ...] [--min-exec N]
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vu1_comum as vc  # noqa: E402

# PS2X_VU1_SEM_FILA=0 na geração desliga o atalho das flags (programas sem leitura de MAC/status)
SEM_FILA = os.environ.get("PS2X_VU1_SEM_FILA", "1") != "0"
# PS2X_VU1_PRONTOS=0 na geração mantém todas as travas de prontidão
PRONTOS = os.environ.get("PS2X_VU1_PRONTOS", "1") != "0"
# PS2X_VU1_CONTA=1 na geração: conta execuções por (programa, par) (diagnóstico; ver vu1n::contaPar)
CONTA = os.environ.get("PS2X_VU1_CONTA", "0") == "1"
# PS2X_VU1_QUENTES=<hash,hash,...>: programas com fmac/opm em linha (os mais executados; ver vu1_conta.txt)
QUENTES_TODOS = os.environ.get("PS2X_VU1_QUENTES", "") == "todos"  # todos os programas em linha (compilar com clang-cl)
QUENTES = set() if QUENTES_TODOS else {int(h, 16) for h in os.environ.get("PS2X_VU1_QUENTES", "").split(",") if h.strip()}
# PS2X_VU1_ORCAMENTO_PAR=1 na geração: confere o orçamento de ciclos em todo par (antes); padrão: só nas cabeças de
# laço (alvos de desvio para trás) e no despacho — cada par anda >= 1 ciclo, então nenhum laço escapa; devolver
# alguns pares depois do limite exato é seguro (o estado fica coerente e o interpretador segue dali). Código bem
# menor (o programa principal do Spawn tinha 165 KB, ~270 bytes por par, e o perfil era plano = limite de front-end).
ORCAMENTO_PAR = os.environ.get("PS2X_VU1_ORCAMENTO_PAR", "0") == "1"
# PS2X_VU1_PRONTOS_VIVOS=0 na geração: grava o pronto de toda escrita de VF/VI (antes); padrão: só dos termos que alguma
# trava confere (o resto vira x.fimV, esperado pelo flush) — menos escritas na memória por par
PRONTOS_VIVOS = os.environ.get("PS2X_VU1_PRONTOS_VIVOS", "1") != "0"
# PS2X_VU1_FIMV_TODOS=1 na geração: grava x.fimV em todo par (antes); padrão: o fimV só é lido pelo flush (fim do
# programa), então um par sem desvio que cai direto no seguinte não grava se o seguinte já garante latência >= a dele - 1
FIMV_TODOS = os.environ.get("PS2X_VU1_FIMV_TODOS", "0") == "1"

# PS2X_VU1_NORM=0 na geração: sem a análise de normalização (fmac/opm normalizam todo operando; despacho com todos os
# pares, como antes)
NORM = os.environ.get("PS2X_VU1_NORM", "1") != "0"
# PS2X_VU1_LOCAL=0 na geração: o programa trabalha direto no VU1State do interpretador (antes); padrão: cópia local
LOCAL = os.environ.get("PS2X_VU1_LOCAL", "1") != "0"

LANES = ((8, 0), (4, 1), (2, 2), (1, 3))


def f32_norm_bits(b):
    e = (b >> 23) & 0xFF
    if e == 0:
        b &= 0x80000000
    elif e == 0xFF:
        b = (b & 0x80000000) | 0x7F7FFFFF
    return b


class Gerador:
    def __init__(self, code, pares, hp, inicio, base=None, entradas=None):
        self.code = code
        self.pares = pares
        self.base = set(pares) if base is None else set(base)  # alcance só do início (o resto vem das extras)
        self.conj = set(pares)
        self.hp = hp
        self.inicio = inicio
        # Otavix (31/10): outros pcs com o MESMO programa (mesmo conjunto alcançável): o runtime escolhe esta função
        # para eles também, então o despacho precisa aceitá-los como entrada (antes devolvia sem andar)
        self.entradas = {inicio & vc.MASCARA_PC} | {e & vc.MASCARA_PC for e in (entradas or ())}
        self.p = {a: vc.Par(code, a) for a in pares}
        # sem leitura de MAC/status no programa: o FMAC não passa pela fila de flags (vu1n::comitaRapido no fim)
        leitores = ('FSEQ', 'FSAND', 'FSOR', 'FMEQ', 'FMAND', 'FMOR', 'FSSET')
        self.sem_fila = SEM_FILA and not any((not q.ibit) and q.nl in leitores for q in self.p.values())
        # com leitura só de MAC (FMxx, sem FSxx/FSSET): FMACs cujo MAC nunca pode ser lido viram "só sticky"
        self.mortos = set()
        self.rem = self.analisa_prontos() if PRONTOS else None
        if SEM_FILA and not self.sem_fila and not any((not q.ibit) and q.nl in ('FSEQ', 'FSAND', 'FSOR', 'FSSET')
                                                       for q in self.p.values()):
            self.mortos = self.analisa_mac()
        # Otavix (normalização): destinos aceitos pelo despacho dinâmico (JR/JALR/desvio pendente); outro pc devolve
        M0 = vc.MASCARA_PC
        self.alvos_din = set(self.entradas) | {a for a in self.p if a not in self.base}
        for a0, q0 in self.p.items():
            d0 = q0.desvio()
            if d0 in vc.DESVIOS_DIRETOS:
                self.alvos_din.add(q0.alvo())
            if d0 == 'BAL':
                self.alvos_din.add((a0 + 16) & M0)
        self.norm = self.analisa_norm() if NORM else None
        # Otavix (bkReg): o par só precisa zerar x.bkReg se algum predecessor pode tê-lo gravado (desvio logo após
        # escrita de VI por IALU/LQI/...) ou se é destino dinâmico; nos outros ele já é 0 (indução sobre a execução)
        self.precisa_bk = None
        if NORM:
            grava = {a2 for a2, q2 in self.p.items() if q2.ul.atrasa_desvio and q2.ul.vi_escreve}
            self.precisa_bk = set(self.alvos_din)
            pend = [('n', a2) for a2 in self.p]
            vistos = set()
            while pend:
                no = pend.pop()
                if no in vistos:
                    continue
                vistos.add(no)
                for su in self.succs(no):
                    if isinstance(su, tuple):
                        if no[1] in grava:
                            self.precisa_bk.add(su[1])
                        pend.append(su)
        # cabeças de laço: alvos de desvio direto/BAL para trás e o par seguinte quando o pc dá a volta na memória
        self.cabecas = set()
        M = vc.MASCARA_PC
        for a, q in self.p.items():
            d = q.desvio()
            if d in vc.DESVIOS_DIRETOS or d == 'BAL':
                t = q.alvo()
                if t <= a:
                    self.cabecas.add(t)
            prox = (a + 8) & M
            if prox <= a:
                self.cabecas.add(prox)
        # termos de prontidão conferidos por alguma trava do programa (os outros não precisam ser gravados)
        self.vivos = None
        if PRONTOS_VIVOS:
            self.vivos = set()
            for a in self.p:
                for fin in (False, True):
                    self.vivos.update(self.termos_trava(a, fin))
        self.pula_fimv = self.analisa_fimv() if (self.vivos is not None and not FIMV_TODOS) else set()
        self.saida = []
        self.finais = set()   # pares que precisam da variante "último par" (depois de um E-bit)
        self.fin_din = False  # algum E-bit com desvio pendente (destino dinâmico)

    def lat_morta(self, p):
        """Maior latência das escritas de VF do par que nenhuma trava confere (vão para x.fimV)."""
        m = 0
        for t, lat in self.escritas_prontas(p):
            if t.startswith('x.vfR') and t not in self.vivos:
                m = max(m, lat)
        return m

    def analisa_fimv(self):
        """Pares (não finais) que dispensam a escrita do fimV: sem desvio nem E-bit, caem no par seguinte do
        programa, e o seguinte garante fimV >= c0 + lat - 1 (cada par anda >= 1 ciclo; as travas só adiantam o
        relógio). Devolver ao interpretador não lê o fimV."""
        M = vc.MASCARA_PC
        cobre = {}

        def liga(a):
            q = self.p[a]
            prox = (a + 8) & M
            if q.ebit or self.checa_desvio(a) or prox not in self.conj or prox <= a:
                return None
            return prox

        # liga() só anda para frente: do maior pc para o menor, o seguinte já está calculado
        pula = set()
        for a in sorted(self.p, reverse=True):
            own = self.lat_morta(self.p[a])
            prox = liga(a)
            seg = cobre[prox] + 1 if prox is not None else 0
            if own and prox is not None and seg >= own:
                pula.add(a)
            cobre[a] = max(own, seg)
        return pula

    def w(self, s):
        self.saida.append(s)

    def eh_desvio(self, a):
        p = self.p.get(a)
        return p is not None and p.desvio() is not None

    def checa_desvio(self, a):
        """O par pode terminar com desvio pendente (ele mesmo é desvio ou segue um)."""
        return self.eh_desvio(a) or self.eh_desvio((a - 8) & vc.MASCARA_PC)

    def alvo_estatico(self, a):
        """Destino do desvio pendente que vence no fim do par a (desvio direto em a-8), ou None."""
        ant = self.p.get((a - 8) & vc.MASCARA_PC)
        if ant is not None and ant.desvio() in vc.DESVIOS_DIRETOS:
            return ant.alvo()
        return None

    # ---------------------------------------------------------------- superior
    def upper(self, p):
        u = p.upper
        op = u & 0x3F
        d, fs, ft, fd = vc.DEST(u), vc.FS(u), vc.FT(u), vc.FD(u)
        if op <= 0x2F:
            if op <= 0x1B:
                tipo = [0, 1, 3, 4, 5, 6, 2][op >> 2]
                return 'vu1n::fmac<%d, 1, false, %d, %d>(x, %d, %d, %d);' % (tipo, d, op & 3, fd, fs, ft)
            tab = {0x1C: (2, 2), 0x1D: (5, 3), 0x1E: (2, 3), 0x1F: (6, 3), 0x20: (0, 2), 0x21: (3, 2), 0x22: (0, 3),
                   0x23: (3, 3), 0x24: (1, 2), 0x25: (4, 2), 0x26: (1, 3), 0x27: (4, 3), 0x28: (0, 0), 0x29: (3, 0),
                   0x2A: (2, 0), 0x2B: (5, 0), 0x2C: (1, 0), 0x2D: (4, 0), 0x2F: (6, 0)}
            if op == 0x2E:
                return 'vu1n::opm<false, %d>(x, %d, %d, %d);' % (d, fd, fs, ft)
            tipo, fonte = tab[op]
            return 'vu1n::fmac<%d, %d, false, %d, 0>(x, %d, %d, %d);' % (tipo, fonte, d, fd, fs, ft)
        sp = vc.esp_upper(u)
        if sp <= 0x0F:
            tipo = [0, 1, 3, 4][sp >> 2]
            return 'vu1n::fmac<%d, 1, true, %d, %d>(x, 0, %d, %d);' % (tipo, d, sp & 3, fs, ft)
        if 0x10 <= sp <= 0x13:
            return 'vu1n::itof<%d, %d>(x, %d, %d);' % ([0, 4, 12, 15][sp & 3], d, ft, fs)
        if 0x14 <= sp <= 0x17:
            return 'vu1n::ftoi<%d, %d>(x, %d, %d);' % ([0, 4, 12, 15][sp & 3], d, ft, fs)
        if 0x18 <= sp <= 0x1B:
            return 'vu1n::fmac<2, 1, true, %d, %d>(x, 0, %d, %d);' % (d, sp & 3, fs, ft)
        if sp == 0x1D:
            return 'vu1n::absv<%d>(x, %d, %d);' % (d, ft, fs)
        if sp == 0x1F:
            return 'vu1n::clip(x, %d, %d);' % (fs, ft)
        if sp == 0x2E:
            return 'vu1n::opm<true, %d>(x, 0, %d, %d);' % (d, fs, ft)
        if sp in (0x2F, 0x30):
            return ''
        tab = {0x1C: (2, 2), 0x1E: (2, 3), 0x20: (0, 2), 0x21: (3, 2), 0x22: (0, 3), 0x23: (3, 3), 0x24: (1, 2),
               0x25: (4, 2), 0x26: (1, 3), 0x27: (4, 3), 0x28: (0, 0), 0x29: (3, 0), 0x2A: (2, 0), 0x2C: (1, 0),
               0x2D: (4, 0)}
        tipo, fonte = tab[sp]
        return 'vu1n::fmac<%d, %d, true, %d, 0>(x, 0, %d, %d);' % (tipo, fonte, d, fs, ft)

    def escreve_mac(self, p):
        """O par escreve MAC/status pelo FMAC (ADD/SUB/MUL/MADD/MSUB/OPM com Dest != 0)."""
        cu = self.upper(p)
        if cu.startswith('vu1n::fmac<'):
            args = cu[len('vu1n::fmac<'):cu.index('>')].split(',')
            return int(args[0]) <= 4 and int(args[3]) != 0
        if cu.startswith('vu1n::opm<'):
            args = cu[len('vu1n::opm<'):cu.index('>')].split(',')
            return int(args[1]) != 0
        return False

    def succs(self, no):
        M = vc.MASCARA_PC
        tipo, pc = no
        q = self.p.get(pc)
        if q is None:
            return ['EXIT']
        if tipo == 'f':
            return ['END']
        if tipo == 'd':
            b = self.p.get((pc - 8) & M)
            if b is None or q.ebit or q.desvio() is not None:
                return ['EXIT']
            d = b.desvio()
            if d in ('JR', 'JALR') or d is None:
                return ['EXIT']
            out = [('n', b.alvo())]
            if d not in ('B', 'BAL'):
                out.append(('n', (pc + 8) & M))
            return out
        if q.desvio() is not None:
            return ['EXIT'] if q.ebit else [('d', (pc + 8) & M)]
        if q.ebit:
            return [('f', (pc + 8) & M)]
        return [('n', (pc + 8) & M)]


    def escritas_prontas(self, p):
        """(termo, latência) das escritas de prontidão do par (as mesmas que par() emite)."""
        out = []
        rl, ll = p.ul.vf_escreve
        if rl and p.suprime_vf_inferior != rl:
            lat = p.ul.lat_vf_efetiva()
            for bit, c in LANES:
                if ll & bit:
                    out.append(('x.vfR[%d][%d]' % (rl, c), lat))
        ru, lu = p.uu.vf_escreve
        if ru:
            for bit, c in LANES:
                if lu & bit:
                    out.append(('x.vfR[%d][%d]' % (ru, c), p.uu.lat_vf_efetiva()))
        for reg in sorted(p.ul.vi_escreve):
            out.append(('x.viR[%d]' % reg, p.ul.lat_vi_efetiva()))
        return out

    def analisa_prontos(self):
        """Por nó (papel, pc): ciclos que ainda podem faltar para cada termo de prontidão no início do par (o Ctx
        nasce com tudo pronto; cada par anda >= 1 ciclo). Termo com 0 em todo caminho dispensa a trava."""
        esc = {a: self.escritas_prontas(q) for a, q in self.p.items()}
        nos = set()
        pend = [('n', a) for a in self.p]
        while pend:
            no = pend.pop()
            if no in nos:
                continue
            nos.add(no)
            for s in self.succs(no):
                if isinstance(s, tuple):
                    pend.append(s)
        M = vc.MASCARA_PC
        # JR/JALR seguem no mesmo Ctx (despacho): destinos plausíveis = início, entradas extras, retornos de BAL e
        # alvos de desvio; outra saída estranha propaga para todos os pares
        alvos_jr = set(self.entradas) | {a for a in self.p if a not in self.base}
        for a, q in self.p.items():
            d = q.desvio()
            if d in vc.DESVIOS_DIRETOS:
                alvos_jr.add(q.alvo())
            if d == 'BAL':
                alvos_jr.add((a + 16) & M)
        alvos_jr = [('n', a) for a in alvos_jr if ('n', a) in nos]
        todos = [no for no in nos if no[0] == 'n']

        def sucs(no):
            out = []
            for su in self.succs(no):
                if isinstance(su, tuple):
                    out.append(su)
                elif su == 'EXIT':
                    tipo, pc = no
                    b = self.p.get((pc - 8) & M) if tipo == 'd' else None
                    if b is not None and b.desvio() in ('JR', 'JALR') and self.p[pc].desvio() is None and not self.p[pc].ebit:
                        out.extend(alvos_jr)
                    elif self.p.get(pc) is not None:
                        out.extend(todos)
            return out

        rem = {no: {} for no in nos}
        mudou = True
        while mudou:
            mudou = False
            for no in nos:
                if no[1] not in self.p:
                    continue
                saida = {k: v - 1 for k, v in rem[no].items() if v > 1}
                for termo, lat in esc[no[1]]:
                    saida[termo] = lat - 1 if lat > 1 else 0
                for su in sucs(no):
                    if su not in rem:
                        continue
                    alvo = rem[su]
                    for k, v in saida.items():
                        if v > alvo.get(k, 0):
                            alvo[k] = v
                            mudou = True
        return rem

    def analisa_mac(self):
        """FMACs mortos: em nenhum caminho o MAC deles chega a ser lido (FMAND/FMEQ/FMOR) ou sai do código conhecido
        antes de um FMAC posterior com 4+ pares de distância (pronto com certeza). Estados: 'N' (nenhum FMAC
        posterior ainda) ou a distância desde o primeiro FMAC posterior (4 = superado)."""
        M = vc.MASCARA_PC
        le = {a for a, q in self.p.items() if not q.ibit and q.nl in ('FMAND', 'FMEQ', 'FMOR')}
        esc = {a for a, q in self.p.items() if self.escreve_mac(q)}

        nos = set()
        pend = [('n', a) for a in self.p]
        while pend:
            no = pend.pop()
            if no in nos:
                continue
            nos.add(no)
            for s in self.succs(no):
                if isinstance(s, tuple):
                    pend.append(s)
        estados = ('N', 0, 1, 2, 3)
        obs = {}

        def avanca(pc, s):
            s2 = 0 if (s == 'N' and pc in esc) else s
            return s2 if s2 == 'N' else min(s2 + 1, 4)

        def ve(sucs, s3):
            for su in sucs:
                if su == 'EXIT':
                    if s3 != 4:
                        return True
                elif su == 'END':
                    if s3 == 'N':
                        return True
                elif s3 != 4 and obs.get((su, s3), False):
                    return True
            return False

        mudou = True
        while mudou:
            mudou = False
            for no in nos:
                for s in estados:
                    if obs.get((no, s), False):
                        continue
                    v = no[1] in le or ve(self.succs(no), avanca(no[1], s))
                    if v:
                        obs[(no, s)] = True
                        mudou = True
        mortos = set()
        for a in esc:
            papeis = [('n', a)]
            if ('d', a) in nos:
                papeis.append(('d', a))
            if all(not ve(self.succs(r), 'N') for r in papeis):
                mortos.add(a)
        return mortos

    # ---------------------------------------------------------------- normalização (Otavix, 29/10)
    def _efeito_norm(self, p, st):
        """Estado de normalização depois do par p. st = (lista de 32 máscaras de lanes de VF, máscara do ACC); lanes
        no formato do DEST (8 = x). N = valor que o nOp não muda (resultado de FMAC/OPM/MAX/MINI/ITOF, VF0)."""
        vf = list(st[0])
        acc = st[1]
        cu = self.upper(p)
        # inferior (lê os valores antigos; se escreve o mesmo VF que o superior, é suprimido)
        rl, ll = (0, 0) if p.ibit else p.ul.vf_escreve
        if rl and p.suprime_vf_inferior != rl:
            n = p.nl
            if n == 'MOVE':
                fs = vc.FS(p.lower)
                vf[rl] = (vf[rl] & ~ll) | (st[0][fs] & ll)
            elif n == 'MR32':
                fs = vc.FS(p.lower)
                src = st[0][fs]
                rot = 0
                # MR32: x <- y, y <- z, z <- w, w <- x
                for bit_d, bit_s in ((8, 4), (4, 2), (2, 1), (1, 8)):
                    if src & bit_s:
                        rot |= bit_d
                vf[rl] = (vf[rl] & ~ll) | (rot & ll)
            else:
                vf[rl] &= ~ll
        # superior
        ru, lu = p.uu.vf_escreve
        if cu.startswith('vu1n::fmac<') or cu.startswith('vu1n::opm<'):
            args = [a.strip() for a in cu[cu.index('<') + 1:cu.index('>')].split(',')]
            para_acc = (args[2] if cu.startswith('vu1n::fmac<') else args[0]) == 'true'
            dest = int(args[3] if cu.startswith('vu1n::fmac<') else args[1])
            if para_acc:
                acc |= dest
            elif ru:
                vf[ru] |= lu
        elif cu.startswith('vu1n::itof<'):
            if ru:
                vf[ru] |= lu
        elif cu.startswith('vu1n::absv<'):
            if ru:
                fs = vc.FS(p.upper)
                vf[ru] = (vf[ru] & ~lu) | (st[0][fs] & lu)
        elif ru:
            vf[ru] &= ~lu
        vf[0] = 0xF
        return (tuple(vf), acc)

    def analisa_norm(self):
        """Por pc: estado de normalização na entrada do par (encontro = E lógico dos caminhos). Entradas de fora
        (início, entradas extras) = nada normalizado. Transferências dinâmicas (JR/JALR, desvio pendente) só caem em
        self.alvos_din (o despacho devolve qualquer outro pc) e levam o estado de saída real."""
        M = vc.MASCARA_PC
        cru = (tuple([0xF] + [0] * 31), 0)
        nos = set()
        pend = [('n', a) for a in self.p]
        while pend:
            no = pend.pop()
            if no in nos:
                continue
            nos.add(no)
            for s in self.succs(no):
                if isinstance(s, tuple):
                    pend.append(s)
        est = {no: None for no in nos}
        for a in self.p:
            if (a in self.entradas or a not in self.base) and ('n', a) in est:
                est[('n', a)] = cru
        alvos = [('n', a) for a in self.alvos_din if ('n', a) in est]

        def encontra(a, b):
            if a is None:
                return b
            return (tuple(x & y for x, y in zip(a[0], b[0])), a[1] & b[1])

        mudou = True
        while mudou:
            mudou = False
            for no in nos:
                st = est[no]
                if st is None or no[1] not in self.p:
                    continue
                out = self._efeito_norm(self.p[no[1]], st)
                sucs = []
                for su in self.succs(no):
                    if su == 'EXIT':
                        sucs.extend(alvos)
                    elif isinstance(su, tuple):
                        sucs.append(su)
                for su in sucs:
                    if su not in est:
                        continue
                    novo = encontra(est[su], out)
                    if novo != est[su]:
                        est[su] = novo
                        mudou = True
        por_pc = {}
        for (papel, a), st in est.items():
            if st is None or papel == 'f':
                continue
            por_pc[a] = encontra(por_pc.get(a), st)
        return por_pc

    def bits_norm(self, p, cu):
        """Norm do fmac/opm do par: 1 = fs, 2 = ft, 4 = ACC normalizados nas lanes que a operação usa."""
        if self.norm is None or not (cu.startswith('vu1n::fmac<') or cu.startswith('vu1n::opm<')):
            return 0
        st = self.norm.get(p.pc)
        if st is None:
            return 0
        vf, acc = st
        args = [a.strip() for a in cu[cu.index('<') + 1:cu.index('>')].split(',')]
        ops = [int(a.strip()) for a in cu[cu.index('(x,') + 3:cu.rindex(')')].split(',')]
        fd, fs, ft = ops
        bits = 0
        if cu.startswith('vu1n::fmac<'):
            tipo, fonte, dest, bc = int(args[0]), int(args[1]), int(args[3]), int(args[4])
            if (vf[fs] & dest) == dest:
                bits |= 1
            if fonte == 0 and (vf[ft] & dest) == dest:
                bits |= 2
            if fonte == 1 and (vf[ft] & (8 >> bc)):
                bits |= 2
            if tipo in (3, 4) and (acc & dest) == dest:
                bits |= 4
        else:
            dest = int(args[1])
            if (vf[fs] & 0xE) == 0xE:
                bits |= 1
            if (vf[ft] & 0xE) == 0xE:
                bits |= 2
            if args[0] == 'false' and (acc & dest) == dest:
                bits |= 4
        return bits

    def upper_escreve_vf0(self, p):
        u = p.upper
        op = u & 0x3F
        if vc.DEST(u) == 0:
            return False
        if op <= 0x2F:
            return vc.FD(u) == 0
        sp = vc.esp_upper(u)
        return (0x10 <= sp <= 0x17 or sp == 0x1D) and vc.FT(u) == 0

    # ---------------------------------------------------------------- inferior
    def lower(self, p):
        """Código do inferior (lista de linhas)."""
        l = p.lower
        n = p.nl
        d, ft, fs = vc.DEST(l), vc.FT(l), vc.FS(l)
        it, is_, id_ = vc.VIT(l), vc.VIS(l), vc.VID(l)
        imm = vc.imm11(l)
        c21, c23 = (l >> 21) & 3, (l >> 23) & 3
        imm12 = (((l >> 21) & 1) << 11) | (l & 0x7FF)
        imm24 = l & 0xFFFFFF
        imm15 = (l & 0x7FF) | ((l >> 10) & 0x7800)

        def vi(r):
            return '0' if r == 0 else 's.vi[%d]' % r

        def vid(r):  # leitura de VI por desvio
            return '0' if r == 0 else 'vu1n::viDesvio(x, %d)' % r

        def wvi(r, expr):
            return [] if r == 0 else ['s.vi[%d] = static_cast<int16_t>(%s);' % (r, expr)]

        def desvia(alvo_expr):
            return ['x.bp = true;', 'x.bt = %s;' % alvo_expr, 'x.bd = 1u;']

        if n == 'NOP':
            return []
        if n == 'LQ':
            return ['vu1n::carrega<%d>(x, %d, vu1n::endQ(x, %s, %d));' % (d, ft, vi(is_), imm)]
        if n == 'SQ':
            return ['vu1n::guardaVf<%d>(x, vu1n::endQ(x, %s, %d), %d);' % (d, vi(it), imm, fs)]
        if n == 'ILW':
            return wvi(it, 'vu1n::leVi<%d>(x, vu1n::endQ(x, %s, %d))' % (d, vi(is_), imm))
        if n == 'ISW':
            return ['vu1n::guardaVi<%d>(x, vu1n::endQ(x, %s, %d), %d);' % (d, vi(is_), imm, it)]
        if n == 'IADDIU':
            return wvi(it, '%s + %d' % (vi(is_), imm15))
        if n == 'ISUBIU':
            return wvi(it, '%s - %d' % (vi(is_), imm15))
        if n == 'FCEQ':
            return ['s.vi[1] = (s.clip & 0xFFFFFFu) == 0x%06Xu ? 1 : 0;' % imm24]
        if n == 'FCSET':
            return ['vu1n::fcset(x, 0x%06Xu);' % imm24]
        if n == 'FCAND':
            return ['s.vi[1] = (s.clip & 0x%06Xu) != 0u ? 1 : 0;' % imm24]
        if n == 'FCOR':
            return ['s.vi[1] = (s.clip | 0x%06Xu) == 0xFFFFFFu ? 1 : 0;' % imm24]
        if n == 'FSEQ':
            return wvi(it, '(s.status & 0xFFFu) == 0x%03Xu ? 1 : 0' % imm12)
        if n == 'FSSET':
            return ['vu1n::fsset(x, 0x%03Xu);' % imm12]
        if n == 'FSAND':
            return wvi(it, 's.status & 0x%03Xu' % imm12)
        if n == 'FSOR':
            return wvi(it, '(s.status & 0xFFFu) | 0x%03Xu' % imm12)
        if n == 'FMEQ':
            return wvi(it, '(s.mac & 0xFFFFu) == static_cast<uint32_t>(static_cast<uint16_t>(%s)) ? 1 : 0' % vi(is_))
        if n == 'FMAND':
            return wvi(it, 's.mac & static_cast<uint32_t>(static_cast<uint16_t>(%s))' % vi(is_))
        if n == 'FMOR':
            return wvi(it, 's.mac | static_cast<uint32_t>(static_cast<uint16_t>(%s))' % vi(is_))
        if n == 'FCGET':
            return wvi(it, 's.clip & 0x0FFFu')
        if n == 'B':
            return desvia('0x%04Xu' % p.alvo())
        if n == 'BAL':
            return wvi(it, '%d' % ((p.pc + 16) // 8)) + desvia('0x%04Xu' % p.alvo())
        if n == 'JR':
            # Otavix (30/10): JR/JALR leem o VI atual (a regra do VI antigo é só dos desvios condicionais)
            return desvia('(static_cast<uint32_t>(static_cast<uint16_t>(%s)) * 8u) & 0x3FFFu' % vi(is_))
        if n == 'JALR':
            return (['const uint32_t alvo = (static_cast<uint32_t>(static_cast<uint16_t>(%s)) * 8u) & 0x3FFFu;' % vi(is_)]
                    + wvi(it, '%d' % ((p.pc + 16) // 8)) + desvia('alvo'))
        cond = {'IBEQ': 'static_cast<int16_t>(%s) == static_cast<int16_t>(%s)' % (vid(is_), vid(it)),
                'IBNE': 'static_cast<int16_t>(%s) != static_cast<int16_t>(%s)' % (vid(is_), vid(it)),
                'IBLTZ': 'static_cast<int16_t>(%s) < 0' % vid(is_),
                'IBGTZ': 'static_cast<int16_t>(%s) > 0' % vid(is_),
                'IBLEZ': 'static_cast<int16_t>(%s) <= 0' % vid(is_),
                'IBGEZ': 'static_cast<int16_t>(%s) >= 0' % vid(is_)}
        if n in cond:
            return ['if (%s)' % cond[n], '{'] + ['    ' + s for s in desvia('0x%04Xu' % p.alvo())] + ['}']
        if n == 'IADD':
            return wvi(id_, '%s + %s' % (vi(is_), vi(it)))
        if n == 'ISUB':
            return wvi(id_, '%s - %s' % (vi(is_), vi(it)))
        if n == 'IADDI':
            i5 = (l >> 6) & 0x1F
            i5 = i5 - 32 if i5 & 0x10 else i5
            return wvi(it, '%s + %d' % (vi(is_), i5))
        if n == 'IAND':
            return wvi(id_, '%s & %s' % (vi(is_), vi(it)))
        if n == 'IOR':
            return wvi(id_, '%s | %s' % (vi(is_), vi(it)))
        if n == 'MOVE':
            return ['{ float t[4]; std::memcpy(t, s.vf[%d], 16); vu1n::grava<%d>(s.vf[%d], t); }' % (fs, d, ft)]
        if n == 'MR32':
            return ['{ const float t[4] = {s.vf[%d][1], s.vf[%d][2], s.vf[%d][3], s.vf[%d][0]}; vu1n::grava<%d>(s.vf[%d], t); }'
                    % (fs, fs, fs, fs, d, ft)]
        if n == 'LQI':
            return ['vu1n::carrega<%d>(x, %d, vu1n::endR(x, %s));' % (d, ft, vi(is_))] + wvi(is_, '%s + 1' % vi(is_))
        if n == 'SQI':
            return ['vu1n::guardaVf<%d>(x, vu1n::endR(x, %s), %d);' % (d, vi(it), fs)] + wvi(it, '%s + 1' % vi(it))
        if n == 'LQD':
            return wvi(is_, '%s - 1' % vi(is_)) + ['vu1n::carrega<%d>(x, %d, vu1n::endR(x, %s));' % (d, ft, vi(is_))]
        if n == 'SQD':
            return wvi(it, '%s - 1' % vi(it)) + ['vu1n::guardaVf<%d>(x, vu1n::endR(x, %s), %d);' % (d, vi(it), fs)]
        if n == 'DIV':
            return ['vu1n::div(x, %d, %d, %d, %d);' % (fs, c21, ft, c23)]
        if n == 'SQRT':
            return ['vu1n::sqrtq(x, %d, %d);' % (ft, c23)]
        if n == 'RSQRT':
            return ['vu1n::rsqrt(x, %d, %d, %d, %d);' % (fs, c21, ft, c23)]
        if n in ('WAITQ', 'WAITP'):
            return []
        if n == 'MTIR':
            return wvi(it, 'static_cast<int16_t>(vu1n::bits(s.vf[%d][%d]) & 0xFFFFu)' % (fs, c21))
        if n == 'MFIR':
            return ['{ const int32_t v = static_cast<int16_t>(%s & 0xFFFF); float t[4]; std::memcpy(&t[0], &v, 4); '
                    't[1] = t[2] = t[3] = t[0]; vu1n::grava<%d>(s.vf[%d], t); }' % (vi(is_), d, ft)]
        if n == 'ILWR':
            return wvi(it, 'vu1n::leVi<%d>(x, vu1n::endR(x, %s))' % (d, vi(is_)))
        if n == 'ISWR':
            return ['vu1n::guardaVi<%d>(x, vu1n::endR(x, %s), %d);' % (d, vi(is_), it)]
        if n == 'RNEXT':
            return ['{ const uint32_t a = (s.r >> 4) & 1u, b = (s.r >> 22) & 1u; s.r = (((s.r << 1) ^ a ^ b) & 0x007FFFFFu) | 0x3F800000u; '
                    'float v; std::memcpy(&v, &s.r, 4); const float t[4] = {v, v, v, v}; vu1n::grava<%d>(s.vf[%d], t); }' % (d, ft)]
        if n == 'RGET':
            return ['{ float v; std::memcpy(&v, &s.r, 4); const float t[4] = {v, v, v, v}; vu1n::grava<%d>(s.vf[%d], t); }' % (d, ft)]
        if n == 'RINIT':
            return ['s.r = 0x3F800000u | (vu1n::bits(s.vf[%d][%d]) & 0x007FFFFFu);' % (fs, c21)]
        if n == 'RXOR':
            return ['s.r = 0x3F800000u | ((s.r ^ vu1n::bits(s.vf[%d][%d])) & 0x007FFFFFu);' % (fs, c21)]
        if n == 'MFP':
            return ['{ const float t[4] = {s.p, s.p, s.p, s.p}; vu1n::grava<%d>(s.vf[%d], t); }' % (d, ft)]
        if n == 'XTOP':
            return wvi(it, 's.top & 0x3FFu')
        if n == 'XITOP':
            return wvi(it, 's.itop & 0x3FFu')
        if n == 'XGKICK':
            return ['vu1n::xgkick(x, %d);' % is_]
        efu = {'ESADD': 0x70, 'ERSADD': 0x71, 'ELENG': 0x72, 'ERLENG': 0x73, 'EATANxy': 0x74, 'EATANxz': 0x75,
               'ESUM': 0x76, 'ERSQRT': 0x77, 'ESQRT': 0x78, 'ESIN': 0x79, 'ERCPR': 0x7A, 'EATAN': 0x7C, 'EEXP': 0x7D}
        if n in efu:
            return ['vu1n::efu<0x%02X>(x, %d, %d);' % (efu[n], fs, c21)]
        raise ValueError('inferior sem tradução: %s %08x' % (n, l))

    def le_filas(self, p):
        u = p.upper
        op = u & 0x3F
        q_ops = (0x1C, 0x20, 0x21, 0x24, 0x25)
        if op in q_ops or (op >= 0x3C and vc.esp_upper(u) in q_ops):
            return True
        return not p.ibit and p.nl in ('FCEQ', 'FCAND', 'FCOR', 'FCGET', 'FSEQ', 'FSAND', 'FSOR', 'FMEQ', 'FMAND',
                                        'FMOR', 'MFP')

    def lower_escreve_vf0(self, p):
        if p.ibit or vc.DEST(p.lower) == 0:
            return False
        if p.nl in ('LQ', 'LQI', 'LQD', 'MOVE', 'MR32', 'MFIR', 'RNEXT', 'RGET', 'MFP'):
            return vc.FT(p.lower) == 0
        return False

    # ---------------------------------------------------------------- par
    def termos_trava(self, a, final):
        """Termos de prontidão (x.vfR[r][c] / x.viR[r]) que a trava do par a confere (os que ainda podem faltar)."""
        p = self.p[a]
        termos = []
        for us in (p.uu, p.ul):
            for reg, lanes in sorted(us.vf_le.items()):
                if reg == 0:
                    continue
                for bit, c in LANES:
                    if lanes & bit:
                        t = 'x.vfR[%d][%d]' % (reg, c)
                        if t not in termos:
                            termos.append(t)
            for reg in sorted(us.vi_le):
                t = 'x.viR[%d]' % reg
                if t not in termos:
                    termos.append(t)
        if self.rem is not None:
            papeis = [('f', a)] if final else [r for r in (('n', a), ('d', a)) if r in self.rem]
            termos = [t_ for t_ in termos if any(self.rem.get(r, {}).get(t_, 0) > 0 for r in papeis) or not papeis]
        return termos

    def devolve(self, a, final, ind):
        eb = 'x.eb = true; ' if final else ''
        return ind + '{ %sx.pc = 0x%04Xu; return vu1n::Devolve; }' % (eb, a)

    def par(self, a, final):
        p = self.p[a]
        I = '    '
        rot = ('F_%04X' if final else 'L_%04X') % a
        self.w('%s: // %s | %s%s' % (rot, p.nu, p.nl, ''.join(' ' + b for b, v in (('I', p.ibit), ('E', p.ebit), ('D', p.dbit), ('T', p.tbit)) if v)))
        self.w('{')
        if CONTA:
            self.w(I + 'vu1n::contaPar(0x%016xull, 0x%04Xu);' % (self.hp, a))
        if ORCAMENTO_PAR or (not final and a in self.cabecas):
            self.w(I + 'if (x.c >= x.fim)')
            self.w(self.devolve(a, final, I + '    '))
        if p.uu.reservada or p.ul.reservada:
            self.w(self.devolve(a, final, I))
            self.w('}')
            return
        if p.dbit or p.tbit:
            cond = ' || '.join(c for c, v in (('s.dBitEnabled', p.dbit), ('s.tBitEnabled', p.tbit)) if v)
            self.w(I + 'if (%s)' % cond)
            self.w(self.devolve(a, final, I + '    '))
        # trava: leituras de VF/VI, Q/P/EFU, XGKICK
        termos = self.termos_trava(a, final)
        extra = []
        if p.ul.pipe == 'fdiv':
            extra.append('if (x.qv) r = std::max(r, x.qPronto);')
        if p.ul.pipe == 'efu':
            extra.append('r = std::max(r, x.efuLivre);')
        if p.ul.wait_p:
            extra.append('for (int k = 0; k < 2; ++k) if (x.pv[k]) r = std::max(r, x.pPronto[k]);')
        if termos or extra:
            self.w(I + '{')
            self.w(I + '    uint64_t r = x.c;')
            for t in termos:
                self.w(I + '    r = std::max(r, %s);' % t)
            for e in extra:
                self.w(I + '    ' + e)
            self.w(I + '    if (!vu1n::trava(x, r))')
            self.w(self.devolve(a, final, I + '        '))
            self.w(I + '}')
        if p.ul.pipe == 'xgkick':
            self.w(I + 'if (!vu1n::esperaXg(x))')
            self.w(self.devolve(a, final, I + '    '))
        # leitura de Q/MAC/status/clip/P efetivados: efetiva as filas até x.c antes
        if self.le_filas(p):
            self.w(I + 'vu1n::sinc(x);')
        # backup de VI para o desvio do par seguinte
        bk = 0
        if p.ul.atrasa_desvio and p.ul.vi_escreve:
            bk = min(p.ul.vi_escreve)
            self.w(I + 'const int32_t bko = s.vi[%d];' % bk)
        # execução
        cu = self.upper(p)
        if self.sem_fila and (cu.startswith('vu1n::fmac<') or cu.startswith('vu1n::opm<')):
            cu = cu.replace('>(x,', ', 1>(x,', 1)
        elif not final and a in self.mortos:
            cu = cu.replace('>(x,', ', 2>(x,', 1)
        nb = 0 if final else self.bits_norm(p, self.upper(p))
        if nb:
            nargs = cu[cu.index('<') + 1:cu.index('>')].count(',') + 1
            base_args = 5 if cu.startswith('vu1n::fmac<') else 2
            cu = cu.replace('>(x,', (', %d>(x,' % nb) if nargs > base_args else (', 0, %d>(x,' % nb), 1)
        if QUENTES_TODOS or self.hp in QUENTES:
            cu = cu.replace('vu1n::fmac<', 'vu1n::fmacI<', 1).replace('vu1n::opm<', 'vu1n::opmI<', 1)
        cl = [] if p.ibit else self.lower(p)
        if p.sombra:
            r = p.sombra
            self.w(I + '{')
            self.w(I + '    float vAnt[4], vSup[4];')
            self.w(I + '    std::memcpy(vAnt, s.vf[%d], 16);' % r)
            self.w(I + '    ' + cu)
            self.w(I + '    std::memcpy(vSup, s.vf[%d], 16);' % r)
            self.w(I + '    std::memcpy(s.vf[%d], vAnt, 16);' % r)
            for s_ in cl:
                self.w(I + '    ' + s_)
            self.w(I + '    std::memcpy(s.vf[%d], vSup, 16);' % r)
            self.w(I + '}')
        else:
            if cu:
                self.w(I + cu)
            if p.ibit:
                self.w(I + 's.i = vu1n::deBits(0x%08Xu);' % f32_norm_bits(p.lower))
            if cl:
                if any(s_.startswith('const ') for s_ in cl):
                    self.w(I + '{')
                    for s_ in cl:
                        self.w(I + '    ' + s_)
                    self.w(I + '}')
                else:
                    for s_ in cl:
                        self.w(I + s_)
        # prontos das escritas (markPairWrites); com self.vivos: só os termos que alguma trava do programa confere
        # (os outros: VF vai para x.fimV, que o flush espera; VI de latência 1 nunca passa do fim, >1 já vai em fimW)
        esc_vf = []
        rl, ll = p.ul.vf_escreve
        if rl and p.suprime_vf_inferior != rl:
            lat = p.ul.lat_vf_efetiva()
            for bit, c in LANES:
                if ll & bit:
                    esc_vf.append(('x.vfR[%d][%d]' % (rl, c), lat))
        ru, lu = p.uu.vf_escreve
        if ru:
            for bit, c in LANES:
                if lu & bit:
                    esc_vf.append(('x.vfR[%d][%d]' % (ru, c), p.uu.lat_vf_efetiva()))
        esc_vi = [(reg, p.ul.lat_vi_efetiva()) for reg in sorted(p.ul.vi_escreve)]
        if self.vivos is None:
            # formato antigo (sem bloco c0): uma escrita por termo
            for t, lat in esc_vf:
                self.w(I + '%s = x.c + %du;' % (t, lat))
            for reg, lat in esc_vi:
                self.w(I + 'x.viR[%d] = x.c + %du;' % (reg, lat))
                if lat > 1:
                    self.w(I + 'x.fimW = std::max(x.fimW, x.c + %du);' % lat)
        elif esc_vf or esc_vi:
            self.w(I + '{')
            self.w(I + '    const uint64_t c0 = x.c;')
            lat_morta = 0
            for t, lat in esc_vf:
                if self.vivos is None or t in self.vivos:
                    self.w(I + '    %s = c0 + %du;' % (t, lat))
                else:
                    lat_morta = max(lat_morta, lat)
            if lat_morta and (final or a not in self.pula_fimv):
                self.w(I + '    x.fimV = std::max(x.fimV, c0 + %du);' % lat_morta)
            for reg, lat in esc_vi:
                if self.vivos is None or ('x.viR[%d]' % reg) in self.vivos:
                    self.w(I + '    x.viR[%d] = c0 + %du;' % (reg, lat))
                if lat > 1:
                    self.w(I + '    x.fimW = std::max(x.fimW, c0 + %du);' % lat)
            self.w(I + '}')
        if bk:
            self.w(I + 'x.bkReg = %d;' % bk)
            self.w(I + 'x.bkVal = bko;')
        elif final or self.precisa_bk is None or a in self.precisa_bk:
            self.w(I + 'x.bkReg = 0;')
        if self.upper_escreve_vf0(p) or self.lower_escreve_vf0(p):
            self.w(I + 'vu1n::vf0(x);')
        # próximo pc
        prox = (a + 8) & vc.MASCARA_PC
        dinamico = self.checa_desvio(a)
        if dinamico:
            self.w(I + 'uint32_t pcn = 0x%04Xu;' % prox)
            self.w(I + 'bool salta = false;')
            self.w(I + 'if (x.bp)')
            self.w(I + '{')
            self.w(I + '    if (x.bd == 0u)')
            self.w(I + '    {')
            self.w(I + '        x.bp = false;')
            self.w(I + '        pcn = x.bt;')
            self.w(I + '        salta = true;')
            self.w(I + '    }')
            self.w(I + '    else')
            self.w(I + '        --x.bd;')
            self.w(I + '}')
        self.w(I + 'vu1n::fimPar(x);')
        if final:
            self.w(I + 's.pc = %s;' % ('pcn' if dinamico else '0x%04Xu' % prox))
            self.w(I + 'vu1n::flush(x);')
            self.w(I + 'return vu1n::Terminou;')
            self.w('}')
            return
        if p.ebit:
            # o par seguinte é o último
            self.finais.add(prox)
            if dinamico:
                alvo = self.alvo_estatico(a)
                if alvo is not None:
                    self.finais.add(alvo)
                self.fin_din = True
                self.w(I + 'pc = pcn;')
                self.w(I + 'goto despachoFinal;')
            elif prox in self.conj:
                self.w(I + 'goto F_%04X;' % prox)
            else:
                self.w(self.devolve(prox, True, I))
            self.w('}')
            return
        if dinamico:
            alvo = self.alvo_estatico(a)
            self.w(I + 'if (salta)')
            self.w(I + '{')
            if alvo is not None and alvo in self.conj:
                self.w(I + '    if (pcn == 0x%04Xu)' % alvo)
                self.w(I + '        goto L_%04X;' % alvo)
            self.w(I + '    pc = pcn;')
            self.w(I + '    goto despacho;')
            self.w(I + '}')
        if prox in self.conj:
            self.w(I + 'goto L_%04X;' % prox)
        else:
            self.w(I + 'x.pc = 0x%04Xu;' % prox)
            self.w(I + 'return vu1n::Devolve;')
        self.w('}')

    def ret(self, linha):
        """Otavix (LOCAL): troca 'return vu1n::X;' pela macro que devolve o estado local antes de sair."""
        if not LOCAL:
            return linha
        import re as _re
        return _re.sub(r'return (vu1n::[A-Za-z]+);', lambda m: 'VU1N_RET(%s);' % m.group(1), linha)

    def gera(self):
        nome = 'p_%016x' % self.hp
        self.w('// programa %016x: início 0x%04X, %d pares' % (self.hp, self.inicio, len(self.pares)))
        self.w('int %s(vu1n::Ctx &x, uint32_t pc)' % nome)
        self.w('{')
        if LOCAL:
            # Otavix: estado do VU em cópia local (pilha) durante o programa; VU1N_RET devolve antes de sair
            self.w('    VU1State *const otxOrig = x.s;')
            self.w('    VU1State otxLocal = *otxOrig;')
            self.w('    x.s = &otxLocal;')
            self.w('    VU1State &s = otxLocal;')
        else:
            self.w('    VU1State &s = *x.s;')
        self.w('    goto despacho;')
        corpo_ini = len(self.saida)
        for a in self.pares:
            self.par(a, False)
        feitos = set()
        while True:
            novos = sorted(f for f in self.finais if f not in feitos)
            if not novos:
                break
            for f in novos:
                feitos.add(f)
                if f in self.conj:
                    self.par(f, True)
        self.w('despacho:')
        if not ORCAMENTO_PAR:
            # JR/JALR e desvios dinâmicos voltam por aqui: confere o orçamento (laços indiretos)
            self.w('    if (x.c >= x.fim)')
            self.w('        { x.pc = pc; return vu1n::Devolve; }')
        self.w('    switch (pc)')
        self.w('    {')
        for a in self.pares:
            if NORM and a not in self.alvos_din:
                continue  # Otavix (normalização): destino dinâmico fora do previsto devolve ao interpretador
            if a in self.base:
                self.w('    case 0x%04Xu: goto L_%04X;' % (a, a))
            else:
                self.w('    case 0x%04Xu: if (x.semExtras) { x.pc = pc; return vu1n::Devolve; } goto L_%04X;' % (a, a))
        self.w('    default:')
        self.w('        x.pc = pc;')
        self.w('        return vu1n::Devolve;')
        self.w('    }')
        self.w('despachoFinal:')
        self.w('    switch (pc)')
        self.w('    {')
        for f in sorted(feitos):
            if f in self.conj and f in self.base:
                self.w('    case 0x%04Xu: goto F_%04X;' % (f, f))
            elif f in self.conj:
                self.w('    case 0x%04Xu: if (x.semExtras) { x.eb = true; x.pc = pc; return vu1n::Devolve; } goto F_%04X;' % (f, f))
        self.w('    default:')
        self.w('        x.eb = true;')
        self.w('        x.pc = pc;')
        self.w('        return vu1n::Devolve;')
        self.w('    }')
        self.w('}')
        self.w('')
        self.saida[corpo_ini:] = [self.ret(l) for l in self.saida[corpo_ini:]]
        return nome


def le_extras(arquivos):
    extras = {}
    for arq in arquivos:
        for linha in open(arq):
            if linha.strip():
                h, pc = linha.split()
                extras.setdefault(int(h, 16), set()).add(int(pc, 16))
    return extras


def coleta(pastas, min_exec, extras=None):
    extras = extras or {}
    progs = {}
    for pasta in pastas:
        cont = {}
        arq = os.path.join(pasta, 'contagem.txt')
        if os.path.exists(arq):
            for linha in open(arq):
                h, pc, n = linha.split()
                cont[(h, int(pc, 16))] = int(n)
        for linha in open(os.path.join(pasta, 'inicios.txt')):
            h, pc = linha.split()
            pc = int(pc, 16)
            arq = os.path.join(pasta, 'vu1_%s.bin' % h)
            if not os.path.exists(arq):
                continue
            code = open(arq, 'rb').read()
            pares, _ = vc.programa(code, pc)
            hp = vc.hash_programa(code, pares)
            if hp not in progs:
                ex = sorted(extras.get(hp, ()))
                base = pares
                if ex:
                    pares, _ = vc.programa(code, [pc] + ex)
                progs[hp] = {'code': code, 'pares': pares, 'base': base, 'inicio': pc, 'exec': 0, 'extras': ex,
                             'hc': vc.hash_programa(code, pares), 'entradas': set()}
            d = progs[hp]
            if pc != d['inicio'] and pc in d['pares']:
                d['entradas'].add(pc)  # Otavix (31/10): mesmo programa visto a partir de outro pc
            d['exec'] += cont.get((h, pc), 0)
    return {hp: d for hp, d in progs.items() if d['exec'] >= min_exec}


PEDACOS = 8  # vu1_programas_<n>.cpp (nomes fixos no CMake); o MSVC sofre com um arquivo só


def main():
    args = sys.argv[1:]
    min_exec = 0
    if '--min-exec' in args:
        i = args.index('--min-exec')
        min_exec = int(args[i + 1])
        del args[i:i + 2]
    arq_extras = []
    while '--extras' in args:
        i = args.index('--extras')
        arq_extras.append(args[i + 1])
        del args[i:i + 2]
    saida, pastas = args[0], args[1:]
    base = saida[:-4] if saida.endswith('.cpp') else saida
    progs = coleta(pastas, min_exec, le_extras(arq_extras))
    cab = ['// Gerado por vu1_tradutor.py (Otavix) - não editar. Microprogramas do VU1 traduzidos para C++.',
           '#include "ps2_vu1_nativo.h"', '']
    pedacos = [[] for _ in range(PEDACOS)]
    carga = [0] * PEDACOS
    tabela = []
    total = 0
    for hp in sorted(progs, key=lambda h: -len(progs[h]['pares'])):
        d = progs[hp]
        g = Gerador(d['code'], d['pares'], hp, d['inicio'], d['base'], d.get('entradas'))
        nome = g.gera()
        k = carga.index(min(carga))
        carga[k] += len(d['pares'])
        pedacos[k] += g.saida
        tabela.append((hp, d['inicio'], nome, d['extras'], d['hc']))
        total += len(d['pares'])
    tabela.sort(key=lambda e: e[0])
    for k in range(PEDACOS):
        linhas = cab + ['#if defined(_MSC_VER)', '#pragma warning(disable : 4102) // rótulo sem uso', '#endif', '',
                        'namespace vu1n_gerado', '{'] + pedacos[k] + ['}']
        with open('%s_%d.cpp' % (base, k), 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(linhas) + '\n')
    linhas = cab + ['namespace vu1n_gerado', '{']
    for hp, ini, nome, ex, hc in tabela:
        linhas.append('    int %s(vu1n::Ctx &x, uint32_t pc);' % nome)
        if ex:
            linhas.append('    const uint16_t kExtras_%016x[] = {%s};' % (hp, ', '.join('0x%04X' % a for a in ex)))
    linhas += ['}', '', 'namespace vu1n', '{']
    if tabela:
        linhas.append('    const Programa kProgramas[] = {')
        for hp, ini, nome, ex, hc in tabela:
            if ex:
                linhas.append('        {0x%016xull, 0x%04Xu, &vu1n_gerado::%s, vu1n_gerado::kExtras_%016x, %du, 0x%016xull},'
                              % (hp, ini, nome, hp, len(ex), hc))
            else:
                linhas.append('        {0x%016xull, 0x%04Xu, &vu1n_gerado::%s, nullptr, 0u, 0x%016xull},' % (hp, ini, nome, hc))
        linhas.append('    };')
    else:
        linhas.append('    const Programa kProgramas[] = {{0ull, 0u, nullptr, nullptr, 0u, 0ull}};')
    linhas.append('    const uint32_t kNumProgramas = %du;' % len(tabela))
    linhas.append('}')
    with open(base + '.cpp', 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(linhas) + '\n')
    print('%d programas, %d pares -> %s.cpp + %d pedaços (pares: %s)' % (len(tabela), total, base, PEDACOS, carga))


if __name__ == '__main__':
    main()
