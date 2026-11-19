#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera presentacion_sommerfeld.pptx (16:9) usando solo la biblioteca estándar.

- Gráficas: presentacion/img/*.png
- Si existen los GIF de ../animaciones/ (python animaciones.py), se usan en
  lugar de la imagen estática de las diapositivas 4, 7, 9 y 11.
- Notas del orador: el guion de presentacion/notas_guion.json.

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
ANIM = os.path.join(AQUI, "..", "animaciones")
SALIDA = os.path.join(AQUI, "presentacion_sommerfeld.pptx")

EMU = 914400                      # EMU por pulgada
SW, SH = 12192000, 6858000        # 13.333 x 7.5 in (16:9)
AZUL, AZUL2, GRIS = "1F3B6E", "2E5AA8", "5A5A5A"
COLOR = {"Sebastián": "0B6E4F", "Joan": "A33B00", "Jorge": "5B2A86", "Todos": "1F3B6E"}
FUENTE = "Calibri"

NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
RT = REL_NS + "/"
XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


def inch(x):
    return int(round(x * EMU))


# =============================================================================
# Texto enriquecido: **negrita**, _{subíndice}, ^{superíndice}
# =============================================================================
def runs(texto, size, color="222222", bold=False, italic=False):
    if "**" in texto:                              # primero la negrita, luego sub/superíndices
        trozos = re.split(r"(\*\*.*?\*\*)", texto)
        return "".join(runs(tz[2:-2], size, color, True, italic) if tz.startswith("**")
                       else runs(tz, size, color, bold, italic) for tz in trozos if tz)
    partes = re.split(r"(_\{.*?\}|\^\{.*?\})", texto)
    out = []
    for p in partes:
        if not p:
            continue
        b, base, t = bold, 0, p
        if p.startswith("_{"):
            base, t = -25000, p[2:-1]
        elif p.startswith("^{"):
            base, t = 30000, p[2:-1]
        attrs = f'lang="es-CO" sz="{int(size * 100)}" b="{int(b)}" i="{int(italic)}" dirty="0"'
        if base:
            attrs += f' baseline="{base}"'
        out.append(f'<a:r><a:rPr {attrs}><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
                   f'<a:latin typeface="{FUENTE}"/><a:cs typeface="{FUENTE}"/></a:rPr>'
                   f'<a:t>{escape(t)}</a:t></a:r>')
    return "".join(out)


def parrafo(texto, size, color="222222", bold=False, italic=False, align="l",
            bullet=None, nivel=0, espacio_antes=6):
    ppr = f'<a:pPr algn="{align}"'
    if bullet:
        mar = 342900 + nivel * 342900
        ppr += f' marL="{mar}" indent="-285750"'
    ppr += f'><a:spcBef><a:spcPts val="{espacio_antes * 100}"/></a:spcBef>'
    if bullet:
        bc = COLOR.get(bullet, AZUL2) if bullet in COLOR else AZUL2
        ch = "•" if nivel == 0 else "–"
        ppr += (f'<a:buClr><a:srgbClr val="{bc}"/></a:buClr><a:buFont typeface="Arial"/>'
                f'<a:buChar char="{ch}"/>')
    else:
        ppr += '<a:buNone/>'
    ppr += '</a:pPr>'
    return (f'<a:p>{ppr}{runs(texto, size, color, bold, italic)}'
            f'<a:endParaRPr lang="es-CO" sz="{int(size * 100)}" dirty="0"/></a:p>')


class Diapositiva:
    def __init__(self, notas=""):
        self.formas, self.rels, self.next_id, self.notas = [], [], 2, notas

    def _id(self):
        self.next_id += 1
        return self.next_id

    def caja(self, x, y, w, h, parrafos, fill=None, linea=None, geom="rect",
             anchor="t", margen=0.08, nombre="Texto"):
        i = self._id()
        relleno = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else '<a:noFill/>'
        ln = (f'<a:ln w="15875"><a:solidFill><a:srgbClr val="{linea}"/></a:solidFill></a:ln>'
              if linea else '<a:ln><a:noFill/></a:ln>')
        m = inch(margen)
        self.formas.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="{nombre} {i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{inch(x)}" y="{inch(y)}"/><a:ext cx="{inch(w)}" cy="{inch(h)}"/></a:xfrm>'
            f'<a:prstGeom prst="{geom}"><a:avLst/></a:prstGeom>{relleno}{ln}</p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="{m}" tIns="{m}" rIns="{m}" bIns="{m}" anchor="{anchor}">'
            f'<a:normAutofit/></a:bodyPr><a:lstStyle/>{"".join(parrafos) or "<a:p/>"}</p:txBody></p:sp>')

    def imagen(self, ruta, x, y, w, h):
        """Inserta la imagen ajustada (sin deformar) y centrada en el rectángulo."""
        iw, ih = tamano_imagen(ruta)
        esc = min(w / iw, h / ih)
        cw, ch = iw * esc, ih * esc
        x, y = x + (w - cw) / 2, y + (h - ch) / 2
        rid = f"rId{len(self.rels) + 2}"
        self.rels.append((rid, "image", ruta))
        i = self._id()
        self.formas.append(
            f'<p:pic><p:nvPicPr><p:cNvPr id="{i}" name="Imagen {i}" descr="{escape(os.path.basename(ruta))}"/>'
            f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
            f'<p:spPr><a:xfrm><a:off x="{inch(x)}" y="{inch(y)}"/><a:ext cx="{inch(cw)}" cy="{inch(ch)}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')

    def tabla(self, x, y, anchos, filas, size=14, alto_fila=0.42):
        i = self._id()
        grid = "".join(f'<a:gridCol w="{inch(a)}"/>' for a in anchos)
        trs = []
        for k, fila in enumerate(filas):
            tcs = []
            for celda in fila:
                if k == 0:
                    txt, fill, col, b = celda, AZUL, "FFFFFF", True
                else:
                    txt, fill, col, b = celda, ("EEF2F9" if k % 2 else "FFFFFF"), "222222", False
                tcs.append(
                    f'<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>{parrafo(txt, size, col, b, align="ctr", espacio_antes=0)}</a:txBody>'
                    f'<a:tcPr marL="68580" marR="68580" marT="45720" marB="45720" anchor="ctr">'
                    + "".join(f'<a:ln{lado} w="9525"><a:solidFill><a:srgbClr val="B9C3D6"/></a:solidFill></a:ln{lado}>'
                              for lado in ("L", "R", "T", "B"))
                    + f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill></a:tcPr></a:tc>')
            trs.append(f'<a:tr h="{inch(alto_fila)}">{"".join(tcs)}</a:tr>')
        self.formas.append(
            f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{i}" name="Tabla {i}"/>'
            f'<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>'
            f'<p:xfrm><a:off x="{inch(x)}" y="{inch(y)}"/><a:ext cx="{inch(sum(anchos))}" cy="{inch(alto_fila * len(filas))}"/></p:xfrm>'
            f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">'
            f'<a:tbl><a:tblPr firstRow="1" bandRow="1"/><a:tblGrid>{grid}</a:tblGrid>{"".join(trs)}</a:tbl>'
            f'</a:graphicData></a:graphic></p:graphicFrame>')

    def xml(self, fondo=None):
        bg = (f'<p:bg><p:bgPr><a:solidFill><a:srgbClr val="{fondo}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>'
              if fondo else "")
        return (XML + f'<p:sld {NS}><p:cSld>{bg}<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
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


# =============================================================================
# Plantilla común de las diapositivas de contenido
# =============================================================================
W_IN, H_IN = SW / EMU, SH / EMU


def base(num, titulo, orador, tiempo, notas):
    d = Diapositiva(notas)
    d.caja(0, 0, W_IN, 1.0, [], fill=AZUL, nombre="Barra")
    d.caja(0.2, 0, W_IN - 3.75, 1.0, [parrafo(titulo, 28, "FFFFFF", True, espacio_antes=0)],
           anchor="ctr", margen=0.25, nombre="Título")
    d.caja(W_IN - 3.35, 0.22, 3.05, 0.56, [parrafo(f"{orador} · {tiempo}", 14, "FFFFFF", True, align="ctr", espacio_antes=0)],
           fill=COLOR[orador], geom="roundRect", anchor="ctr", margen=0.04, nombre="Orador")
    d.caja(0.45, 7.05, 8, 0.35, [parrafo("Capacidad calorífica electrónica a T finita · Modelo de Sommerfeld",
                                         11, "8A8A8A", espacio_antes=0)], margen=0, nombre="Pie")
    d.caja(W_IN - 1.45, 7.05, 1.0, 0.35, [parrafo(f"{num} / 16", 11, "8A8A8A", align="r", espacio_antes=0)],
           margen=0, nombre="Número")
    return d


def vinetas(items, size=20):
    ps = []
    for it in items:
        nivel = 1 if it.startswith("- ") else 0
        texto = it[2:] if nivel else it
        ps.append(parrafo(texto, size - 2 * nivel, "222222", bullet=True, nivel=nivel,
                          espacio_antes=10 if nivel == 0 else 4))
    return ps


def img(nombre):
    return os.path.join(IMG, nombre + ".png")


def anim_o_img(gif, png):
    ruta = os.path.join(ANIM, gif + ".gif")
    return (ruta, True) if os.path.exists(ruta) else (img(png), False)


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
    d.caja(0.8, 1.35, W_IN - 1.6, 1.6, [parrafo("Capacidad Calorífica Electrónica a T Finita", 40, "FFFFFF", True, align="ctr")],
           anchor="ctr", nombre="Título")
    d.caja(0.8, 2.95, W_IN - 1.6, 0.7, [parrafo("Modelo de Sommerfeld · Simulación numérica en Python", 24, "C9D6EE", align="ctr")],
           anchor="ctr")
    d.caja(W_IN / 2 - 2.5, 3.85, 5.0, 0.04, [], fill="C9D6EE")
    nombres = [parrafo(n, 24, "FFFFFF", True, align="ctr", espacio_antes=8)
               for n in ("Sebastián Sánchez", "Joan Tovar", "Jorge Garzón")]
    d.caja(0.8, 4.1, W_IN - 1.6, 1.9, nombres, anchor="t")
    d.caja(0.8, 6.35, W_IN - 1.6, 0.5, [parrafo("Física computacional · 2026", 16, "C9D6EE", align="ctr")])
    S.append((d, AZUL))

    # 2. Motivación ---------------------------------------------------------
    d = base(2, "¿Por qué los electrones casi no aportan calor?", "Sebastián", "0:45–2:15", nota(1))
    d.caja(0.45, 1.3, 6.0, 5.6, vinetas([
        "Gas clásico: cada electrón aporta (3/2) k_{B}",
        "- En el cobre serían 12.5 J/(mol K), la mitad de la red",
        "El experimento mide apenas ~1 % de ese valor",
        "Sommerfeld (1928): los electrones son fermiones",
        "- Por el principio de Pauli solo se excitan los que están a ~k_{B}T de E_{F}",
        "Resultado: **C_{V} = γ T**, lineal en T",
    ]))
    d.imagen(img("barras"), 6.7, 1.35, 6.2, 5.5)
    S.append((d, None))

    # 3. Objetivos ----------------------------------------------------------
    d = base(3, "Objetivos", "Sebastián", "2:15–3:00", nota(2))
    d.caja(0.45, 1.3, 12.4, 1.3, [
        parrafo("**Objetivo general**", 22, AZUL),
        parrafo("Simular numéricamente la contribución electrónica a la capacidad calorífica de un metal "
                "integrando la densidad de estados y la distribución de Fermi-Dirac.", 19)],
        fill="EEF2F9", linea="C9D3E6")
    d.caja(0.45, 2.8, 6.1, 3.9, [
        parrafo("**Objetivos específicos**", 22, AZUL),
        parrafo("**i.** Calcular la energía interna térmica integrando g(E) · E · f(E,T).", 18, espacio_antes=12),
        parrafo("**ii.** Obtener C_{V}(T) por derivación numérica y contrastarla con la aproximación lineal de Sommerfeld.",
                18, espacio_antes=12)], fill="EEF2F9", linea="C9D3E6")
    d.caja(6.75, 2.8, 6.1, 3.9, [
        parrafo("**Cálculo numérico**", 22, AZUL),
        parrafo("**Ligadura:** Newton-Raphson para μ(T) conservando N", 18, espacio_antes=12),
        parrafo("**Cuadratura adaptativa:** Gauss-Kronrod para U(T)", 18, espacio_antes=12),
        parrafo("**Diferenciación:** C_{V} = dU/dT y coeficiente γ", 18, espacio_antes=12)],
        fill="EEF2F9", linea="C9D3E6")
    S.append((d, None))

    # 4. Modelo físico ------------------------------------------------------
    ruta, es_gif = anim_o_img("1_fermi_dirac", "fd")
    d = base(4, "Modelo: densidad de estados y Fermi-Dirac", "Sebastián", "3:00–4:45",
             nota(3, "" if es_gif else aviso_gif.format(g="animaciones/1_fermi_dirac")))
    d.caja(0.45, 1.15, 12.4, 1.1, [
        parrafo("g(E) = (3/2) E^{1/2} (electrones libres 3D)     f(E,T) = 1 / [e^{(E−μ)/k_BT} + 1]", 20, align="ctr"),
        parrafo("N = ∫ g(E) f(E,T) dE          U = ∫ E g(E) f(E,T) dE", 20, AZUL, True, align="ctr")],
        anchor="ctr")
    if es_gif:
        d.imagen(img("dos"), 0.3, 2.35, 4.4, 4.6)
        d.imagen(ruta, 4.8, 2.35, 8.25, 4.6)
    else:
        d.imagen(img("dos"), 0.4, 2.35, 6.2, 4.6)
        d.imagen(ruta, 6.75, 2.35, 6.2, 4.6)
    S.append((d, None))

    # 5. Unidades y predicción ---------------------------------------------
    d = base(5, "Unidades y predicción de Sommerfeld", "Sebastián", "4:45–6:30", nota(4))
    d.caja(0.45, 1.3, 5.6, 5.5, [
        parrafo("**Variables**", 22, AZUL),
        parrafo("ε = E / E_{F}", 22, espacio_antes=14),
        parrafo("t = T / T_{F},   T_{F} = E_{F} / k_{B}", 22, espacio_antes=10),
        parrafo("g(ε) = (3/2) ε^{1/2}  →  ∫_{0}^{1} g dε = 1", 22, espacio_antes=10),
        parrafo("U(T = 0) = (3/5) N E_{F}", 22, espacio_antes=10),
        parrafo("Metal típico: T_{F} ~ 10^{4}–10^{5} K → a 300 K, t ~ 0.004", 17, GRIS, espacio_antes=22)],
        fill="EEF2F9", linea="C9D3E6")
    d.caja(6.35, 1.3, 6.5, 5.5, [
        parrafo("**Expansión de Sommerfeld (t pequeño)**", 22, AZUL),
        parrafo("μ / E_{F} = 1 − (π²/12) t²", 24, espacio_antes=20),
        parrafo("ΔU / (N E_{F}) = (π²/4) t²", 24, espacio_antes=16),
        parrafo("C_{V} / (N k_{B}) = (π²/2) t", 24, espacio_antes=16),
        parrafo("γ = π²/2 ≈ 4.9348", 30, COLOR["Sebastián"], True, align="ctr", espacio_antes=26),
        parrafo("en unidades de N k_{B} / T_{F}", 16, GRIS, align="ctr", espacio_antes=2)],
        fill="FFFFFF", linea=COLOR["Sebastián"])
    S.append((d, None))

    # 6. Esquema del algoritmo ---------------------------------------------
    d = base(6, "Esquema del algoritmo", "Joan", "6:30–7:30", nota(5))
    pasos = [("Rejilla de T", "200 valores de t entre 0.01 y 0.5"),
             ("Ligadura", "Newton-Raphson → μ(t) con N = 1"),
             ("Cuadratura adaptativa", "Gauss-Kronrod → U(t)"),
             ("Derivada numérica", "diferencias centrales → C_{V}(t)"),
             ("Ajuste", "mínimos cuadrados → γ")]
    colores = [AZUL2, COLOR["Joan"], COLOR["Joan"], COLOR["Jorge"], COLOR["Jorge"]]
    bw, gap, x0 = 2.15, 0.42, 0.45
    for k, ((t1, t2), c) in enumerate(zip(pasos, colores)):
        x = x0 + k * (bw + gap)
        d.caja(x, 2.2, bw, 2.3, [parrafo(f"**{t1}**", 19, "FFFFFF", align="ctr", espacio_antes=0),
                                 parrafo(t2, 15, "FFFFFF", align="ctr", espacio_antes=10)],
               fill=c, geom="roundRect", anchor="ctr", margen=0.1)
        if k < len(pasos) - 1:
            d.caja(x + bw + 0.06, 3.15, gap - 0.12, 0.4, [], fill="9AA7BF", geom="rightArrow")
    d.caja(0.45, 4.9, 12.4, 0.5, [parrafo("Para cada temperatura: primero μ, luego U.   Con U en toda la rejilla: C_{V} y γ.",
                                          19, GRIS, align="ctr")])
    d.caja(2.4, 5.7, 8.5, 0.7, [parrafo("Python · NumPy · SciPy · Matplotlib · GitHub", 20, AZUL, True, align="ctr",
                                        espacio_antes=0)], fill="EEF2F9", geom="roundRect", anchor="ctr")
    S.append((d, None))

    # 7. Newton -------------------------------------------------------------
    ruta, es_gif = anim_o_img("2_newton", "newton")
    d = base(7, "Ecuación de ligadura: Newton-Raphson", "Joan", "7:30–9:15",
             nota(6, "" if es_gif else aviso_gif.format(g="animaciones/2_newton")))
    d.caja(0.45, 1.3, 5.0, 5.6, [
        parrafo("F(μ) = ∫ g f dε − 1 = 0", 21, AZUL, True),
        parrafo("μ_{k+1} = μ_{k} − F(μ_{k}) / F′(μ_{k})", 21, AZUL, True, espacio_antes=8),
        parrafo("F′ = ∫ g (−∂f/∂ε) dε > 0", 21, AZUL, True, espacio_antes=8),
        *vinetas(["N crece con μ → raíz única",
                  "Salvaguarda: si el paso sale de [a, b], bisección",
                  "Continuación: semilla = μ de la T anterior",
                  "3–4 iteraciones por temperatura",
                  "Brent (SciPy): diferencia ≤ 1.4×10^{−14}"], 18)])
    d.imagen(ruta, 5.6, 1.25, 7.4, 5.65)
    S.append((d, None))

    # 8. Resultado mu(T) ----------------------------------------------------
    d = base(8, "Resultado: potencial químico μ(T)", "Joan", "9:15–10:30", nota(7))
    d.imagen(img("mu"), 0.35, 1.25, 7.4, 5.0)
    d.imagen(img("newton_conv"), 7.9, 1.25, 5.1, 3.4)
    d.caja(7.9, 4.75, 5.1, 2.2, vinetas(["t = 0.01: μ = 0.99991774 (Sommerfeld 0.99991775)",
                                         "t = 1: μ = −0.021 (régimen clásico)",
                                         "max |N − 1| = 9.8×10^{−15}"], 16))
    S.append((d, None))

    # 9. Cuadratura ---------------------------------------------------------
    ruta, es_gif = anim_o_img("3_cuadratura", "integrando")
    d = base(9, "Integración adaptativa de U(T)", "Joan", "10:30–12:00",
             nota(8, "" if es_gif else aviso_gif.format(g="animaciones/3_cuadratura")))
    d.caja(0.45, 1.3, 5.0, 3.3, vinetas([
        "scipy.integrate.quad: Gauss-Kronrod adaptativo (QUADPACK)",
        "Divide solo donde el error estimado es grande",
        "Punto de ruptura en ε = μ",
        "Corte: E_{max} = μ + 40 k_{B}T (cola ~ e^{−40})",
        "Tolerancia relativa 10^{−13}"], 18))
    d.tabla(0.55, 4.75, [2.6, 2.2], [["Corte E_{max}", "U (t = 0.1)"],
                                    ["μ + 10 t", "0.624262488730"],
                                    ["μ + 20 t", "0.624283104469"],
                                    ["μ + 40 t", "0.624283106151"],
                                    ["μ + 60 t", "0.624283106151"]], size=13, alto_fila=0.4)
    d.imagen(ruta, 5.6, 1.25, 7.4, 5.65)
    S.append((d, None))

    # 10. Delta U -----------------------------------------------------------
    d = base(10, "Energía térmica ΔU(T)", "Joan", "12:00–13:00", nota(9))
    d.imagen(img("du"), 0.35, 1.25, 8.0, 5.65)
    d.caja(8.55, 1.6, 4.4, 4.8, [
        parrafo("ΔU = U(T) − (3/5) N E_{F}", 20, AZUL, True),
        *vinetas(["Crece como t², igual que Sommerfeld",
                  "Ajuste ΔU = a t² (t ≤ 0.05):",
                  "- a = 2.461",
                  "- π²/4 = 2.467",
                  "La diferencia de 0.3 % es la corrección de orden t^{4}"], 19)])
    S.append((d, None))

    # 11. Derivada ----------------------------------------------------------
    ruta, es_gif = anim_o_img("4_derivada_cv", "tangente")
    d = base(11, "Diferenciación numérica", "Jorge", "13:00–14:15",
             nota(10, "" if es_gif else aviso_gif.format(g="animaciones/4_derivada_cv")))
    d.caja(0.45, 1.3, 5.0, 5.6, [
        parrafo("C_{V}(T_{i}) ≈ [U(T_{i+1}) − U(T_{i−1})] / 2h", 21, AZUL, True),
        *vinetas(["Diferencias centrales: error O(h²)",
                  "Extremos: fórmula de un lado, también de 2.º orden",
                  "Derivar amplifica el ruido:",
                  "- error 10^{−6} en U → ~0.5 % en C_{V} a la T más baja",
                  "Por eso la integral necesita precisión de 10^{−13}"], 18)])
    d.imagen(ruta, 5.6, 1.25, 7.4, 5.65)
    S.append((d, None))

    # 12. C_V ---------------------------------------------------------------
    d = base(12, "C_{V}(T) frente a Sommerfeld", "Jorge", "14:15–15:45", nota(11))
    d.imagen(img("cv"), 0.3, 1.2, 6.5, 4.75)
    d.imagen(img("razon"), 6.65, 1.2, 6.5, 4.75)
    d.caja(0.45, 6.0, 12.4, 0.95, [parrafo(
        "Lineal a baja T  ·  t = 0.1: 96.7 %   t = 0.3: 71 %   t = 0.5: 51 % del valor lineal  ·  "
        "a t ~ 1 tiende al límite clásico 3/2", 17, GRIS, align="ctr")], anchor="ctr")
    S.append((d, None))

    # 13. Gamma -------------------------------------------------------------
    d = base(13, "Extracción del coeficiente lineal γ", "Jorge", "15:45–17:00", nota(12))
    d.tabla(0.55, 1.45, [3.9, 1.9, 1.5], [
        ["Ajuste (t ≤ 0.05)", "γ", "Error"],
        ["C_{V} = γ t", "4.9117", "−0.47 %"],
        ["C_{V} = γ t + δ t³", "4.934927", "+0.0025 %"],
        ["Teoría: π²/2", "4.934802", "—"]], size=17, alto_fila=0.62)
    d.caja(0.55, 4.25, 7.3, 2.6, vinetas([
        "El ajuste lineal puro ignora la corrección −(3π^{4}/20) t³",
        "δ ajustado = −14.98 (teoría −14.61)",
        "Se excluyen los extremos de la rejilla (derivada de un lado)"], 18))
    d.tabla(8.4, 1.45, [1.7, 2.75], [
        ["Puntos", "γ"],
        ["50", "4.933624"],
        ["100", "4.934682"],
        ["200", "4.934927"],
        ["400", "4.934981"]], size=17, alto_fila=0.62)
    d.caja(8.4, 4.75, 4.45, 1.2, [parrafo("Convergencia con el paso h: γ estable en la 4.ª cifra decimal",
                                          16, GRIS, align="ctr")], anchor="ctr")
    S.append((d, None))

    # 14. Cobre -------------------------------------------------------------
    d = base(14, "Aplicación a un metal real: el cobre", "Jorge", "17:00–18:30", nota(13))
    tarjetas = [("E_{F} = 7.0 eV", "T_{F} = 81 232 K", "a 300 K: t = 0.0037"),
                ("γ calculado", "0.505 mJ/(mol K²)", "electrones libres"),
                ("γ experimental", "0.695 mJ/(mol K²)", "→ m*/m ≈ 1.38"),
                ("C_{V} electrónica (300 K)", "0.15 J/(mol K)", "red: 3R = 24.9 J/(mol K)")]
    for k, (a, b, c) in enumerate(tarjetas):
        x = 0.45 + k * 3.15
        d.caja(x, 1.4, 2.95, 2.4, [parrafo(a, 17, GRIS, align="ctr", espacio_antes=0),
                                   parrafo(f"**{b}**", 22, COLOR["Jorge"], align="ctr", espacio_antes=10),
                                   parrafo(c, 15, GRIS, align="ctr", espacio_antes=10)],
               fill="F4F0F8", linea="C8B6DA", geom="roundRect", anchor="ctr")
    d.caja(0.45, 4.1, 12.4, 2.8, vinetas([
        "La diferencia de 38 % se resume en una masa efectiva m*/m ≈ 1.38",
        "- El modelo no incluye el potencial de la red ni la interacción electrón-fonón",
        "A 300 K los electrones aportan ~1 % de lo que predice la física clásica",
        "A pocos kelvin la red decae como T³ y domina el término electrónico: C/T = γ + βT²"], 19))
    S.append((d, None))

    # 15. Conclusiones ------------------------------------------------------
    d = base(15, "Conclusiones", "Jorge", "18:30–19:30", nota(14))
    concl = [("Ligadura", "Newton-Raphson salvaguardado: N se conserva a 10^{−14} en 3–4 iteraciones."),
             ("Integración", "Gauss-Kronrod adaptativo integra el escalón de Fermi-Dirac con precisión de 10^{−13}."),
             ("C_{V} y γ", "C_{V} es lineal a baja T; γ coincide con π²/2 dentro de 0.0025 %."),
             ("Más allá de Sommerfeld", "El cálculo muestra dónde falla la aproximación lineal y recupera el límite clásico 3/2.")]
    for k, (a, b) in enumerate(concl):
        y = 1.35 + k * 1.38
        d.caja(0.6, y, 0.75, 0.75, [parrafo(str(k + 1), 26, "FFFFFF", True, align="ctr", espacio_antes=0)],
               fill=COLOR["Jorge"], geom="ellipse", anchor="ctr", margen=0)
        d.caja(1.6, y - 0.1, 11.2, 1.0, [parrafo(f"**{a}:** {b}", 21)], anchor="ctr")
    S.append((d, None))

    # 16. Cierre ------------------------------------------------------------
    d = Diapositiva(nota(15))
    d.caja(0.8, 1.9, W_IN - 1.6, 1.4, [parrafo("¡Gracias!", 54, "FFFFFF", True, align="ctr")], anchor="ctr")
    d.caja(0.8, 3.3, W_IN - 1.6, 0.9, [parrafo("¿Preguntas?", 32, "C9D6EE", align="ctr")], anchor="ctr")
    d.caja(0.8, 4.6, W_IN - 1.6, 0.7, [parrafo("Sebastián Sánchez · Joan Tovar · Jorge Garzón", 22, "FFFFFF", align="ctr")])
    d.caja(0.8, 5.5, W_IN - 1.6, 0.6, [parrafo("github.com/SolecitoPunk/capacidad_calorifica", 18, "C9D6EE", align="ctr")])
    S.append((d, AZUL))
    return S


