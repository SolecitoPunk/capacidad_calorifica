#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera presentacion_sommerfeld.pptx (16:9, estilo "limones") con la biblioteca estándar.

- Ecuaciones nativas de PowerPoint (OMML): se editan con doble clic, igual que
  las de Insertar > Ecuación. Programas sin soporte (p. ej. Google Slides) usan
  una versión en texto plano.
- Gráficas: presentacion/img/*.png; adornos: presentacion/img/deco/*.png
  (ilustraciones propias, inspiradas en la plantilla "Mantis & Lemon").
- Si existen los GIF de ../animaciones/ (python animaciones.py), se usan en
  lugar de la imagen estática de las diapositivas 4, 7, 9 y 11.
- Notas del orador: presentacion/notas_guion.json.

Fuentes: IM Fell English (títulos) y Arimo (texto), gratuitas en Google Fonts.
Si no están instaladas, PowerPoint las sustituye; Google Slides ya las tiene.

Uso (desde la carpeta del repositorio):
    python presentacion/generar_pptx.py
"""

import json
import os
import re
import struct
import zipfile
from datetime import datetime, timezone
from xml.sax.saxutils import escape

AQUI = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(AQUI, "img")
DECO = os.path.join(IMG, "deco")
ANIM = os.path.join(AQUI, "..", "animaciones")
SALIDA = os.path.join(AQUI, "presentacion_sommerfeld.pptx")

EMU = 914400                      # EMU por pulgada
SW, SH = 12192000, 6858000        # 13.333 x 7.5 in (16:9)
W_IN, H_IN = SW / EMU, SH / EMU

# Paleta (amarillo limón, verde oliva, café, menta, crema) y fuentes
AMARILLO, AMARILLO2 = "F6C445", "C98E1C"
OLIVA, OLIVA2 = "66744F", "4C573A"
CAFE, MENTA, CREMA, PAPEL = "8B4A20", "D5E0CB", "FFF8E6", "FFFDF5"
AZUL = "5B78B5"
TEXTO = "3B3A33"
GRIS = "7A7462"
BORDE = "D8CCA8"
COLOR = {"Sebastián": OLIVA, "Joan": CAFE, "Jorge": AZUL}
PARTE = {"Sebastián": "I · EL PROBLEMA FÍSICO", "Joan": "II · MÉTODOS NUMÉRICOS",
         "Jorge": "III · RESULTADOS"}
F_TIT, F_TXT, F_MAT = "IM Fell English", "Arimo", "Cambria Math"

NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')
NS_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
NS_A14 = "http://schemas.microsoft.com/office/drawing/2010/main"
NS_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
RT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


def inch(x):
    return int(round(x * EMU))


# =============================================================================
# Texto enriquecido: **negrita**, _{subíndice}, ^{superíndice}
# =============================================================================
def runs(texto, size, color=TEXTO, bold=False, italic=False, fuente=F_TXT, spc=0):
    if "**" in texto:
        trozos = re.split(r"(\*\*.*?\*\*)", texto)
        return "".join(runs(tz[2:-2], size, color, True, italic, fuente, spc) if tz.startswith("**")
                       else runs(tz, size, color, bold, italic, fuente, spc) for tz in trozos if tz)
    out = []
    for p in re.split(r"(_\{.*?\}|\^\{.*?\})", texto):
        if not p:
            continue
        base, t = 0, p
        if p.startswith("_{"):
            base, t = -25000, p[2:-1]
        elif p.startswith("^{"):
            base, t = 30000, p[2:-1]
        attrs = f'lang="es-CO" sz="{int(size * 100)}" b="{int(bold)}" i="{int(italic)}" dirty="0"'
        if base:
            attrs += f' baseline="{base}"'
        if spc:
            attrs += f' spc="{spc}"'
        out.append(f'<a:r><a:rPr {attrs}><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
                   f'<a:latin typeface="{fuente}"/><a:cs typeface="{fuente}"/></a:rPr>'
                   f'<a:t>{escape(t)}</a:t></a:r>')
    return "".join(out)


def parrafo(texto, size, color=TEXTO, bold=False, italic=False, align="l", bullet=False,
            nivel=0, antes=6, fuente=F_TXT, spc=0, interlineado=None):
    ppr = f'<a:pPr algn="{align}"'
    if bullet:
        ppr += f' marL="{342900 + nivel * 342900}" indent="-285750"'
    ppr += '>'
    if interlineado:
        ppr += f'<a:lnSpc><a:spcPct val="{int(interlineado * 1000)}"/></a:lnSpc>'
    ppr += f'<a:spcBef><a:spcPts val="{antes * 100}"/></a:spcBef>'
    if bullet:
        ppr += (f'<a:buClr><a:srgbClr val="{AMARILLO2 if nivel == 0 else OLIVA}"/></a:buClr>'
                f'<a:buFont typeface="Arial"/><a:buChar char="{"•" if nivel == 0 else "–"}"/>')
    else:
        ppr += '<a:buNone/>'
    ppr += '</a:pPr>'
    return (f'<a:p>{ppr}{runs(texto, size, color, bold, italic, fuente, spc)}'
            f'<a:endParaRPr lang="es-CO" sz="{int(size * 100)}" dirty="0"/></a:p>')


def titulo_p(texto, size, color=CAFE, align="l"):
    return parrafo(texto, size, color, False, True, align, antes=0, fuente=F_TIT)


def etiqueta_p(texto, size=12, color=AMARILLO2, align="l"):
    return parrafo(texto, size, color, True, False, align, antes=0, spc=300)


def vinetas(items, size=19):
    ps = []
    for it in items:
        nivel = 1 if it.startswith("- ") else 0
        ps.append(parrafo(it[2:] if nivel else it, size - 2 * nivel, bullet=True, nivel=nivel,
                          antes=10 if nivel == 0 else 3))
    return ps


# =============================================================================
# Ecuaciones OMML (editor de ecuaciones de PowerPoint)
# =============================================================================
class Mat:
    """Construye OMML. size en pt; color hex. Las letras van en cursiva y los
    números/operadores en redonda, como en el editor de ecuaciones."""

    def __init__(self, size=24, color=TEXTO):
        self.size, self.color = size, color

    def _rpr(self, italic):
        return (f'<a:rPr lang="es-CO" sz="{int(self.size * 100)}" i="{int(italic)}" dirty="0">'
                f'<a:solidFill><a:srgbClr val="{self.color}"/></a:solidFill>'
                f'<a:latin typeface="{F_MAT}" panose="02040503050406030204" pitchFamily="18" charset="0"/></a:rPr>')

    def ctrl(self):
        return f'<m:ctrlPr>{self._rpr(True)}</m:ctrlPr>'

    def v(self, t):                    # variable (cursiva)
        return f'<m:r>{self._rpr(True)}<m:t>{escape(t)}</m:t></m:r>'

    def n(self, t):                    # número / operador / texto recto
        return (f'<m:r><m:rPr><m:sty m:val="p"/></m:rPr>{self._rpr(False)}'
                f'<m:t xml:space="preserve">{escape(t)}</m:t></m:r>')

    def f(self, num, den):
        return f'<m:f><m:fPr>{self.ctrl()}</m:fPr><m:num>{num}</m:num><m:den>{den}</m:den></m:f>'

    def sub(self, e, s):
        return f'<m:sSub><m:sSubPr>{self.ctrl()}</m:sSubPr><m:e>{e}</m:e><m:sub>{s}</m:sub></m:sSub>'

    def sup(self, e, s):
        return f'<m:sSup><m:sSupPr>{self.ctrl()}</m:sSupPr><m:e>{e}</m:e><m:sup>{s}</m:sup></m:sSup>'

    def subsup(self, e, s, p):
        return (f'<m:sSubSup><m:sSubSupPr>{self.ctrl()}</m:sSubSupPr><m:e>{e}</m:e>'
                f'<m:sub>{s}</m:sub><m:sup>{p}</m:sup></m:sSubSup>')

    def integral(self, lo, hi, cuerpo):
        lims = f'<m:sub>{lo}</m:sub><m:sup>{hi}</m:sup>' if lo or hi else '<m:sub/><m:sup/>'
        oc = '' if lo or hi else '<m:subHide m:val="1"/><m:supHide m:val="1"/>'
        return (f'<m:nary><m:naryPr><m:limLoc m:val="subSup"/>{oc}{self.ctrl()}</m:naryPr>'
                f'{lims}<m:e>{cuerpo}</m:e></m:nary>')

    def raiz(self, e):
        return (f'<m:rad><m:radPr><m:degHide m:val="1"/>{self.ctrl()}</m:radPr>'
                f'<m:deg/><m:e>{e}</m:e></m:rad>')

    def par(self, e, beg="(", end=")"):
        bc = "" if beg == "(" else f'<m:begChr m:val="{escape(beg)}"/>'
        ec = "" if end == ")" else f'<m:endChr m:val="{escape(end)}"/>'
        return f'<m:d><m:dPr>{bc}{ec}{self.ctrl()}</m:dPr><m:e>{e}</m:e></m:d>'


# =============================================================================
# Diapositiva
# =============================================================================
class Diapositiva:
    def __init__(self, notas=""):
        self.formas, self.rels, self.next_id, self.notas = [], [], 1, notas

    def _id(self):
        self.next_id += 1
        return self.next_id

    def _sp(self, i, x, y, w, h, cuerpo, fill=None, linea=None, geom="rect", anchor="t",
            margen=0.08, nombre="Texto", guion=False, txbox=False, autofit=True):
        relleno = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else '<a:noFill/>'
        if linea:
            dash = '<a:prstDash val="dash"/>' if guion else ''
            ln = f'<a:ln w="19050"><a:solidFill><a:srgbClr val="{linea}"/></a:solidFill>{dash}</a:ln>'
        else:
            ln = '<a:ln><a:noFill/></a:ln>'
        m = inch(margen)
        fit = '<a:normAutofit/>' if autofit else ''
        cnv = '<p:cNvSpPr txBox="1"/>' if txbox else '<p:cNvSpPr/>'
        return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="{nombre} {i}"/>'
                f'{cnv}<p:nvPr/></p:nvSpPr>'
                f'<p:spPr><a:xfrm><a:off x="{inch(x)}" y="{inch(y)}"/><a:ext cx="{inch(w)}" cy="{inch(h)}"/></a:xfrm>'
                f'<a:prstGeom prst="{geom}"><a:avLst/></a:prstGeom>{relleno}{ln}</p:spPr>'
                f'<p:txBody><a:bodyPr wrap="square" lIns="{m}" tIns="{m}" rIns="{m}" bIns="{m}" anchor="{anchor}">'
                f'{fit}</a:bodyPr><a:lstStyle/>{cuerpo or "<a:p/>"}</p:txBody></p:sp>')

    def caja(self, x, y, w, h, parrafos, **kw):
        self.formas.append(self._sp(self._id(), x, y, w, h, "".join(parrafos), **kw))

    def ecuacion(self, x, y, w, h, omml, texto_plano, size=24, color=TEXTO, align="centerGroup", **kw):
        """Ecuación editable (OMML) con alternativa en texto plano."""
        i = self._id()
        p_mat = (f'<a:p><a14:m><m:oMathPara xmlns:m="{NS_M}"><m:oMathParaPr><m:jc m:val="{align}"/>'
                 f'</m:oMathParaPr><m:oMath>{omml}</m:oMath></m:oMathPara></a14:m>'
                 f'<a:endParaRPr lang="es-CO" sz="{int(size * 100)}" dirty="0"/></a:p>')
        jc = {"centerGroup": "ctr", "left": "l", "right": "r"}[align]
        p_txt = parrafo(texto_plano, size, color, align=jc, antes=0, fuente=F_MAT)
        kw.setdefault("anchor", "ctr")
        eleccion = self._sp(i, x, y, w, h, p_mat, nombre="Ecuación", txbox=True, autofit=False, **kw)
        alterna = self._sp(i, x, y, w, h, p_txt, nombre="Ecuación", txbox=True, autofit=False, **kw)
        self.formas.append(f'<mc:AlternateContent xmlns:mc="{NS_MC}">'
                           f'<mc:Choice xmlns:a14="{NS_A14}" Requires="a14">{eleccion}</mc:Choice>'
                           f'<mc:Fallback>{alterna}</mc:Fallback></mc:AlternateContent>')

    def imagen(self, ruta, x, y, w, h, ajustar=True):
        iw, ih = tamano_imagen(ruta)
        if ajustar:
            esc = min(w / iw, h / ih)
            cw, ch = iw * esc, ih * esc
            x, y = x + (w - cw) / 2, y + (h - ch) / 2
        else:
            cw, ch = w, h
        rid = f"rId{len(self.rels) + 2}"
        self.rels.append((rid, ruta))
        i = self._id()
        self.formas.append(
            f'<p:pic><p:nvPicPr><p:cNvPr id="{i}" name="Imagen {i}" descr="{escape(os.path.basename(ruta))}"/>'
            f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
            f'<p:spPr><a:xfrm><a:off x="{inch(x)}" y="{inch(y)}"/><a:ext cx="{inch(cw)}" cy="{inch(ch)}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')

    def tabla(self, x, y, anchos, filas, size=15, alto_fila=0.45):
        i = self._id()
        grid = "".join(f'<a:gridCol w="{inch(a)}"/>' for a in anchos)
        bordes = "".join(f'<a:ln{lado} w="9525"><a:solidFill><a:srgbClr val="{BORDE}"/></a:solidFill></a:ln{lado}>'
                         for lado in ("L", "R", "T", "B"))
        trs = []
        for k, fila in enumerate(filas):
            tcs = []
            for txt in fila:
                fill, col, b = (OLIVA, "FFFFFF", True) if k == 0 else ((PAPEL if k % 2 else "F3EBD3"), TEXTO, False)
                tcs.append(f'<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>{parrafo(txt, size, col, b, align="ctr", antes=0)}'
                           f'</a:txBody><a:tcPr marL="68580" marR="68580" marT="45720" marB="45720" anchor="ctr">'
                           f'{bordes}<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill></a:tcPr></a:tc>')
            trs.append(f'<a:tr h="{inch(alto_fila)}">{"".join(tcs)}</a:tr>')
        self.formas.append(
            f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{i}" name="Tabla {i}"/>'
            f'<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>'
            f'<p:xfrm><a:off x="{inch(x)}" y="{inch(y)}"/><a:ext cx="{inch(sum(anchos))}" cy="{inch(alto_fila * len(filas))}"/></p:xfrm>'
            f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">'
            f'<a:tbl><a:tblPr firstRow="1" bandRow="1"/><a:tblGrid>{grid}</a:tblGrid>{"".join(trs)}</a:tbl>'
            f'</a:graphicData></a:graphic></p:graphicFrame>')

    def xml(self):
        return (XML + f'<p:sld {NS}><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
                '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
                + "".join(self.formas) + '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>')


def tamano_imagen(ruta):
    with open(ruta, "rb") as f:
        cab = f.read(32)
    if cab[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", cab[16:24])
    if cab[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", cab[6:10])
    raise ValueError(f"Formato no soportado: {ruta}")


def img(nombre):
    return os.path.join(IMG, nombre + ".png")


def deco(nombre):
    return os.path.join(DECO, nombre + ".png")


def anim_o_img(gif, png):
    ruta = os.path.join(ANIM, gif + ".gif")
    return (ruta, True) if os.path.exists(ruta) else (img(png), False)


# =============================================================================
# Plantillas de diapositiva
# =============================================================================
X0, X1, Y0, Y1 = 0.7, W_IN - 0.7, 1.75, 6.75        # área útil de contenido


def base(num, titulo, orador, tiempo, notas):
    d = Diapositiva(notas)
    d.imagen(deco("marco"), 0, 0, W_IN, H_IN, ajustar=False)
    d.caja(0.62, 0.5, 9.0, 0.85, [titulo_p(titulo, 34)], anchor="b", margen=0.05, nombre="Título")
    d.caja(0.66, 1.3, 9.0, 0.35, [etiqueta_p(PARTE[orador])], anchor="t", margen=0.05, nombre="Sección")
    d.caja(W_IN - 3.45, 0.62, 2.75, 0.52,
           [parrafo(f"{orador} · {tiempo}", 14, "FFFFFF", True, align="ctr", antes=0)],
           fill=COLOR[orador], geom="roundRect", anchor="ctr", margen=0.03, nombre="Orador")
    d.imagen(deco("estrellas"), W_IN - 1.55, 1.2, 0.9, 0.45)
    d.caja(W_IN - 1.6, 6.82, 0.95, 0.3, [parrafo(f"{num} / 16", 11, GRIS, align="r", antes=0)],
           margen=0, nombre="Número")
    return d


def tarjeta(d, x, y, w, h, parrafos, fill=PAPEL, linea=BORDE, **kw):
    d.caja(x, y, w, h, parrafos, fill=fill, linea=linea, geom="roundRect", margen=0.15, **kw)


# =============================================================================
# Contenido
# =============================================================================
def construir(notas):
    def nota(i, extra=""):
        n = notas[i]
        return "\n\n".join([n["cabecera"]] + n["parrafos"] + ([extra] if extra else []))

    aviso_gif = ("[Imagen estática. Para la animación ejecute python animaciones.py y vuelva a "
                 "generar el pptx con python presentacion/generar_pptx.py, o inserte {g}.gif "
                 "con Insertar > Imagen.]")
    S = []

    # 1. Portada ------------------------------------------------------------
    d = Diapositiva(nota(0))
    d.imagen(deco("portada"), 0, 0, W_IN, H_IN, ajustar=False)
    d.caja(W_IN / 2 - 3.9, 1.35, 7.8, 4.2, [], fill=AMARILLO, linea=CAFE, geom="ellipse", guion=True)
    d.caja(W_IN / 2 - 3.4, 1.75, 6.8, 1.2, [titulo_p("Capacidad Calorífica", 46, OLIVA2, "ctr")],
           anchor="b", margen=0)
    d.caja(W_IN / 2 - 3.4, 2.95, 6.8, 0.9, [titulo_p("Electrónica a T finita", 34, OLIVA2, "ctr")],
           anchor="t", margen=0)
    d.caja(W_IN / 2 - 3.2, 3.9, 6.4, 0.45, [etiqueta_p("MODELO DE SOMMERFELD · SIMULACIÓN NUMÉRICA", 12, CAFE, "ctr")],
           margen=0)
    d.caja(W_IN / 2 - 3.2, 4.4, 6.4, 0.45, [parrafo("Física computacional · 2026", 14, OLIVA2, align="ctr", antes=0)],
           margen=0)
    d.caja(W_IN / 2 - 3.6, 5.8, 7.2, 0.6,
           [parrafo("Sebastián Sánchez  ·  Joan Tovar  ·  Jorge Garzón", 18, OLIVA2, True, align="ctr", antes=0)],
           fill=PAPEL, linea=OLIVA, geom="roundRect", anchor="ctr", margen=0.05)
    S.append(d)

    # 2. Motivación ---------------------------------------------------------
    d = base(2, "El enigma del calor específico", "Sebastián", "0:45–2:15", nota(1))
    m = Mat(24, CAFE)
    d.caja(X0, Y0, 6.0, 3.7, vinetas([
        "Gas clásico (equipartición): cada electrón aporta (3/2) k_{B}",
        "- En el cobre serían 12.5 J/(mol K), la mitad de la red",
        "El experimento mide apenas ~1 % de ese valor",
        "Sommerfeld (1928): los electrones son fermiones",
        "- Por el principio de Pauli solo se excitan los que están a ~k_{B}T de E_{F}"]))
    tarjeta(d, X0 + 0.1, 5.55, 5.8, 1.1, [], fill=MENTA, linea=OLIVA)
    d.ecuacion(X0 + 0.1, 5.55, 2.9, 1.1,
               m.sup(m.sub(m.v("C"), m.v("V")), m.n("clás")) + m.n("=") + m.f(m.n("3"), m.n("2")) + m.v("N") + m.sub(m.v("k"), m.n("B")),
               "C_V(clás) = (3/2) N k_B", 22, CAFE)
    d.ecuacion(X0 + 3.0, 5.55, 2.9, 1.1, m.sub(m.v("C"), m.v("V")) + m.n("=") + m.v("γ") + m.v("T"),
               "C_V = γ T", 26, OLIVA2)
    d.imagen(img("barras"), 6.85, Y0 - 0.05, 5.8, 5.0)
    S.append(d)

    # 3. Objetivos ----------------------------------------------------------
    d = base(3, "Objetivos", "Sebastián", "2:15–3:00", nota(2))
    tarjeta(d, X0, Y0, X1 - X0, 1.3, [
        etiqueta_p("OBJETIVO GENERAL", 13, CAFE),
        parrafo("Simular numéricamente la contribución electrónica a la capacidad calorífica de un metal "
                "integrando la densidad de estados y la distribución de Fermi-Dirac.", 18, antes=6)], fill=MENTA, linea=OLIVA)
    tarjeta(d, X0, 3.3, 5.85, 3.4, [
        etiqueta_p("OBJETIVOS ESPECÍFICOS", 13, CAFE),
        parrafo("**i.** Calcular la energía interna térmica integrando numéricamente g(E) · E · f(E,T).", 18, antes=14),
        parrafo("**ii.** Obtener C_{V}(T) por derivación numérica y contrastarla con la aproximación lineal de Sommerfeld.",
                18, antes=14)])
    tarjeta(d, X0 + 6.1, 3.3, 5.85, 3.4, [
        etiqueta_p("CÁLCULO NUMÉRICO", 13, CAFE),
        parrafo("**Ligadura:** Newton-Raphson para μ(T) conservando N", 18, antes=14),
        parrafo("**Cuadratura adaptativa:** Gauss-Kronrod para U(T)", 18, antes=12),
        parrafo("**Diferenciación:** C_{V} = dU/dT y coeficiente γ", 18, antes=12)])
    S.append(d)

    # 4. Modelo físico ------------------------------------------------------
    ruta, es_gif = anim_o_img("1_fermi_dirac", "fd")
    d = base(4, "El modelo: g(E) y Fermi-Dirac", "Sebastián", "3:00–4:45",
             nota(3, "" if es_gif else aviso_gif.format(g="animaciones/1_fermi_dirac")))
    m = Mat(22, TEXTO)
    E, T = m.v("E"), m.v("T")
    gE = m.v("g") + m.par(E)
    fET = m.v("f") + m.par(E + m.n(",") + T)
    kBT = m.sub(m.v("k"), m.n("B")) + T
    tarjeta(d, X0, Y0, X1 - X0, 1.15, [], fill=MENTA, linea=OLIVA)
    d.ecuacion(X0, Y0, 2.9, 1.15, gE + m.n("=") + m.f(m.n("3"), m.n("2")) + m.raiz(E), "g(E) = (3/2) √E", 22)
    d.ecuacion(X0 + 2.9, Y0, 3.2, 1.15,
               fET + m.n("=") + m.f(m.n("1"), m.sup(m.v("e"), m.f(E + m.n("−") + m.v("μ"), kBT)) + m.n("+1")),
               "f(E,T) = 1 / (e^((E−μ)/k_BT) + 1)", 22)
    d.ecuacion(X0 + 6.1, Y0, 2.9, 1.15, m.v("N") + m.n("=") + m.integral(m.n("0"), m.n("∞"), gE + fET + m.n(" d") + E),
               "N = ∫ g(E) f(E,T) dE", 22, OLIVA2)
    d.ecuacion(X0 + 9.0, Y0, 2.95, 1.15, m.v("U") + m.n("=") + m.integral(m.n("0"), m.n("∞"), E + gE + fET + m.n(" d") + E),
               "U = ∫ E g(E) f(E,T) dE", 22, OLIVA2)
    if es_gif:
        d.imagen(img("dos"), X0 - 0.1, 3.05, 4.3, 3.75)
        d.imagen(ruta, X0 + 4.25, 3.05, 7.8, 3.75)
    else:
        d.imagen(img("dos"), X0 - 0.1, 3.05, 6.0, 3.75)
        d.imagen(ruta, X0 + 5.95, 3.05, 6.0, 3.75)
    S.append(d)

    # 5. Unidades y predicción ---------------------------------------------
    d = base(5, "Unidades y predicción de Sommerfeld", "Sebastián", "4:45–6:30", nota(4))
    m = Mat(24, TEXTO)
    t2 = m.sup(m.v("t"), m.n("2"))
    pi2 = m.sup(m.v("π"), m.n("2"))
    tarjeta(d, X0, Y0, 5.5, 4.95, [etiqueta_p("VARIABLES ADIMENSIONALES", 13, CAFE)], fill=MENTA, linea=OLIVA)
    filas_izq = [
        (m.v("ε") + m.n("=") + m.f(m.v("E"), m.sub(m.v("E"), m.v("F"))) + m.n(",   ") + m.v("t") + m.n("=")
         + m.f(m.v("T"), m.sub(m.v("T"), m.v("F"))), "ε = E/E_F,  t = T/T_F"),
        (m.v("g") + m.par(m.v("ε")) + m.n("=") + m.f(m.n("3"), m.n("2")) + m.raiz(m.v("ε")) + m.n("  ⇒  ")
         + m.integral(m.n("0"), m.n("1"), m.v("g") + m.n(" d") + m.v("ε")) + m.n("=1"), "g(ε) = (3/2)√ε  ⇒  ∫₀¹ g dε = 1"),
        (m.v("U") + m.par(m.v("T") + m.n("=0")) + m.n("=") + m.f(m.n("3"), m.n("5")) + m.v("N") + m.sub(m.v("E"), m.v("F")),
         "U(T=0) = (3/5) N E_F"),
    ]
    for k, (om, tx) in enumerate(filas_izq):
        d.ecuacion(X0 + 0.1, Y0 + 0.55 + k * 1.15, 5.3, 1.1, om, tx, 22)
    d.caja(X0 + 0.2, Y0 + 4.05, 5.1, 0.8, [parrafo("Metal típico: T_{F} ~ 10^{4}–10^{5} K → a 300 K, t ~ 0.004", 15, GRIS, antes=0)],
           anchor="ctr", margen=0.05)
    tarjeta(d, X0 + 5.75, Y0, 6.2, 4.95, [etiqueta_p("EXPANSIÓN DE SOMMERFELD (t PEQUEÑO)", 13, CAFE)])
    filas_der = [
        (m.f(m.v("μ"), m.sub(m.v("E"), m.v("F"))) + m.n("=1−") + m.f(pi2, m.n("12")) + t2, "μ/E_F = 1 − (π²/12) t²"),
        (m.f(m.n("Δ") + m.v("U"), m.v("N") + m.sub(m.v("E"), m.v("F"))) + m.n("=") + m.f(pi2, m.n("4")) + t2,
         "ΔU/(N E_F) = (π²/4) t²"),
        (m.f(m.sub(m.v("C"), m.v("V")), m.v("N") + m.sub(m.v("k"), m.n("B"))) + m.n("=") + m.f(pi2, m.n("2")) + m.v("t"),
         "C_V/(N k_B) = (π²/2) t"),
    ]
    for k, (om, tx) in enumerate(filas_der):
        d.ecuacion(X0 + 5.85, Y0 + 0.5 + k * 1.05, 6.0, 1.0, om, tx, 24)
    m2 = Mat(30, COLOR["Sebastián"])
    d.ecuacion(X0 + 5.85, Y0 + 3.7, 6.0, 1.05,
               m2.v("γ") + m2.n("=") + m2.f(m2.sup(m2.v("π"), m2.n("2")), m2.n("2")) + m2.n("≈4.9348"), "γ = π²/2 ≈ 4.9348", 30,
               COLOR["Sebastián"])
    S.append(d)

    # 6. Esquema del algoritmo ---------------------------------------------
    d = base(6, "Esquema del algoritmo", "Joan", "6:30–7:30", nota(5))
    pasos = [("Rejilla de T", "200 valores de t entre 0.01 y 0.5"),
             ("Ligadura", "Newton-Raphson → μ(t) con N = 1"),
             ("Cuadratura adaptativa", "Gauss-Kronrod → U(t)"),
             ("Derivada numérica", "diferencias centrales → C_{V}(t)"),
             ("Ajuste", "mínimos cuadrados → γ")]
    colores = [OLIVA, CAFE, CAFE, AZUL, AZUL]
    bw, gap = 2.1, 0.36
    for k, ((t1, t2_), c) in enumerate(zip(pasos, colores)):
        x = X0 + k * (bw + gap)
        d.caja(x, 2.25, bw, 2.25, [parrafo(t1, 21, "FFFFFF", italic=True, align="ctr", antes=0, fuente=F_TIT),
                                   parrafo(t2_, 14, "FFFFFF", align="ctr", antes=10)],
               fill=c, geom="roundRect", anchor="ctr", margen=0.1)
        d.imagen(deco("limon"), x + bw / 2 - 0.35, 1.85, 0.7, 0.5)
        if k < len(pasos) - 1:
            d.caja(x + bw + 0.05, 3.2, gap - 0.1, 0.36, [], fill=AMARILLO2, geom="rightArrow")
    d.caja(X0, 4.85, X1 - X0, 0.5, [parrafo("Para cada temperatura: primero μ, luego U.   Con U en toda la rejilla: C_{V} y γ.",
                                            18, GRIS, align="ctr")])
    d.caja(3.0, 5.65, W_IN - 6.0, 0.65, [parrafo("Python · NumPy · SciPy · Matplotlib · GitHub", 18, OLIVA2, True,
                                                 align="ctr", antes=0)],
           fill=MENTA, linea=OLIVA, geom="roundRect", anchor="ctr")
    S.append(d)

    # 7. Newton -------------------------------------------------------------
    ruta, es_gif = anim_o_img("2_newton", "newton")
    d = base(7, "Ecuación de ligadura: Newton-Raphson", "Joan", "7:30–9:15",
             nota(6, "" if es_gif else aviso_gif.format(g="animaciones/2_newton")))
    m = Mat(22, CAFE)
    mu = m.v("μ")
    tarjeta(d, X0, Y0, 5.0, 2.65, [], fill=MENTA, linea=OLIVA)
    d.ecuacion(X0, Y0 + 0.05, 5.0, 0.85,
               m.v("F") + m.par(mu) + m.n("=") + m.integral(m.n("0"), m.sub(m.v("E"), m.n("max")), m.v("g f") + m.n(" d") + m.v("ε"))
               + m.n("−1=0"), "F(μ) = ∫ g f dε − 1 = 0", 22, CAFE)
    d.ecuacion(X0, Y0 + 0.9, 5.0, 0.85,
               m.sub(mu, m.v("k") + m.n("+1")) + m.n("=") + m.sub(mu, m.v("k")) + m.n("−")
               + m.f(m.v("F") + m.par(m.sub(mu, m.v("k"))), m.v("F") + m.n("′") + m.par(m.sub(mu, m.v("k")))),
               "μ_(k+1) = μ_k − F(μ_k)/F′(μ_k)", 22, CAFE)
    d.ecuacion(X0, Y0 + 1.75, 5.0, 0.85,
               m.v("F") + m.n("′") + m.n("=") + m.integral("", "", m.v("g") + m.par(m.n("−") + m.f(m.n("∂") + m.v("f"), m.n("∂") + m.v("ε")))
                                                         + m.n(" d") + m.v("ε")) + m.n(">0"),
               "F′ = ∫ g (−∂f/∂ε) dε > 0", 22, CAFE)
    d.caja(X0, 4.5, 5.0, 2.3, vinetas(["Salvaguarda: si el paso sale de [a, b], bisección",
                                       "Semilla: μ de la temperatura anterior",
                                       "3–4 iteraciones; Brent coincide a 1.4×10^{−14}"], 17))
    d.imagen(ruta, X0 + 5.2, Y0 - 0.1, 6.75, 5.15)
    S.append(d)

    # 8. Resultado mu(T) ----------------------------------------------------
    d = base(8, "Resultado: potencial químico μ(T)", "Joan", "9:15–10:30", nota(7))
    d.imagen(img("mu"), X0 - 0.1, Y0 - 0.05, 7.0, 4.95)
    d.imagen(img("newton_conv"), X0 + 7.05, Y0 - 0.05, 4.9, 3.2)
    tarjeta(d, X0 + 7.1, 4.95, 4.85, 1.8, vinetas(["t = 0.01: μ = 0.99991774 (Sommerfeld: 0.99991775)",
                                                   "t = 1: μ = −0.021 (régimen clásico)",
                                                   "max |N − 1| = 9.8×10^{−15}"], 14))
    S.append(d)

    # 9. Cuadratura ---------------------------------------------------------
    ruta, es_gif = anim_o_img("3_cuadratura", "integrando")
    d = base(9, "Integración adaptativa de U(T)", "Joan", "10:30–12:00",
             nota(8, "" if es_gif else aviso_gif.format(g="animaciones/3_cuadratura")))
    m = Mat(22, CAFE)
    eps = m.v("ε")
    tarjeta(d, X0, Y0, 5.0, 1.05, [], fill=MENTA, linea=OLIVA)
    d.ecuacion(X0, Y0, 5.0, 1.05,
               m.v("U") + m.n("=") + m.integral(m.n("0"), m.v("μ") + m.n("+40") + m.sub(m.v("k"), m.n("B")) + m.v("T"),
                                                eps + m.v("g") + m.par(eps) + m.v("f") + m.par(eps) + m.n(" d") + eps),
               "U = ∫₀^(μ+40k_BT) ε g(ε) f(ε) dε", 22, CAFE)
    d.caja(X0, 2.9, 5.0, 2.0, vinetas(["quad: Gauss-Kronrod adaptativo (QUADPACK)",
                                       "Subdivide solo donde el error es grande",
                                       "Punto de ruptura en ε = μ; tolerancia 10^{−13}"], 16))
    d.tabla(X0 + 0.2, 4.85, [2.3, 2.3], [["Corte E_{max}", "U (t = 0.1)"],
                                         ["μ + 10 t", "0.624262488730"],
                                         ["μ + 20 t", "0.624283104469"],
                                         ["μ + 40 t", "0.624283106151"]], size=13, alto_fila=0.42)
    d.imagen(ruta, X0 + 5.2, Y0 - 0.1, 6.75, 5.15)
    S.append(d)

    # 10. Delta U -----------------------------------------------------------
    d = base(10, "Energía térmica ΔU(T)", "Joan", "12:00–13:00", nota(9))
    m = Mat(24, CAFE)
    d.imagen(img("du"), X0 - 0.1, Y0 - 0.05, 7.4, 5.1)
    tarjeta(d, X0 + 7.45, Y0, 4.5, 1.1, [], fill=MENTA, linea=OLIVA)
    d.ecuacion(X0 + 7.45, Y0, 4.5, 1.1,
               m.n("Δ") + m.v("U") + m.n("=") + m.v("U") + m.par(m.v("T")) + m.n("−") + m.f(m.n("3"), m.n("5")) + m.v("N")
               + m.sub(m.v("E"), m.v("F")), "ΔU = U(T) − (3/5) N E_F", 22, CAFE)
    tarjeta(d, X0 + 7.45, 3.05, 4.5, 3.7, vinetas(["Crece como t², igual que Sommerfeld",
                                                   "Ajuste ΔU = a t² (t ≤ 0.05):",
                                                   "- a = 2.461   frente a   π²/4 = 2.467",
                                                   "La diferencia de 0.3 % es la corrección de orden t^{4}"], 17))
    S.append(d)

    # 11. Derivada ----------------------------------------------------------
    ruta, es_gif = anim_o_img("4_derivada_cv", "tangente")
    d = base(11, "Diferenciación numérica", "Jorge", "13:00–14:15",
             nota(10, "" if es_gif else aviso_gif.format(g="animaciones/4_derivada_cv")))
    m = Mat(21, AZUL)
    Ti = lambda s: m.v("U") + m.par(m.sub(m.v("T"), m.v("i") + m.n(s)))   # noqa: E731
    tarjeta(d, X0, Y0, 5.0, 1.25, [], fill=MENTA, linea=OLIVA)
    d.ecuacion(X0, Y0, 5.0, 1.25,
               m.sub(m.v("C"), m.v("V")) + m.par(m.sub(m.v("T"), m.v("i"))) + m.n("≈")
               + m.f(Ti("+1") + m.n("−") + Ti("−1"), m.n("2") + m.v("h")) + m.n("+") + m.v("O") + m.par(m.sup(m.v("h"), m.n("2"))),
               "C_V(T_i) ≈ [U(T_(i+1)) − U(T_(i−1))] / 2h + O(h²)", 21, AZUL)
    d.caja(X0, 3.15, 5.0, 3.6, vinetas(["Diferencias centrales: error O(h²)",
                                        "Extremos: fórmula de un lado, también de 2.º orden",
                                        "Derivar amplifica el ruido:",
                                        "- error 10^{−6} en U → ~0.5 % en C_{V} a la T más baja",
                                        "Por eso la integral necesita precisión de 10^{−13}"], 17))
    d.imagen(ruta, X0 + 5.2, Y0 - 0.1, 6.75, 5.15)
    S.append(d)

    # 12. C_V ---------------------------------------------------------------
    d = base(12, "C_{V}(T) frente a Sommerfeld", "Jorge", "14:15–15:45", nota(11))
    d.imagen(img("cv"), X0 - 0.15, Y0 - 0.1, 6.1, 4.25)
    d.imagen(img("razon"), X0 + 5.95, Y0 - 0.1, 6.1, 4.25)
    tarjeta(d, X0, 6.0, X1 - X0, 0.75, [parrafo(
        "Lineal a baja T  ·  t = 0.1: 96.7 %   t = 0.3: 71 %   t = 0.5: 51 % del valor lineal  ·  "
        "a t ~ 1 tiende al límite clásico 3/2", 15, GRIS, align="ctr", antes=0)], fill=MENTA, linea=OLIVA, anchor="ctr")
    S.append(d)

    # 13. Gamma -------------------------------------------------------------
    d = base(13, "Extracción del coeficiente lineal γ", "Jorge", "15:45–17:00", nota(12))
    m = Mat(24, AZUL)
    tarjeta(d, X0, Y0, 7.3, 1.0, [], fill=MENTA, linea=OLIVA)
    d.ecuacion(X0, Y0, 3.6, 1.0, m.sub(m.v("C"), m.v("V")) + m.n("=") + m.v("γ t") + m.n("+") + m.v("δ") + m.sup(m.v("t"), m.n("3")),
               "C_V = γ t + δ t³", 24, AZUL)
    d.ecuacion(X0 + 3.6, Y0, 3.7, 1.0,
               m.sub(m.v("δ"), m.n("teo")) + m.n("=−") + m.f(m.n("3") + m.sup(m.v("π"), m.n("4")), m.n("20")) + m.n("≈−14.61"),
               "δ_teo = −3π⁴/20 ≈ −14.61", 22, AZUL)
    d.tabla(X0, 2.95, [3.4, 2.1, 1.8], [
        ["Ajuste (t ≤ 0.05)", "γ", "Error"],
        ["C_{V} = γ t", "4.9117", "−0.47 %"],
        ["C_{V} = γ t + δ t³", "4.934927", "+0.0025 %"],
        ["Teoría: π²/2", "4.934802", "—"]], size=16, alto_fila=0.55)
    d.caja(X0, 5.25, 7.3, 1.5, vinetas(["El ajuste lineal puro ignora la corrección cúbica",
                                        "δ ajustado = −14.98 (teoría −14.61)"], 17))
    d.tabla(X0 + 7.65, Y0, [1.6, 2.7], [
        ["Puntos", "γ"], ["50", "4.933624"], ["100", "4.934682"], ["200", "4.934927"], ["400", "4.934981"]],
        size=16, alto_fila=0.55)
    tarjeta(d, X0 + 7.65, 4.75, 4.3, 1.2, [parrafo("Convergencia con el paso h: γ estable en la 4.ª cifra decimal",
                                                   15, GRIS, align="ctr", antes=0)], anchor="ctr")
    S.append(d)

    # 14. Cobre -------------------------------------------------------------
    d = base(14, "Aplicación a un metal real: el cobre", "Jorge", "17:00–18:30", nota(13))
    tarjetas = [("E_{F} = 7.0 eV", "T_{F} = 81 232 K", "a 300 K: t = 0.0037"),
                ("γ calculado", "0.505 mJ/(mol K²)", "electrones libres"),
                ("γ experimental", "0.695 mJ/(mol K²)", "→ m*/m ≈ 1.38"),
                ("C_{V} electrónica (300 K)", "0.15 J/(mol K)", "red: 3R = 24.9 J/(mol K)")]
    for k, (a, b, c) in enumerate(tarjetas):
        x = X0 + k * 3.03
        tarjeta(d, x, Y0, 2.85, 2.0, [parrafo(a, 15, GRIS, align="ctr", antes=0),
                                      parrafo(f"**{b}**", 20, AZUL, align="ctr", antes=10),
                                      parrafo(c, 14, GRIS, align="ctr", antes=10)], anchor="ctr")
    m = Mat(24, AZUL)
    tarjeta(d, X0, 4.0, 4.6, 1.3, [], fill=MENTA, linea=OLIVA)
    d.ecuacion(X0, 4.0, 4.6, 1.3,
               m.f(m.sup(m.v("m"), m.n("*")), m.v("m")) + m.n("≈") + m.f(m.sub(m.v("γ"), m.n("exp")), m.sub(m.v("γ"), m.n("teo")))
               + m.n("≈1.38"), "m*/m ≈ γ_exp/γ_teo ≈ 1.38", 24, AZUL)
    d.caja(X0 + 4.85, 3.9, 7.1, 2.85, vinetas([
        "El modelo no incluye el potencial de la red ni la interacción electrón-fonón",
        "A 300 K los electrones aportan ~1 % de lo que predice la física clásica",
        "A pocos kelvin domina el término electrónico: C/T = γ + βT²"], 17))
    S.append(d)

    # 15. Conclusiones ------------------------------------------------------
    d = base(15, "Conclusiones", "Jorge", "18:30–19:30", nota(14))
    concl = [("Ligadura", "Newton-Raphson salvaguardado: N se conserva a 10^{−14} en 3–4 iteraciones."),
             ("Integración", "Gauss-Kronrod adaptativo integra el escalón de Fermi-Dirac con precisión de 10^{−13}."),
             ("C_{V} y γ", "C_{V} es lineal a baja T; γ coincide con π²/2 dentro de 0.0025 %."),
             ("Más allá de Sommerfeld", "El cálculo muestra dónde falla la aproximación lineal y recupera el límite clásico 3/2.")]
    for k, (a, b) in enumerate(concl):
        y = Y0 + k * 1.22
        d.imagen(deco("limon"), X0, y + 0.12, 0.95, 0.68)
        d.caja(X0 + 0.15, y + 0.2, 0.65, 0.5, [parrafo(str(k + 1), 18, CAFE, True, align="ctr", antes=0)],
               anchor="ctr", margen=0)
        tarjeta(d, X0 + 1.15, y, X1 - X0 - 1.15, 1.0, [parrafo(f"**{a}:** {b}", 18, antes=0)], anchor="ctr")
    S.append(d)

    # 16. Cierre ------------------------------------------------------------
    d = Diapositiva(nota(15))
    d.imagen(deco("portada"), 0, 0, W_IN, H_IN, ajustar=False)
    d.caja(W_IN / 2 - 3.6, 1.4, 7.2, 3.9, [], fill=AMARILLO, linea=CAFE, geom="ellipse", guion=True)
    d.caja(W_IN / 2 - 3.2, 1.9, 6.4, 1.5, [titulo_p("¡Gracias!", 64, OLIVA2, "ctr")], anchor="b", margen=0)
    d.caja(W_IN / 2 - 3.2, 3.4, 6.4, 0.8, [titulo_p("¿Preguntas?", 34, CAFE, "ctr")], anchor="t", margen=0)
    d.caja(W_IN / 2 - 3.2, 4.25, 6.4, 0.45, [etiqueta_p("SEBASTIÁN · JOAN · JORGE", 12, CAFE, "ctr")], margen=0)
    d.caja(W_IN / 2 - 3.6, 5.8, 7.2, 0.6,
           [parrafo("github.com/SolecitoPunk/capacidad_calorifica", 16, OLIVA2, True, align="ctr", antes=0)],
           fill=PAPEL, linea=OLIVA, geom="roundRect", anchor="ctr", margen=0.05)
    S.append(d)
    return S


