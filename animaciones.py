#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Animaciones para la presentación (modelo de Sommerfeld)
=======================================================
Autores: Sebastián Sánchez, Joan Tovar, Jorge Garzón

Genera GIF (y MP4 si hay ffmpeg) en la carpeta animaciones/ usando la misma
física y los mismos métodos numéricos de sommerfeld_cv.py:

  1_fermi_dirac.gif   Diapositiva 4  (Sebastián): el escalón de Fermi-Dirac se
                      suaviza al subir T; mu(T) se mueve y aparecen electrones
                      excitados por encima de E_F y huecos por debajo.
  2_newton.gif        Diapositiva 7  (Joan): iteraciones de Newton-Raphson
                      sobre F(mu) = N(mu) - 1 y convergencia cuadrática.
  3_cuadratura.gif    Diapositiva 9  (Joan): subintervalos que elige la
                      cuadratura adaptativa de quad al bajar T.
  4_derivada_cv.gif   Diapositivas 11-12 (Jorge): la pendiente de ΔU(T)
                      se convierte, punto a punto, en la curva C_V(T).

Uso
---
    python animaciones.py                     # las cuatro animaciones
    python animaciones.py --solo newton cv    # solo algunas
    python animaciones.py --mp4               # además MP4 (requiere ffmpeg)

