# Base comum do tradutor do VU1 (vu1_analisa.py / vu1_tradutor.py): decodificação, uso de registradores
# (espelho de decodeUpperUsage/decodeLowerUsage do ps2_vu1_core.cpp), alcance de um programa a partir do pc
# inicial e o hash dele. O alcance e o hash são repetidos em C++ (ps2_vu1_nativo.h, vu1n::programa) e os dois
# têm que dar o mesmo resultado.
import struct

TAM_CODIGO = 0x4000
MASCARA_PC = 0x3FFF

UPPER = {}
for _i, _n in enumerate(['ADD', 'SUB', 'MADD', 'MSUB', 'MAX', 'MINI', 'MUL']):
    for _bc in range(4):
        UPPER[_i * 4 + _bc] = _n + 'bc'
UPPER.update({0x1C: 'MULq', 0x1D: 'MAXi', 0x1E: 'MULi', 0x1F: 'MINIi', 0x20: 'ADDq', 0x21: 'MADDq', 0x22: 'ADDi',
              0x23: 'MADDi', 0x24: 'SUBq', 0x25: 'MSUBq', 0x26: 'SUBi', 0x27: 'MSUBi', 0x28: 'ADD', 0x29: 'MADD',
              0x2A: 'MUL', 0x2B: 'MAX', 0x2C: 'SUB', 0x2D: 'MSUB', 0x2E: 'OPMSUB', 0x2F: 'MINI'})
UPPER_ESP = {}
for _i, _n in enumerate(['ADDA', 'SUBA', 'MADDA', 'MSUBA']):
    for _bc in range(4):
        UPPER_ESP[_i * 4 + _bc] = _n + 'bc'
UPPER_ESP.update({0x10: 'ITOF0', 0x11: 'ITOF4', 0x12: 'ITOF12', 0x13: 'ITOF15', 0x14: 'FTOI0', 0x15: 'FTOI4',
                  0x16: 'FTOI12', 0x17: 'FTOI15', 0x18: 'MULAbc', 0x19: 'MULAbc', 0x1A: 'MULAbc', 0x1B: 'MULAbc',
                  0x1C: 'MULAq', 0x1D: 'ABS', 0x1E: 'MULAi', 0x1F: 'CLIP', 0x20: 'ADDAq', 0x21: 'MADDAq',
                  0x22: 'ADDAi', 0x23: 'MADDAi', 0x24: 'SUBAq', 0x25: 'MSUBAq', 0x26: 'SUBAi', 0x27: 'MSUBAi',
                  0x28: 'ADDA', 0x29: 'MADDA', 0x2A: 'MULA', 0x2C: 'SUBA', 0x2D: 'MSUBA', 0x2E: 'OPMULA',
                  0x2F: 'NOP', 0x30: 'NOP'})
LOWER = {0x00: 'LQ', 0x01: 'SQ', 0x04: 'ILW', 0x05: 'ISW', 0x08: 'IADDIU', 0x09: 'ISUBIU', 0x10: 'FCEQ',
         0x11: 'FCSET', 0x12: 'FCAND', 0x13: 'FCOR', 0x14: 'FSEQ', 0x15: 'FSSET', 0x16: 'FSAND', 0x17: 'FSOR',
         0x18: 'FMEQ', 0x1A: 'FMAND', 0x1B: 'FMOR', 0x1C: 'FCGET', 0x20: 'B', 0x21: 'BAL', 0x24: 'JR',
         0x25: 'JALR', 0x28: 'IBEQ', 0x29: 'IBNE', 0x2C: 'IBLTZ', 0x2D: 'IBGTZ', 0x2E: 'IBLEZ', 0x2F: 'IBGEZ'}