# =============================================================================
# Partes fijas del paquete (tema, maestros, diseños)
# =============================================================================
TEMA = XML + f'''<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Limones">
<a:themeElements>
<a:clrScheme name="Limones"><a:dk1><a:srgbClr val="{TEXTO}"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
<a:dk2><a:srgbClr val="{OLIVA2}"/></a:dk2><a:lt2><a:srgbClr val="{CREMA}"/></a:lt2>
<a:accent1><a:srgbClr val="{AMARILLO}"/></a:accent1><a:accent2><a:srgbClr val="{OLIVA}"/></a:accent2><a:accent3><a:srgbClr val="{CAFE}"/></a:accent3>
<a:accent4><a:srgbClr val="{MENTA}"/></a:accent4><a:accent5><a:srgbClr val="{AZUL}"/></a:accent5><a:accent6><a:srgbClr val="{AMARILLO2}"/></a:accent6>
<a:hlink><a:srgbClr val="{AZUL}"/></a:hlink><a:folHlink><a:srgbClr val="{CAFE}"/></a:folHlink></a:clrScheme>
<a:fontScheme name="Limones"><a:majorFont><a:latin typeface="{F_TIT}"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>
<a:minorFont><a:latin typeface="{F_TXT}"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>
<a:fmtScheme name="Limones">
<a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>
<a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="19050"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>
<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>
</a:fmtScheme></a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>'''