Los GIF se insertan directamente en Google Slides o PowerPoint
(Insertar > Imagen) y se reproducen en bucle automáticamente.
"""

import argparse
import os

import matplotlib
matplotlib.use("Agg")                      # no abrir ventanas: solo archivos
import matplotlib.pyplot as plt            # noqa: E402
import numpy as np                         # noqa: E402
from matplotlib import animation           # noqa: E402
from scipy.integrate import quad, simpson  # noqa: E402

from sommerfeld_cv import (                # noqa: E402
    EPSABS, EPSREL, MU_INF, MU_SUP, U0, GAMMA_TEO,
    densidad_estados, fermi_dirac, numero_particulas, dn_dmu,
    potencial_quimico, e_max, calcular_serie, derivada_numerica,
    cv_somm, mu_somm,
)

CARPETA = "animaciones"
DPI = 100
plt.rcParams.update({"font.size": 11})


def guardar(anim, nombre, fps, mp4=False):
    """Guarda la animación como GIF (Pillow, viene con matplotlib) y,
    opcionalmente, como MP4 si ffmpeg está instalado."""
    os.makedirs(CARPETA, exist_ok=True)
    ruta = os.path.join(CARPETA, nombre + ".gif")
    anim.save(ruta, writer=animation.PillowWriter(fps=fps), dpi=DPI)
    print(f"  guardado: {ruta}")
    if mp4:
        if animation.writers.is_available("ffmpeg"):
            ruta = os.path.join(CARPETA, nombre + ".mp4")
            anim.save(ruta, writer=animation.FFMpegWriter(fps=fps, bitrate=2400),
                      dpi=150)
            print(f"  guardado: {ruta}")
        else:
            print("  (ffmpeg no está instalado: se omite el MP4)")


def con_pausa(n_frames, pausa_final):
    """Lista de índices de cuadro que repite el último para hacer una pausa
    antes de que el GIF vuelva a empezar."""
    return list(range(n_frames)) + [n_frames - 1] * pausa_final


# =============================================================================
# 1. FERMI-DIRAC Y OCUPACIÓN AL SUBIR LA TEMPERATURA
# =============================================================================
def anim_fermi_dirac(mp4=False):
    print("1) Fermi-Dirac y ocupación")
    ts = np.geomspace(0.005, 0.5, 80)
    mus, semilla = [], 1.0
    for t in ts:                                   # continuación en T
        semilla, _ = potencial_quimico(t, semilla)
        mus.append(semilla)

    e = np.linspace(0, 2, 800)
    g = densidad_estados(e)
    g0 = np.where(e <= 1.0, g, 0.0)                # ocupación a T = 0

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.4))
    a1.plot(e, (e <= 1).astype(float), color="gray", ls="--", lw=1, label="T = 0")
    linea_f, = a1.plot([], [], "b", lw=2.2, label="f(ε, T)")
    linea_mu = a1.axvline(1.0, color="r", ls=":", lw=1.5, label="μ(T)")
    a1.set(xlim=(0, 2), ylim=(-0.03, 1.08), xlabel=r"$\epsilon = E/E_F$",
           ylabel=r"$f(\epsilon)$", title="Distribución de Fermi-Dirac")
    a1.legend(loc="upper right")
    a1.grid(alpha=0.3)

    a2.plot(e, g, "k", lw=1, label=r"$g(\epsilon)$")
    a2.plot(e, g0, color="gray", ls="--", lw=1, label="ocupación a T = 0")
    linea_gf, = a2.plot([], [], "b", lw=2)
    a2.axvline(1.0, color="gray", lw=0.8)
    a2.set(xlim=(0, 2), ylim=(0, 2.2), xlabel=r"$\epsilon = E/E_F$",
           ylabel=r"$g(\epsilon)\,f(\epsilon)$", title="Estados ocupados")
    a2.grid(alpha=0.3)
    titulo = fig.suptitle("")
    dinamicos = []

    def dibujar(i):
        for obj in dinamicos:
            obj.remove()
        dinamicos.clear()
        t, mu = ts[i], mus[i]
        f = fermi_dirac(e, t, mu)
        gf = g * f
        linea_f.set_data(e, f)
        linea_mu.set_xdata([mu, mu])
        linea_gf.set_data(e, gf)
        dinamicos.append(a1.axvspan(mu - 2 * t, mu + 2 * t, color="orange",
                                    alpha=0.15))
        dinamicos.append(a2.fill_between(e, gf, color="tab:blue", alpha=0.25,
                                         label="ocupados"))
        dinamicos.append(a2.fill_between(e, g0, gf, where=(e > 1), color="red",
                                         alpha=0.45, label="electrones excitados"))
        dinamicos.append(a2.fill_between(e, gf, g0, where=(e <= 1), color="gold",
                                         alpha=0.6, label="huecos"))
        dinamicos.append(a2.legend(loc="upper left", fontsize=9))
        titulo.set_text(rf"$t = T/T_F = {t:.3f}$      $\mu/E_F = {mu:.4f}$      "
                        r"(franja naranja: $\mu \pm 2k_BT$)")
        return []

    anim = animation.FuncAnimation(fig, dibujar, frames=con_pausa(len(ts), 20),
                                   interval=80)
    fig.tight_layout()
    fig.subplots_adjust(top=0.86)                  # espacio para el suptitle
    guardar(anim, "1_fermi_dirac", fps=12, mp4=mp4)
    plt.close(fig)


# =============================================================================
# 2. NEWTON-RAPHSON PARA LA ECUACIÓN DE LIGADURA
# =============================================================================
def historial_newton(t, mu0, max_iter=12):
    """Misma lógica que potencial_quimico() pero guardando cada iteración:
    lista de (mu_k, F_k, F'_k, mu_{k+1}, fue_biseccion)."""
    a, b, mu, hist = MU_INF, MU_SUP, mu0, []
    for _ in range(max_iter):
        F = numero_particulas(mu, t) - 1.0
        if abs(F) < 1e-14:
            hist.append((mu, F, np.nan, mu, False))
            break
        if F > 0:
            b = mu
        else:
            a = mu
        dF = dn_dmu(mu, t)
        nuevo = mu - F / dF
        bis = not (a < nuevo < b)
        if bis:
            nuevo = 0.5 * (a + b)
        hist.append((mu, F, dF, nuevo, bis))
        if abs(nuevo - mu) < 1e-13:
            break
        mu = nuevo
    return hist


def anim_newton(mp4=False, t=0.3, mu0=0.35):
    print("2) Newton-Raphson")
    hist = historial_newton(t, mu0)
    mu_raiz = hist[-1][3]
    m = np.linspace(0.0, 1.5, 300)
    F_curva = np.array([numero_particulas(x, t) - 1.0 for x in m])

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.4),
                                 gridspec_kw={"width_ratios": [1.6, 1]})
    a1.plot(m, F_curva, "k", lw=2, label=r"$F(\mu) = N(\mu) - 1$")
    a1.axhline(0, color="gray", lw=0.8)
    a1.set(xlim=(0, 1.5), ylim=(-0.9, 0.9), xlabel=r"$\mu/E_F$",
           ylabel=r"$F(\mu)$", title=rf"Ecuación de ligadura a $t = {t}$")
    a1.grid(alpha=0.3)
    a1.legend(loc="upper left")

    a2.set(xlim=(-0.3, len(hist) - 0.7), ylim=(1e-17, 3), yscale="log",
           xlabel="iteración k", ylabel=r"$|F(\mu_k)| = |N - 1|$",
           title="Convergencia cuadrática")
    a2.axhline(2.2e-16, color="gray", ls=":", lw=1)
    a2.text(0, 5e-16, "precisión de máquina", fontsize=8, color="gray")
    a2.grid(alpha=0.3, which="both")
    linea_conv, = a2.plot([], [], "o-", color="tab:red")

    # Secuencia de cuadros: por iteración, 3 fases de PASO cuadros cada una
    PASO = 7
    pasos = [(k, fase) for k in range(len(hist)) for fase in range(3)
             for _ in range(PASO)]
    pasos += [(len(hist) - 1, 3)] * 25
    dinamicos = []

    def dibujar(j):
        for obj in dinamicos:
            obj.remove()
        dinamicos.clear()
        k, fase = pasos[j]
        # Iteraciones ya terminadas (en gris)
        for kk in range(k):
            mu_k, F_k, _, mu_n, _ = hist[kk]
            dinamicos += a1.plot([mu_k, mu_n], [F_k, 0], color="tab:blue",
                                 lw=1, alpha=0.35)
            dinamicos += a1.plot([mu_k], [F_k], "o", color="tab:blue", alpha=0.35)
        mu_k, F_k, dF, mu_n, bis = hist[k]
        dinamicos += a1.plot([mu_k, mu_k], [0, F_k], ":", color="tab:blue")
        dinamicos += a1.plot([mu_k], [F_k], "o", color="tab:blue", ms=8)
        texto = rf"$k={k}$:  $\mu_k = {mu_k:.6f}$,  $F = {F_k:.1e}$"
        if fase >= 1 and np.isfinite(dF):
            x = np.array([0.0, 1.5])
            dinamicos += a1.plot(x, F_k + dF * (x - mu_k), color="tab:orange",
                                 lw=1.8, label="tangente")
            texto += "\n" + (r"tangente: pendiente $\partial N/\partial\mu = "
                             rf"{dF:.3f}$")
        if fase >= 2 and np.isfinite(dF):
            dinamicos += a1.plot([mu_n], [0], "s", color="tab:green", ms=8)
            paso = "bisección" if bis else r"$\mu_{k+1} = \mu_k - F/F'$"
            texto += "\n" + rf"{paso} $= {mu_n:.6f}$"
        if fase == 3:
            dinamicos.append(a1.axvline(mu_raiz, color="tab:green", ls="--"))
            texto = (rf"raíz: $\mu/E_F = {mu_raiz:.10f}$" + "\n"
                     rf"Sommerfeld: $1-\pi^2t^2/12 = {mu_somm(t):.4f}$")
        dinamicos.append(a1.text(0.98, 0.04, texto, transform=a1.transAxes,
                                 ha="right", va="bottom", fontsize=9.5,
                                 bbox=dict(fc="white", ec="gray", alpha=0.9)))
        ks = np.arange(k + 1)
        errs = [max(abs(h[1]), 1e-16) for h in hist[:k + 1]]
        linea_conv.set_data(ks, errs)
        return []

    anim = animation.FuncAnimation(fig, dibujar, frames=len(pasos), interval=100)
    fig.tight_layout()
    guardar(anim, "2_newton", fps=10, mp4=mp4)
    plt.close(fig)