LOWER1 = {0x30: 'IADD', 0x31: 'ISUB', 0x32: 'IADDI', 0x34: 'IAND', 0x35: 'IOR'}
LOWER_ESP = {0x30: 'MOVE', 0x31: 'MR32', 0x34: 'LQI', 0x35: 'SQI', 0x36: 'LQD', 0x37: 'SQD', 0x38: 'DIV',
             0x39: 'SQRT', 0x3A: 'RSQRT', 0x3B: 'WAITQ', 0x3C: 'MTIR', 0x3D: 'MFIR', 0x3E: 'ILWR', 0x3F: 'ISWR',
             0x40: 'RNEXT', 0x41: 'RGET', 0x42: 'RINIT', 0x43: 'RXOR', 0x64: 'MFP', 0x68: 'XTOP', 0x69: 'XITOP',
             0x6C: 'XGKICK', 0x70: 'ESADD', 0x71: 'ERSADD', 0x72: 'ELENG', 0x73: 'ERLENG', 0x74: 'EATANxy',
             0x75: 'EATANxz', 0x76: 'ESUM', 0x78: 'ESQRT', 0x79: 'ERSQRT', 0x7A: 'ERCPR',
             0x7B: 'WAITP', 0x7C: 'ESIN', 0x7D: 'EATAN', 0x7E: 'EEXP'}  # Otavix 31/10: como o PS2/PCSX2

DESVIOS_DIRETOS = ('B', 'BAL', 'IBEQ', 'IBNE', 'IBLTZ', 'IBGTZ', 'IBLEZ', 'IBGEZ')
DESVIOS = DESVIOS_DIRETOS + ('JR', 'JALR')


def esp_upper(u):
    return (u & 3) | ((u >> 4) & 0x7C)


def nome_upper(u):
    f = u & 0x3F
    if f >= 0x3C:
        return UPPER_ESP.get(esp_upper(u), 'U?%03x' % esp_upper(u))
    return UPPER.get(f, 'U?%02x' % f)


def nome_lower(l):
    if l == 0 or l == 0x8000033C:
        return 'NOP'
    op = (l >> 25) & 0x7F
    if op == 0x40:
        f = l & 0x3F
        if f >= 0x3C:
            return LOWER_ESP.get((l & 3) | ((l >> 4) & 0x7C), 'L?%03x' % ((l & 3) | ((l >> 4) & 0x7C)))
        return LOWER1.get(f, 'L1?%02x' % f)
    return LOWER.get(op, 'L?%02x' % op)


def nome_par(lower, upper):
    return nome_upper(upper), ('LOI' if upper & 0x80000000 else nome_lower(lower))


def imm11(l):
    v = l & 0x7FF
    return v - 0x800 if v & 0x400 else v


def DEST(i): return (i >> 21) & 0xF
def FT(i): return (i >> 16) & 0x1F
def FS(i): return (i >> 11) & 0x1F
def FD(i): return (i >> 6) & 0x1F
def VIT(i): return (i >> 16) & 0xF
def VIS(i): return (i >> 11) & 0xF
def VID(i): return (i >> 6) & 0xF
def LANE(c): return 1 << (3 - c)


class Uso:
    """Espelho de InstructionUsage."""

    def __init__(self):
        self.vf_le = {}          # reg -> lanes
        self.vf_escreve = (0, 0)  # (reg, lanes)
        self.vi_le = set()
        self.vi_escreve = set()
        self.latencia = 0
        self.lat_vf = 0
        self.lat_vi = 0
        self.pipe = None          # 'fmac' 'lsu' 'fdiv' 'efu' 'ialu' 'desvio' 'xgkick'
        self.wait_q = False
        self.wait_p = False
        self.atrasa_desvio = False
        self.reservada = False

    def le_vf(self, reg, lanes):
        if lanes:
            self.vf_le[reg] = self.vf_le.get(reg, 0) | lanes

    def escreve_vf(self, reg, lanes):
        if reg == 0 or lanes == 0:
            return
        r, l = self.vf_escreve
        if r == 0:
            self.vf_escreve = (reg, lanes)
        elif r == reg:
            self.vf_escreve = (reg, l | lanes)

    def le_vi(self, reg):
        if reg:
            self.vi_le.add(reg)

    def escreve_vi(self, reg):
        if reg:
            self.vi_escreve.add(reg)

    def lat_vf_efetiva(self):
        return self.lat_vf or self.latencia

    def lat_vi_efetiva(self):
        return self.lat_vi or self.latencia