SPTREE_VACIO = ('<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
                '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>')
CLRMAP = ('<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" '
          'accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>')
NIVEL = ('<a:lvl1pPr marL="0" algn="l"><a:defRPr sz="1800"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill>'
         '<a:latin typeface="+mn-lt"/></a:defRPr></a:lvl1pPr>')

MAESTRO = (XML + f'<p:sldMaster {NS}><p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="{CREMA}"/></a:solidFill>'
           '<a:effectLst/></p:bgPr></p:bg>' + SPTREE_VACIO + '</p:spTree></p:cSld>' + CLRMAP
           + '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
           f'<p:txStyles><p:titleStyle>{NIVEL}</p:titleStyle><p:bodyStyle>{NIVEL}</p:bodyStyle>'
           f'<p:otherStyle>{NIVEL}</p:otherStyle></p:txStyles></p:sldMaster>')

DISENO = (XML + f'<p:sldLayout {NS} type="blank" preserve="1"><p:cSld name="En blanco">' + SPTREE_VACIO
          + '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>')

NSW, NSH = 6858000, 9144000


def ph_notas(i, nombre, tipo, x, y, w, h, idx, cuerpo=""):
    extra = '<a:picLocks noGrp="1" noRot="1" noChangeAspect="1"/>' if tipo == "sldImg" else '<a:spLocks noGrp="1"/>'
    xfrm = (f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>') if w else ""
    tx = f'<p:txBody><a:bodyPr/><a:lstStyle/>{cuerpo or "<a:p/>"}</p:txBody>' if tipo == "body" else ""
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="{nombre}"/><p:cNvSpPr>{extra}</p:cNvSpPr>'
            f'<p:nvPr><p:ph type="{tipo}" idx="{idx}"/></p:nvPr></p:nvSpPr><p:spPr>{xfrm}</p:spPr>{tx}</p:sp>')