# =============================================================================
# Partes fijas del paquete (tema, maestros, diseños)
# =============================================================================
TEMA = XML + f'''<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Sommerfeld">
<a:themeElements>
<a:clrScheme name="Sommerfeld"><a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1><a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
<a:dk2><a:srgbClr val="{AZUL}"/></a:dk2><a:lt2><a:srgbClr val="EEF2F9"/></a:lt2>
<a:accent1><a:srgbClr val="{AZUL2}"/></a:accent1><a:accent2><a:srgbClr val="D62728"/></a:accent2><a:accent3><a:srgbClr val="2CA02C"/></a:accent3>
<a:accent4><a:srgbClr val="{COLOR["Jorge"]}"/></a:accent4><a:accent5><a:srgbClr val="{COLOR["Joan"]}"/></a:accent5><a:accent6><a:srgbClr val="{COLOR["Sebastián"]}"/></a:accent6>
<a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme>
<a:fontScheme name="Sommerfeld"><a:majorFont><a:latin typeface="{FUENTE}"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>
<a:minorFont><a:latin typeface="{FUENTE}"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>
<a:fmtScheme name="Sommerfeld">
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

MAESTRO = (XML + f'<p:sldMaster {NS}><p:cSld><p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef></p:bg>'
           + SPTREE_VACIO + '</p:spTree></p:cSld>' + CLRMAP
           + '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
           f'<p:txStyles><p:titleStyle>{NIVEL}</p:titleStyle><p:bodyStyle>{NIVEL}</p:bodyStyle>'
           f'<p:otherStyle>{NIVEL}</p:otherStyle></p:txStyles></p:sldMaster>')

DISENO = (XML + f'<p:sldLayout {NS} type="blank" preserve="1"><p:cSld name="En blanco">' + SPTREE_VACIO
          + '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>')

NSW, NSH = 6858000, 9144000        # página de notas (vertical)


def ph_notas(i, nombre, tipo, x, y, w, h, idx=None, cuerpo=""):
    idx_attr = f' idx="{idx}"' if idx is not None else ""
    extra = '<a:picLocks noGrp="1" noRot="1" noChangeAspect="1"/>' if tipo == "sldImg" else '<a:spLocks noGrp="1"/>'
    xfrm = (f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>') if w else ""
    tx = (f'<p:txBody><a:bodyPr/><a:lstStyle/>{cuerpo or "<a:p/>"}</p:txBody>' if tipo == "body" else "")
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="{nombre}"/><p:cNvSpPr>{extra}</p:cNvSpPr>'
            f'<p:nvPr><p:ph type="{tipo}"{idx_attr}/></p:nvPr></p:nvSpPr><p:spPr>{xfrm}</p:spPr>{tx}</p:sp>')


MAESTRO_NOTAS = (XML + f'<p:notesMaster {NS}><p:cSld><p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef></p:bg>'
                 + SPTREE_VACIO
                 + ph_notas(2, "Imagen de diapositiva", "sldImg", 381000, 685800, 6096000, 3429000, idx=2)
                 + ph_notas(3, "Notas", "body", 685800, 4343400, 5486400, 4114800, idx=3)
                 + '</p:spTree></p:cSld>' + CLRMAP
                 + f'<p:notesStyle>{NIVEL.replace("1800", "1200")}</p:notesStyle></p:notesMaster>')


def nota_xml(texto):
    ps = "".join(f'<a:p><a:r><a:rPr lang="es-CO" sz="1200" dirty="0"/><a:t>{escape(linea)}</a:t></a:r></a:p>'
                 for linea in texto.split("\n"))
    return (XML + f'<p:notes {NS}><p:cSld>' + SPTREE_VACIO
            + ph_notas(2, "Imagen de diapositiva", "sldImg", 0, 0, 0, 0, idx=2)
            + ph_notas(3, "Notas", "body", 0, 0, 0, 0, idx=3, cuerpo=ps)
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

    media, nombres_media = {}, {}
    archivos = {}
    for k, (d, fondo) in enumerate(diapositivas, start=1):
        lista = [("rId1", RT + "slideLayout", "../slideLayouts/slideLayout1.xml")]
        for rid, _, ruta in d.rels:
            if ruta not in nombres_media:
                ext = os.path.splitext(ruta)[1].lower()
                nombres_media[ruta] = f"imagen{len(nombres_media) + 1}{ext}"
                with open(ruta, "rb") as fh:
                    media[nombres_media[ruta]] = fh.read()
            lista.append((rid, RT + "image", "../media/" + nombres_media[ruta]))
        lista.append((f"rId{len(lista) + 1}", RT + "notesSlide", f"../notesSlides/notesSlide{k}.xml"))
        archivos[f"ppt/slides/slide{k}.xml"] = d.xml(fondo)
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
    archivos["ppt/notesMasters/_rels/notesMaster1.xml.rels"] = rels([
        ("rId1", RT + "theme", "../theme/theme2.xml")])
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
        f'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>generar_pptx.py</Application>'
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