ACC_LE_UPPER = {0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x21, 0x23, 0x25, 0x27, 0x29, 0x2D, 0x2E}


def uso_upper(u):
    us = Uso()
    us.pipe = 'fmac'
    us.latencia = 4
    op = u & 0x3F
    dest, fs, ft, fd = DEST(u), FS(u), FT(u), FD(u)
    if op <= 0x2F:
        us.le_vf(fs, dest)
        us.escreve_vf(fd, dest)
        if op <= 0x1B:
            us.le_vf(ft, LANE(op & 3))
        elif op >= 0x28:
            us.le_vf(ft, 0xE if op == 0x2E else dest)
        return us
    if op >= 0x3C:
        sp = esp_upper(u)
        escreve_acc = (sp <= 0x0F or 0x18 <= sp <= 0x1C or sp == 0x1E or 0x20 <= sp <= 0x2A or 0x2C <= sp <= 0x2E)
        if escreve_acc:
            us.le_vf(fs, dest)
            if sp <= 0x1B:
                us.le_vf(ft, LANE(sp & 3))
            elif 0x28 <= sp <= 0x2E:
                us.le_vf(ft, 0xE if sp == 0x2E else dest)
        elif 0x10 <= sp <= 0x17 or sp == 0x1D:
            us.le_vf(fs, dest)
            us.escreve_vf(ft, dest)
        elif sp == 0x1F:
            us.le_vf(fs, 0xE)
            us.le_vf(ft, 0x1)
        elif sp not in (0x2F, 0x30):
            us.reservada = True
        return us
    us.reservada = True
    return us