MAESTRO_NOTAS = (XML + f'<p:notesMaster {NS}><p:cSld><p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef></p:bg>'
                 + SPTREE_VACIO
                 + ph_notas(2, "Imagen de diapositiva", "sldImg", 381000, 685800, 6096000, 3429000, 2)
                 + ph_notas(3, "Notas", "body", 685800, 4343400, 5486400, 4114800, 3)
                 + '</p:spTree></p:cSld>' + CLRMAP
                 + f'<p:notesStyle>{NIVEL.replace("1800", "1200")}</p:notesStyle></p:notesMaster>')


def nota_xml(texto):
    ps = "".join(f'<a:p><a:r><a:rPr lang="es-CO" sz="1200" dirty="0"/><a:t>{escape(linea)}</a:t></a:r></a:p>'
                 for linea in texto.split("\n"))
    return (XML + f'<p:notes {NS}><p:cSld>' + SPTREE_VACIO
            + ph_notas(2, "Imagen de diapositiva", "sldImg", 0, 0, 0, 0, 2)
            + ph_notas(3, "Notas", "body", 0, 0, 0, 0, 3, cuerpo=ps)
            + '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>')


def rels(lista):
    return (XML + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(f'<Relationship Id="{i}" Type="{t}" Target="{escape(d)}"/>' for i, t, d in lista)
            + '</Relationships>')