# =============================================================================
# 3. CUADRATURA ADAPTATIVA: SUBINTERVALOS QUE ELIGE quad
# =============================================================================
def particion_quad(mu, t):
    """Ejecuta la misma integral de energia_interna() con full_output=1 y
    devuelve (valor, número de evaluaciones, bordes de los subintervalos)."""
    integrando = lambda x: x * densidad_estados(x) * fermi_dirac(x, t, mu)
    emax = e_max(mu, t)
    puntos = [mu] if 0.0 < mu < emax else None
    res = quad(integrando, 0.0, emax, points=puntos, limit=500,
               epsabs=EPSABS, epsrel=EPSREL, full_output=1)
    val, info = res[0], res[2]
    n = info.get("last", 0)
    if "alist" in info and "blist" in info and n > 0:
        bordes = np.unique(np.concatenate([info["alist"][:n], info["blist"][:n]]))
    else:                                          # versión de SciPy sin esos datos
        bordes = np.array([0.0] + (puntos or []) + [emax])
    return val, info["neval"], bordes, emax


def anim_cuadratura(mp4=False):
    print("3) Cuadratura adaptativa")
    ts = np.geomspace(0.3, 0.005, 50)
    datos, semilla = [], 1.0
    for t in ts:
        semilla, _ = potencial_quimico(t, semilla)
        val, neval, bordes, emax = particion_quad(semilla, t)
        # Simpson con paso fijo y el MISMO número de evaluaciones
        x = np.linspace(0.0, emax, neval if neval % 2 else neval + 1)
        y = x * densidad_estados(x) * fermi_dirac(x, t, semilla)
        err_simp = abs(simpson(y, x=x) - val)
        datos.append((t, semilla, val, neval, bordes, emax, err_simp))

    e = np.linspace(0, 2, 1200)
    fig, ax = plt.subplots(figsize=(11, 4.6))
    linea, = ax.plot([], [], "b", lw=2)
    ax.set(xlim=(0, 2), ylim=(0, 1.75), xlabel=r"$\epsilon = E/E_F$",
           ylabel=r"$\epsilon\, g(\epsilon)\, f(\epsilon)$",
           title="Integrando de U(T) y subintervalos de la cuadratura adaptativa")
    ax.grid(alpha=0.3)
    dinamicos = []

    def dibujar(i):
        for obj in dinamicos:
            obj.remove()
        dinamicos.clear()
        t, mu, val, neval, bordes, emax, err_simp = datos[i]
        y = e * densidad_estados(e) * fermi_dirac(e, t, mu)
        linea.set_data(e, y)
        dinamicos.append(ax.fill_between(e, y, color="tab:blue", alpha=0.15))
        visibles = bordes[bordes <= 2.0]
        dinamicos.append(ax.vlines(visibles, 0, 1.75, color="tab:red",
                                   lw=0.6, alpha=0.6))
        dinamicos.append(ax.axvline(mu, color="k", ls=":", lw=1.2))
        texto = (rf"$t = {t:.4f}$,  $\mu/E_F = {mu:.5f}$" + "\n"
                 f"subintervalos: {len(bordes) - 1}   evaluaciones: {neval}\n"
                 rf"$U/(N E_F) = {val:.12f}$" + "\n"
                 f"Simpson (paso fijo, {neval} ptos): error {err_simp:.1e}")
        dinamicos.append(ax.text(0.015, 0.97, texto, transform=ax.transAxes,
                                 va="top", fontsize=9.5,
                                 bbox=dict(fc="white", ec="gray", alpha=0.9)))
        dinamicos.append(ax.text(0.985, 0.97,
                                 rf"corte en $E_{{max}} = \mu + 40\,k_BT = {emax:.2f}$",
                                 transform=ax.transAxes, ha="right", va="top",
                                 fontsize=9, color="gray"))
        return []

    anim = animation.FuncAnimation(fig, dibujar, frames=con_pausa(len(ts), 15),
                                   interval=120)
    fig.tight_layout()
    guardar(anim, "3_cuadratura", fps=8, mp4=mp4)
    plt.close(fig)