def uso_lower(l):
    us = Uso()
    if l == 0 or l == 0x8000033C:
        return us
    op = (l >> 25) & 0x7F
    vfT, vfS, viT, viS, viD, dest = FT(l), FS(l), VIT(l), VIS(l), VID(l), DEST(l)
    if op == 0x00:
        us.pipe, us.latencia = 'lsu', 4
        us.le_vi(viS); us.escreve_vf(vfT, dest)
    elif op == 0x01:
        us.pipe, us.latencia = 'lsu', 1
        us.le_vi(viT); us.le_vf(vfS, dest)
    elif op == 0x04:
        us.pipe, us.latencia = 'lsu', 4
        us.le_vi(viS); us.escreve_vi(viT)
    elif op == 0x05:
        us.pipe, us.latencia = 'lsu', 1
        us.le_vi(viS); us.le_vi(viT)
    elif op in (0x08, 0x09):
        us.pipe, us.latencia, us.atrasa_desvio = 'ialu', 1, True
        us.le_vi(viS); us.escreve_vi(viT)
    elif op in (0x10, 0x12, 0x13):
        us.pipe, us.latencia = 'ialu', 1
        us.escreve_vi(1)
    elif op == 0x11:
        us.pipe, us.latencia = 'fmac', 4
    elif op in (0x14, 0x16, 0x17):
        us.pipe, us.latencia = 'ialu', 1
        us.escreve_vi(viT)
    elif op == 0x15:
        us.pipe, us.latencia = 'fmac', 4
    elif op in (0x18, 0x1A, 0x1B):
        us.pipe, us.latencia = 'ialu', 1
        us.le_vi(viS); us.escreve_vi(viT)
    elif op == 0x1C:
        us.pipe, us.latencia = 'ialu', 1
        us.escreve_vi(viT)
    elif op == 0x20:
        us.pipe = 'desvio'
    elif op == 0x21:
        us.pipe, us.latencia = 'desvio', 1
        us.escreve_vi(viT)
    elif op == 0x24:
        us.pipe = 'desvio'
        us.le_vi(viS)
    elif op == 0x25:
        us.pipe, us.latencia = 'desvio', 1
        us.le_vi(viS); us.escreve_vi(viT)
    elif op in (0x28, 0x29):
        us.pipe = 'desvio'
        us.le_vi(viS); us.le_vi(viT)
    elif op in (0x2C, 0x2D, 0x2E, 0x2F):
        us.pipe = 'desvio'
        us.le_vi(viS)
    elif op == 0x40:
        f = l & 0x3F
        if f in (0x30, 0x31, 0x34, 0x35):
            us.pipe, us.latencia, us.atrasa_desvio = 'ialu', 1, True
            us.le_vi(viS); us.le_vi(viT); us.escreve_vi(viD)
        elif f == 0x32:
            us.pipe, us.latencia, us.atrasa_desvio = 'ialu', 1, True
            us.le_vi(viS); us.escreve_vi(viT)
        elif f < 0x3C:
            us.reservada = True
        else:
            sp = (l & 3) | ((l >> 4) & 0x7C)
            c21, c23 = (l >> 21) & 3, (l >> 23) & 3
            if sp in (0x30, 0x31):
                us.pipe, us.latencia = 'fmac', 4
                us.le_vf(vfS, 0xF if sp == 0x31 else dest); us.escreve_vf(vfT, dest)
            elif sp in (0x34, 0x36):
                us.pipe, us.latencia, us.lat_vi, us.atrasa_desvio = 'lsu', 4, 1, True
                us.le_vi(viS); us.escreve_vi(viS); us.escreve_vf(vfT, dest)
            elif sp in (0x35, 0x37):
                us.pipe, us.latencia, us.atrasa_desvio = 'lsu', 1, True
                us.le_vi(viT); us.escreve_vi(viT); us.le_vf(vfS, dest)
            elif sp == 0x38:
                us.pipe, us.latencia = 'fdiv', 7
                us.le_vf(vfS, LANE(c21)); us.le_vf(vfT, LANE(c23))
            elif sp == 0x39:
                us.pipe, us.latencia = 'fdiv', 7
                us.le_vf(vfT, LANE(c23))
            elif sp == 0x3A:
                us.pipe, us.latencia = 'fdiv', 13
                us.le_vf(vfS, LANE(c21)); us.le_vf(vfT, LANE(c23))
            elif sp == 0x3B:
                us.pipe, us.wait_q = 'fdiv', True
            elif sp == 0x3C:
                us.pipe, us.latencia, us.atrasa_desvio = 'ialu', 1, True
                us.le_vf(vfS, LANE(c21)); us.escreve_vi(viT)
            elif sp == 0x3D:
                us.pipe, us.latencia = 'fmac', 4
                us.le_vi(viS); us.escreve_vf(vfT, dest)
            elif sp == 0x3E:
                us.pipe, us.latencia = 'lsu', 4
                us.le_vi(viS); us.escreve_vi(viT)
            elif sp == 0x3F:
                us.pipe, us.latencia = 'lsu', 1
                us.le_vi(viS); us.le_vi(viT)
            elif sp in (0x40, 0x41):
                us.pipe, us.latencia = 'fmac', 4
                us.escreve_vf(vfT, dest)
            elif sp in (0x42, 0x43):
                us.pipe, us.latencia = 'ialu', 1
                us.le_vf(vfS, LANE(c21))
            elif sp == 0x64:
                us.pipe, us.latencia = 'fmac', 4
                us.escreve_vf(vfT, dest)
            elif sp in (0x68, 0x69):
                us.pipe, us.latencia = 'ialu', 1
                us.escreve_vi(viT)
            elif sp == 0x6C:
                us.pipe, us.latencia = 'xgkick', 2
                us.le_vi(viS)
            elif sp in (0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x78, 0x79, 0x7A, 0x7C, 0x7D, 0x7E):
                # Otavix 31/10: códigos EFU como o PS2/PCSX2 (ERSQRT 0x79, ESIN 0x7C, EATAN 0x7D, EEXP 0x7E)
                us.pipe = 'efu'
                us.latencia = {0x70: 11, 0x71: 18, 0x72: 18, 0x79: 18, 0x73: 24, 0x74: 54, 0x75: 54, 0x7D: 54,
                               0x76: 12, 0x78: 12, 0x7A: 12, 0x7C: 29, 0x7E: 44}[sp]
                if 0x70 <= sp <= 0x73:
                    us.le_vf(vfS, 0xE)
                elif sp == 0x74:
                    us.le_vf(vfS, 0xC)
                elif sp == 0x75:
                    us.le_vf(vfS, 0xA)
                elif sp == 0x76:
                    us.le_vf(vfS, 0xF)
                else:
                    us.le_vf(vfS, LANE(c21))
            elif sp == 0x7B:
                us.pipe, us.wait_p = 'efu', True
            else:
                us.reservada = True
    else:
        us.reservada = True
    return us