# =============================================================================
# Ensamblado del paquete
# =============================================================================
def main():
    with open(os.path.join(AQUI, "notas_guion.json"), encoding="utf-8") as f:
        notas = json.load(f)
    diapositivas = construir(notas)
    n = len(diapositivas)

    media, nombres_media, archivos = {}, {}, {}
    for k, d in enumerate(diapositivas, start=1):
        lista = [("rId1", RT + "slideLayout", "../slideLayouts/slideLayout1.xml")]
        for rid, ruta in d.rels:
            if ruta not in nombres_media:
                ext = os.path.splitext(ruta)[1].lower()
                nombres_media[ruta] = f"imagen{len(nombres_media) + 1}{ext}"
                with open(ruta, "rb") as fh:
                    media[nombres_media[ruta]] = fh.read()
            lista.append((rid, RT + "image", "../media/" + nombres_media[ruta]))
        lista.append((f"rId{len(lista) + 1}", RT + "notesSlide", f"../notesSlides/notesSlide{k}.xml"))
        archivos[f"ppt/slides/slide{k}.xml"] = d.xml()
        archivos[f"ppt/slides/_rels/slide{k}.xml.rels"] = rels(lista)
        archivos[f"ppt/notesSlides/notesSlide{k}.xml"] = nota_xml(d.notas)
        archivos[f"ppt/notesSlides/_rels/notesSlide{k}.xml.rels"] = rels([
            ("rId1", RT + "notesMaster", "../notesMasters/notesMaster1.xml"),
            ("rId2", RT + "slide", f"../slides/slide{k}.xml")])

    archivos["ppt/slideMasters/slideMaster1.xml"] = MAESTRO
    archivos["ppt/slideMasters/_rels/slideMaster1.xml.rels"] = rels([
        ("rId1", RT + "slideLayout", "../slideLayouts/slideLayout1.xml"),
        ("rId2", RT + "theme", "../theme/theme1.xml")])
    archivos["ppt/slideLayouts/slideLayout1.xml"] = DISENO
    archivos["ppt/slideLayouts/_rels/slideLayout1.xml.rels"] = rels([
        ("rId1", RT + "slideMaster", "../slideMasters/slideMaster1.xml")])
    archivos["ppt/notesMasters/notesMaster1.xml"] = MAESTRO_NOTAS
    archivos["ppt/notesMasters/_rels/notesMaster1.xml.rels"] = rels([("rId1", RT + "theme", "../theme/theme2.xml")])
    archivos["ppt/theme/theme1.xml"] = TEMA
    archivos["ppt/theme/theme2.xml"] = TEMA

    sld_ids = "".join(f'<p:sldId id="{255 + k}" r:id="rId{k + 3}"/>' for k in range(1, n + 1))
    archivos["ppt/presentation.xml"] = (
        XML + f'<p:presentation {NS} saveSubsetFonts="1">'
        '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        '<p:notesMasterIdLst><p:notesMasterId r:id="rId2"/></p:notesMasterIdLst>'
        f'<p:sldIdLst>{sld_ids}</p:sldIdLst>'
        f'<p:sldSz cx="{SW}" cy="{SH}"/><p:notesSz cx="{NSW}" cy="{NSH}"/>'
        '<p:defaultTextStyle>' + NIVEL + '</p:defaultTextStyle></p:presentation>')
    pres_rels = [("rId1", RT + "slideMaster", "slideMasters/slideMaster1.xml"),
                 ("rId2", RT + "notesMaster", "notesMasters/notesMaster1.xml"),
                 ("rId3", RT + "theme", "theme/theme1.xml")]
    pres_rels += [(f"rId{k + 3}", RT + "slide", f"slides/slide{k}.xml") for k in range(1, n + 1)]
    m = n + 4
    pres_rels += [(f"rId{m}", RT + "presProps", "presProps.xml"),
                  (f"rId{m + 1}", RT + "viewProps", "viewProps.xml"),
                  (f"rId{m + 2}", RT + "tableStyles", "tableStyles.xml")]
    archivos["ppt/_rels/presentation.xml.rels"] = rels(pres_rels)
    archivos["ppt/presProps.xml"] = XML + f'<p:presentationPr {NS}/>'
    archivos["ppt/viewProps.xml"] = (XML + f'<p:viewPr {NS}><p:normalViewPr><p:restoredLeft sz="15620"/>'
                                     '<p:restoredTop sz="80000"/></p:normalViewPr><p:gridSpacing cx="76200" cy="76200"/></p:viewPr>')
    archivos["ppt/tableStyles.xml"] = (XML + '<a:tblStyleLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                                       'def="{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}"/>')

    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    archivos["docProps/core.xml"] = (
        XML + '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<dc:title>Capacidad calorífica electrónica a T finita</dc:title>'
        '<dc:creator>Sebastián Sánchez, Joan Tovar, Jorge Garzón</dc:creator>'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{ahora}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{ahora}</dcterms:modified></cp:coreProperties>')
    archivos["docProps/app.xml"] = (
        XML + '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>generar_pptx.py</Application>'
        f'<Slides>{n}</Slides><Notes>{n}</Notes></Properties>')
    archivos["_rels/.rels"] = rels([
        ("rId1", RT + "officeDocument", "ppt/presentation.xml"),
        ("rId2", "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "docProps/core.xml"),
        ("rId3", RT + "extended-properties", "docProps/app.xml")])

    ct = "application/vnd.openxmlformats-officedocument.presentationml"
    over = [("/ppt/presentation.xml", ct + ".presentation.main+xml"),
            ("/ppt/slideMasters/slideMaster1.xml", ct + ".slideMaster+xml"),
            ("/ppt/slideLayouts/slideLayout1.xml", ct + ".slideLayout+xml"),
            ("/ppt/notesMasters/notesMaster1.xml", ct + ".notesMaster+xml"),
            ("/ppt/theme/theme1.xml", "application/vnd.openxmlformats-officedocument.theme+xml"),
            ("/ppt/theme/theme2.xml", "application/vnd.openxmlformats-officedocument.theme+xml"),
            ("/ppt/presProps.xml", ct + ".presProps+xml"),
            ("/ppt/viewProps.xml", ct + ".viewProps+xml"),
            ("/ppt/tableStyles.xml", ct + ".tableStyles+xml"),
            ("/docProps/core.xml", "application/vnd.openxmlformats-package.core-properties+xml"),
            ("/docProps/app.xml", "application/vnd.openxmlformats-officedocument.extended-properties+xml")]
    over += [(f"/ppt/slides/slide{k}.xml", ct + ".slide+xml") for k in range(1, n + 1)]
    over += [(f"/ppt/notesSlides/notesSlide{k}.xml", ct + ".notesSlide+xml") for k in range(1, n + 1)]
    archivos["[Content_Types].xml"] = (
        XML + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/><Default Extension="gif" ContentType="image/gif"/>'
        + "".join(f'<Override PartName="{p}" ContentType="{c}"/>' for p, c in over) + '</Types>')

    with zipfile.ZipFile(SALIDA, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", archivos.pop("[Content_Types].xml"))
        for nombre, contenido in archivos.items():
            z.writestr(nombre, contenido)
        for nombre, datos in media.items():
            z.writestr("ppt/media/" + nombre, datos)
    gifs = [r for r in nombres_media if r.endswith(".gif")]
    print(f"Generado: {SALIDA}  ({n} diapositivas, {len(media)} imágenes, {len(gifs)} animaciones GIF)")


if __name__ == "__main__":
    main()