# =============================================================================
# 4. DE LA PENDIENTE DE ΔU(T) A LA CURVA C_V(T)
# =============================================================================
def anim_derivada_cv(mp4=False):
    print("4) Derivada numérica y C_V(T)")
    t = np.linspace(0.01, 1.0, 200)
    _, _, _, u = calcular_serie(t)
    du = u - U0
    cv = derivada_numerica(u, t)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.4))
    a1.plot(t, du, color="lightgray", lw=4)
    a1.plot(t, (np.pi**2 / 4) * t**2, "r--", lw=1, label=r"$\frac{\pi^2}{4}t^2$")
    traza_u, = a1.plot([], [], "b", lw=2, label=r"$\Delta U$ numérico")
    tangente, = a1.plot([], [], color="tab:orange", lw=2, label="pendiente = $C_V$")
    punto_u, = a1.plot([], [], "o", color="tab:orange")
    a1.set(xlim=(0, 1), ylim=(0, du.max() * 1.1), xlabel=r"$t = T/T_F$",
           ylabel=r"$\Delta U/(N E_F)$", title=r"Energía térmica $\Delta U(T)$")
    a1.legend(loc="upper left")
    a1.grid(alpha=0.3)

    a2.plot(t, cv_somm(t), "r--", lw=1.2, label=r"Sommerfeld $\frac{\pi^2}{2}t$")
    a2.axhline(1.5, color="gray", ls="-.", lw=1, label="límite clásico 3/2")
    traza_c, = a2.plot([], [], "b", lw=2, label=r"$C_V = dU/dT$ numérico")
    punto_c, = a2.plot([], [], "o", color="tab:orange")
    a2.set(xlim=(0, 1), ylim=(0, 2.2), xlabel=r"$t = T/T_F$",
           ylabel=r"$C_V/(N k_B)$", title="Capacidad calorífica")
    a2.legend(loc="upper left", fontsize=9)
    a2.grid(alpha=0.3)
    texto = a2.text(0.97, 0.05, "", transform=a2.transAxes, ha="right",
                    fontsize=10, bbox=dict(fc="white", ec="gray", alpha=0.9))

    indices = list(range(1, len(t) - 1, 2))
    L = 0.12                                            # semilongitud de la tangente

    def dibujar(j):
        i = indices[min(j, len(indices) - 1)]
        traza_u.set_data(t[:i + 1], du[:i + 1])
        x = np.array([t[i] - L, t[i] + L])
        tangente.set_data(x, du[i] + cv[i] * (x - t[i]))
        punto_u.set_data([t[i]], [du[i]])
        traza_c.set_data(t[:i + 1], cv[:i + 1])
        punto_c.set_data([t[i]], [cv[i]])
        texto.set_text(rf"$t = {t[i]:.3f}$   $C_V/Nk_B = {cv[i]:.4f}$" + "\n"
                       rf"$C_V / C_V^{{Somm}} = {cv[i] / (GAMMA_TEO * t[i]):.4f}$")
        return []

    anim = animation.FuncAnimation(fig, dibujar, frames=len(indices) + 25,
                                   interval=80)
    fig.tight_layout()
    guardar(anim, "4_derivada_cv", fps=12, mp4=mp4)
    plt.close(fig)


ANIMACIONES = {"fermi": anim_fermi_dirac, "newton": anim_newton,
               "cuadratura": anim_cuadratura, "cv": anim_derivada_cv}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Animaciones de la presentación")
    parser.add_argument("--solo", nargs="+", choices=ANIMACIONES.keys(),
                        help="generar solo estas animaciones")
    parser.add_argument("--mp4", action="store_true",
                        help="guardar también MP4 (requiere ffmpeg)")
    args = parser.parse_args()
    for nombre in (args.solo or ANIMACIONES):
        ANIMACIONES[nombre](mp4=args.mp4)
    print(f"\nListo. Archivos en la carpeta {CARPETA}/")