class Par:
    def __init__(self, code, pc):
        self.pc = pc
        self.lower, self.upper = struct.unpack_from('<II', code, pc)
        u = self.upper
        self.ibit = bool(u & 0x80000000)
        self.ebit = bool(u & 0x40000000)
        self.mbit = bool(u & 0x20000000)
        self.dbit = bool(u & 0x10000000)
        self.tbit = bool(u & 0x08000000)
        self.nu, self.nl = nome_par(self.lower, u)
        self.uu = uso_upper(u)
        self.ul = Uso() if self.ibit else uso_lower(self.lower)
        r = self.uu.vf_escreve[0]
        self.sombra = 0
        self.suprime_vf_inferior = 0
        if r and (r in self.ul.vf_le or self.ul.vf_escreve[0] == r):
            self.sombra = r
            if self.ul.vf_escreve[0] == r:
                self.suprime_vf_inferior = r

    def desvio(self):
        return None if self.ibit or self.nl not in DESVIOS else self.nl

    def alvo(self):
        return (self.pc + 8 + imm11(self.lower) * 8) & MASCARA_PC


def programa(code, inicio):
    """inicio: pc ou lista de pcs (entradas extras)."""
    """Pares alcançáveis a partir de 'inicio'. Um par é 'incluído' quando pode executar; 'explorado' quando o fluxo
    passa por ele normalmente (delay slots são incluídos sem seguir adiante, a não ser que outro caminho chegue
    neles). Desvio dentro de delay slot: o alvo entra como início extra. Devolve (pares, indiretos)."""
    tam = len(code)
    incluidos = set()
    explorados = set()
    inicios = inicio if isinstance(inicio, (list, tuple)) else [inicio]
    pend = [a & (tam - 1) for a in inicios]
    indiretos = 0

    def delay_slot(a):
        nonlocal indiretos
        a &= tam - 1
        incluidos.add(a)
        lower, upper = struct.unpack_from('<II', code, a)
        if upper & 0x80000000:
            return
        nl = nome_lower(lower)
        if nl in DESVIOS_DIRETOS:
            pend.append((a + 8 + imm11(lower) * 8) & (tam - 1))
            pend.append((a + 8) & (tam - 1))
        elif nl in ('JR', 'JALR'):
            indiretos += 1
            pend.append((a + 8) & (tam - 1))

    while pend:
        pc = pend.pop()
        while True:
            pc &= tam - 1
            if pc in explorados:
                break
            explorados.add(pc)
            incluidos.add(pc)
            lower, upper = struct.unpack_from('<II', code, pc)
            ibit = bool(upper & 0x80000000)
            nl = 'LOI' if ibit else nome_lower(lower)
            if upper & 0x40000000:
                delay_slot(pc + 8)
                break
            if nl in DESVIOS_DIRETOS:
                pend.append((pc + 8 + imm11(lower) * 8) & (tam - 1))
                delay_slot(pc + 8)
                if nl == 'B':
                    break
                if nl == 'BAL':
                    pend.append(pc + 16)
                pc = pc + 16
                continue
            if nl in ('JR', 'JALR'):
                indiretos += 1
                delay_slot(pc + 8)
                if nl == 'JALR':
                    pend.append(pc + 16)
                break
            pc = pc + 8
    return sorted(incluidos), indiretos


def hash_programa(code, pares):
    """FNV-1a 64 sobre (LE32 endereço + 8 bytes do par), em ordem de endereço (igual ao vu1n::hashPrograma)."""
    h = 1469598103934665603
    for a in pares:
        for b in struct.pack('<I', a) + code[a:a + 8]:
            h ^= b
            h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return h
