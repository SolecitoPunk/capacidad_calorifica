#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Capacidad calorífica electrónica a T finita (modelo de Sommerfeld)
===================================================================
Autores: Sebastián Sánchez, Joan Tovar, Jorge Garzón

Objetivo general
----------------
Simular numéricamente la contribución electrónica a la capacidad calorífica
de un metal (gas de electrones libres cuantizado) integrando la densidad de
estados g(E) con la distribución de Fermi-Dirac f(E,T).

Objetivos específicos / cálculo numérico pedido
-----------------------------------------------
1. Ecuación de ligadura  N = ∫ g(E) f(E,T;mu) dE  -> mu(T).
   Algoritmo iterativo propio: Newton-Raphson con salvaguarda de bisección
   (la derivada dN/dmu también se integra numéricamente). Se contrasta con
   el método de Brent (scipy.optimize.brentq).
2. Energía interna  U(T) = ∫ E g(E) f(E,T) dE  con cuadratura adaptativa de
   Gauss-Kronrod (QUADPACK, scipy.integrate.quad).
3. C_V(T) = dU/dT por diferencias finitas centrales (O(h^2)) y extracción del
   coeficiente lineal gamma, comparándolo con Sommerfeld  C_V = gamma*T.

Unidades adimensionales
-----------------------
    eps = E / E_F        t = T / T_F        m = mu / E_F      (T_F = E_F / k_B)

Densidad de estados 3D (ambos espines) normalizada para que a T = 0
N = ∫_0^1 g(eps) d eps = 1:

    g(eps) = (3/2) * sqrt(eps)          [unidades de N / E_F]

Entonces, en unidades de N*E_F (energía) y N*k_B (capacidad calorífica):
    n(m,t) = ∫ g f d eps  = 1            (ligadura)
    u(m,t) = ∫ eps g f d eps             (energía interna),   u(0) = 3/5
    c_v(t) = du/dt

Expansión de Sommerfeld (resultado analítico de referencia):
    mu/E_F   = 1 - (pi^2/12) t^2 + ...
    Delta u  = (pi^2/4) t^2 - (3 pi^4/80) t^4 + ...
    c_v      = (pi^2/2) t   - (3 pi^4/20) t^3 + ...   -> gamma = pi^2/2

Uso
---
    python sommerfeld_cv.py              # cálculo + gráficas en pantalla
    python sommerfeld_cv.py --sin-ventana  # solo guarda archivos (sin plt.show)
"""

import argparse
import os
import warnings

import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import expit          # función logística: estable numéricamente

# =============================================================================
# 0. PARÁMETROS DE LA SIMULACIÓN
# =============================================================================
T_MIN, T_MAX, N_T = 0.01, 0.50, 200   # rango principal de t = T/T_F
T_MAX_EXT, N_EXTRA = 1.00, 200        # rango ampliado para ver desviaciones
NSIG = 40.0                           # E_max = max(mu,0) + NSIG*t  (cola e^-40 ~ 4e-18)
EPSABS, EPSREL = 1e-13, 1e-13         # tolerancias de quad
T_LOW_FIT = 0.05                      # ajuste de gamma con los puntos t <= T_LOW_FIT

# Ecuación de ligadura (Newton-Raphson + bisección)
MU_INF, MU_SUP = -30.0, 5.0           # intervalo que siempre contiene la raíz
XTOL_MU = 1e-12                       # criterio de parada |Δmu|
FTOL_N = 1e-14                        # criterio de parada |n - 1|
MAX_ITER = 100

# Metal de ejemplo (cobre) para pasar a unidades físicas
EF_eV = 7.00                          # energía de Fermi del Cu [eV]
KB_eV = 8.617333262e-5                # constante de Boltzmann [eV/K]
R_GAS = 8.314462618                   # N_A k_B [J/(mol K)]
Z_VAL = 1                             # electrones de conducción por átomo (Cu)
GAMMA_EXP_CU = 0.695                  # gamma experimental del Cu [mJ/(mol K^2)] (Kittel)

CARPETA_FIG = "figuras"


# =============================================================================
# 1. MODELO FÍSICO: DOS y DISTRIBUCIÓN DE FERMI-DIRAC
# =============================================================================
def densidad_estados(eps):
    """g(eps) = (3/2) sqrt(eps): electrones libres 3D (con espín).
    Normalizada para que ∫_0^1 g d eps = 1  (N = 1)."""
    return 1.5 * np.sqrt(eps)


def fermi_dirac(eps, t, mu):
    """f = 1/(exp((eps-mu)/t)+1).  Se usa expit(-x) = 1/(1+e^x), que no
    desborda para argumentos grandes (a T pequeña (eps-mu)/t es enorme)."""
    return expit(-(eps - mu) / t)


def menos_df_deps(eps, t, mu):
    """-∂f/∂eps = f(1-f)/t: pico de ancho ~t centrado en mu."""
    x = (eps - mu) / t
    return expit(x) * expit(-x) / t


# =============================================================================
# 2. INTEGRALES (cuadratura adaptativa de Gauss-Kronrod)
# =============================================================================
def e_max(mu, t, nsig=NSIG):
    """Límite superior de integración: la cola decae como exp(-(E-mu)/t)."""
    return max(mu, 0.0) + nsig * t


def _integrar(integrando, mu, t, nsig=NSIG, epsrel=EPSREL):
    """Integra de 0 a E_max con quad (QAGS/QAGP). 'points=[mu]' obliga a
    partir el intervalo donde f cambia bruscamente (escalón de ancho ~t)."""
    emax = e_max(mu, t, nsig)
    puntos = [mu] if 0.0 < mu < emax else None
    val, _ = quad(integrando, 0.0, emax, points=puntos, limit=500,
                  epsabs=EPSABS, epsrel=epsrel)
    return val


def numero_particulas(mu, t, nsig=NSIG):
    """n(mu,t) = ∫ g f d eps   (debe valer 1)."""
    return _integrar(lambda e: densidad_estados(e) * fermi_dirac(e, t, mu),
                     mu, t, nsig)


def dn_dmu(mu, t, nsig=NSIG):
    """∂n/∂mu = ∫ g (-∂f/∂eps) d eps > 0  (derivada para Newton-Raphson)."""
    return _integrar(lambda e: densidad_estados(e) * menos_df_deps(e, t, mu),
                     mu, t, nsig)


def energia_interna(mu, t, nsig=NSIG, epsrel=EPSREL):
    """u(mu,t) = ∫ eps g f d eps   [unidades N*E_F]."""
    return _integrar(lambda e: e * densidad_estados(e) * fermi_dirac(e, t, mu),
                     mu, t, nsig, epsrel)


# =============================================================================
# 3. ECUACIÓN DE LIGADURA: mu(T)
# =============================================================================
def potencial_quimico(t, mu_inicial=1.0):
    """Resuelve F(mu) = n(mu,t) - 1 = 0 con Newton-Raphson salvaguardado.

    - Paso de Newton:  mu_{k+1} = mu_k - F(mu_k) / F'(mu_k),  F' = dn/dmu.
    - n(mu) es monótona creciente, así que con el signo de F se mantiene un
      intervalo [a, b] que siempre encierra la raíz. Si el paso de Newton se
      sale de ese intervalo se hace un paso de bisección (convergencia
      garantizada; cerca de la raíz la convergencia es cuadrática).
    Devuelve (mu, número de iteraciones)."""
    a, b = MU_INF, MU_SUP
    mu = min(max(mu_inicial, a + 1e-3), b - 1e-3)
    for k in range(1, MAX_ITER + 1):
        F = numero_particulas(mu, t) - 1.0
        if abs(F) < FTOL_N:
            return mu, k
        if F > 0:
            b = mu          # sobran electrones -> la raíz está a la izquierda
        else:
            a = mu
        dF = dn_dmu(mu, t)
        mu_nuevo = mu - F / dF if dF > 0 else 0.5 * (a + b)
        if not (a < mu_nuevo < b):
            mu_nuevo = 0.5 * (a + b)                 # salvaguarda: bisección
        paso = abs(mu_nuevo - mu)
        mu = mu_nuevo
        if paso < XTOL_MU:
            return mu, k
    warnings.warn(f"Newton no convergió en t={t}; se usa Brent.", stacklevel=2)
    return potencial_quimico_brent(t), MAX_ITER


def potencial_quimico_brent(t):
    """Referencia independiente: método de Brent (scipy.optimize.brentq)."""
    F = lambda mu: numero_particulas(mu, t) - 1.0
    return brentq(F, MU_INF, MU_SUP, xtol=1e-14, rtol=1e-13, maxiter=200)


# =============================================================================
# 4. ENERGÍA, CAPACIDAD CALORÍFICA Y AJUSTE DE GAMMA
# =============================================================================
def calcular_serie(t_arr):
    """Para cada t: mu (con continuación: la semilla es el mu del t anterior),
    iteraciones de Newton, comprobación de N y u(t)."""
    mu, iters = np.empty(len(t_arr)), np.empty(len(t_arr), dtype=int)
    semilla = 1.0                                   # mu(T=0) = E_F
    for i, t in enumerate(t_arr):
        mu[i], iters[i] = potencial_quimico(t, semilla)
        semilla = mu[i]
    n = np.array([numero_particulas(m, t) for m, t in zip(mu, t_arr)])
    u = np.array([energia_interna(m, t) for m, t in zip(mu, t_arr)])
    return mu, iters, n, u


def derivada_numerica(u, t):
    """C_V/(N k_B) = du/dt.  np.gradient usa diferencias centrales
    (u_{i+1}-u_{i-1})/(2h) en puntos interiores (error O(h^2)) y fórmulas
    de 2º orden en los extremos (edge_order=2)."""
    return np.gradient(u, t, edge_order=2)


def ajustar_gamma(t, cv, t_max=T_LOW_FIT):
    """Extrae gamma por mínimos cuadrados con los puntos interiores t <= t_max.

    - Modelo 1 (lineal puro):    c_v = gamma t
    - Modelo 2 (con corrección): c_v = gamma t + delta t^3
      El término t^3 absorbe la primera corrección de la expansión de
      Sommerfeld; sin él, gamma sale sesgado por debajo (~0.5 %).
    Se excluyen los extremos porque allí la derivada es de un solo lado."""
    sel = (t <= t_max)
    sel[0] = sel[-1] = False
    ts, cs = t[sel], cv[sel]
    gamma_1 = np.sum(cs * ts) / np.sum(ts**2)
    A = np.column_stack([ts, ts**3])
    (gamma_2, delta), *_ = np.linalg.lstsq(A, cs, rcond=None)
    return gamma_1, gamma_2, delta


# --- Predicciones teóricas de Sommerfeld (unidades adimensionales) -----------
U0 = 3.0 / 5.0                                              # u(0)
GAMMA_TEO = np.pi**2 / 2.0                                  # c_v = GAMMA_TEO * t
DELTA_TEO = -3.0 * np.pi**4 / 20.0                          # coeficiente de t^3
du_somm = lambda t: (np.pi**2 / 4.0) * t**2                 # Delta u (1er orden)
cv_somm = lambda t: GAMMA_TEO * t                           # C_V/(N k_B) lineal
cv_somm2 = lambda t: GAMMA_TEO * t + DELTA_TEO * t**3       # con corrección t^3
mu_somm = lambda t: 1.0 - (np.pi**2 / 12.0) * t**2          # mu/E_F


# =============================================================================
# 5. GRÁFICAS
# =============================================================================
def graficar(t, mu, du, t_ext, mu_e, cv_e, gamma_num):
    plt.rcParams.update({"font.size": 10})
    e = np.linspace(0, 2, 600)

    def panel_dos(ax):
        ax.plot(e, densidad_estados(e), 'b', label=r"$g(\epsilon)$")
        m = e <= 1
        ax.fill_between(e[m], densidad_estados(e[m]), alpha=0.25,
                        label="estados ocupados (T=0)")
        ax.axvline(1, color='gray', ls='--', label=r'$E_F$')
        ax.set(title=r"Densidad de estados $g(\epsilon)=\frac{3}{2}\sqrt{\epsilon}$",
               xlabel=r"$\epsilon=E/E_F$", ylabel=r"$g$  [$N/E_F$]")
        ax.legend()

    def panel_fd(ax):
        for tv in (0.01, 0.05, 0.1, 0.2, 0.5):
            mv, _ = potencial_quimico(tv)
            ax.plot(e, fermi_dirac(e, tv, mv), label=f"t={tv}")
        ax.set(title=r"Fermi-Dirac con $\mu(T)$ calculado",
               xlabel=r"$\epsilon=E/E_F$", ylabel=r"$f(\epsilon)$")
        ax.legend()

    def panel_mu(ax):
        ax.plot(t_ext, mu_e, 'b', label="numérico (Newton)")
        ax.plot(t_ext, mu_somm(t_ext), 'r--', label=r"$1-\frac{\pi^2}{12}t^2$")
        ax.set(title=r"Potencial químico $\mu(T)$", xlabel=r"$t=T/T_F$",
               ylabel=r"$\mu/E_F$", ylim=(-0.2, 1.05))
        ax.legend()

    def panel_du(ax):
        ax.plot(t, du, 'b', label="numérico")
        ax.plot(t, du_somm(t), 'r--', label=r"$\frac{\pi^2}{4}t^2$")
        ax.set(title=r"Energía térmica $\Delta U = U(T)-U(0)$",
               xlabel=r"$t=T/T_F$", ylabel=r"$\Delta U/(N E_F)$")
        ax.legend()

    def panel_cv(ax):
        ax.plot(t_ext, cv_e, 'b', lw=2, label=r"numérico $dU/dT$")
        ax.plot(t_ext, cv_somm(t_ext), 'r--',
                label=r"Sommerfeld $\frac{\pi^2}{2}t$")
        ax.plot(t_ext, cv_somm2(t_ext), 'm:',
                label=r"$\frac{\pi^2}{2}t-\frac{3\pi^4}{20}t^3$")
        ax.axhline(1.5, color='gray', ls='-.', label="límite clásico 3/2")
        ax.set(title=rf"Capacidad calorífica ($\gamma_{{num}}$={gamma_num:.5f})",
               xlabel=r"$t=T/T_F$", ylabel=r"$C_V/(Nk_B)$", ylim=(0, 2.2))
        ax.legend()

    def panel_razon(ax):
        ax.plot(t_ext, cv_e / cv_somm(t_ext), 'g')
        ax.axhline(1, color='k', ls='--', lw=0.8)
        ax.set(title=r"$C_V^{num}/C_V^{Sommerfeld}$", xlabel=r"$t=T/T_F$",
               ylabel="razón")

    paneles = [("1_densidad_estados", panel_dos), ("2_fermi_dirac", panel_fd),
               ("3_potencial_quimico", panel_mu), ("4_energia_termica", panel_du),
               ("5_capacidad_calorifica", panel_cv), ("6_razon_cv", panel_razon)]

    # Figura resumen 2x3
    fig, axs = plt.subplots(2, 3, figsize=(15, 8.5))
    for ax, (_, fn) in zip(axs.flat, paneles):
        fn(ax)
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig("sommerfeld_resultados.png", dpi=150)

    # Figuras individuales (para las diapositivas)
    os.makedirs(CARPETA_FIG, exist_ok=True)
    for nombre, fn in paneles:
        f1, a1 = plt.subplots(figsize=(6.4, 4.4))
        fn(a1)
        a1.grid(alpha=0.3)
        f1.tight_layout()
        f1.savefig(os.path.join(CARPETA_FIG, nombre + ".png"), dpi=200)
        plt.close(f1)
    return fig


# =============================================================================
# 6. PROGRAMA PRINCIPAL
# =============================================================================
def main(mostrar=True):
    # ---- 6.1 Rejilla principal de temperaturas -----------------------------
    t = np.linspace(T_MIN, T_MAX, N_T)
    mu, iters, n, u = calcular_serie(t)
    du = u - U0                       # energía térmica ΔU = U(T) - U(0)
    cv = derivada_numerica(u, t)
    gamma_1, gamma_num, delta_num = ajustar_gamma(t, cv)

    # ---- 6.2 Validaciones ---------------------------------------------------
    print("=" * 70)
    print(" 1) ECUACIÓN DE LIGADURA  (Newton-Raphson salvaguardado)")
    print("=" * 70)
    print(f" Conservación de N:      max|n-1| = {np.max(np.abs(n - 1)):.2e}")
    print(f" Iteraciones de Newton:  media = {iters.mean():.2f}, máx = {iters.max()}")
    idx = np.linspace(0, N_T - 1, 6).astype(int)
    dif_brent = max(abs(mu[i] - potencial_quimico_brent(t[i])) for i in idx)
    print(f" Contraste con Brent:    max|mu_Newton - mu_Brent| = {dif_brent:.2e}")
    print(f" mu(t={T_MIN}) = {mu[0]:.8f}   Sommerfeld: {mu_somm(T_MIN):.8f}")

    print("\n" + "=" * 70)
    print(" 2) ENERGÍA INTERNA  (cuadratura adaptativa Gauss-Kronrod)")
    print("=" * 70)
    t_peq = 1e-3
    u_peq = energia_interna(potencial_quimico(t_peq)[0], t_peq)
    print(f" u(t={t_peq}) = {u_peq:.12f}   Sommerfeld 3/5 + (pi^2/4) t^2 = "
          f"{U0 + du_somm(t_peq):.12f}")
    m_low = t <= T_LOW_FIT
    a = np.sum(du[m_low] * t[m_low]**2) / np.sum(t[m_low]**4)
    print(f" ΔU ≈ a t^2:  a_num = {a:.5f}   a_Sommerfeld = pi^2/4 = {np.pi**2/4:.5f}")

    print("\n" + "=" * 70)
    print(f" 3) CAPACIDAD CALORÍFICA y coeficiente gamma  (ajuste t <= {T_LOW_FIT})")
    print("=" * 70)
    err = lambda g: abs(g / GAMMA_TEO - 1) * 100
    print(f" gamma teórico (pi^2/2)              = {GAMMA_TEO:.6f}")
    print(f" ajuste c_v = gamma t                -> {gamma_1:.6f}  (error {err(gamma_1):.3f} %)")
    print(f" ajuste c_v = gamma t + delta t^3    -> {gamma_num:.6f}  (error {err(gamma_num):.4f} %)")
    print(f"   delta_num = {delta_num:.2f}   delta_Sommerfeld = -3pi^4/20 = {DELTA_TEO:.2f}")

    # ---- 6.3 Sensibilidad a E_max, tolerancia y paso de T -------------------
    print("\n Sensibilidad (t = 0.1):")
    t0 = 0.1
    mu0, _ = potencial_quimico(t0)
    for ns in (10, 20, 30, 40, 60):
        print(f"   E_max = mu + {ns:>2d} t       -> u = {energia_interna(mu0, t0, ns):.14f}")
    for tol in (1e-6, 1e-9, 1e-13):
        print(f"   epsrel = {tol:.0e}       -> u = {energia_interna(mu0, t0, epsrel=tol):.14f}")
    for N_test in (50, 100, 200, 400):
        tt = np.linspace(T_MIN, T_MAX, N_test)
        _, _, _, uu = calcular_serie(tt)
        _, g_, _ = ajustar_gamma(tt, derivada_numerica(uu, tt))
        print(f"   paso h = {tt[1]-tt[0]:.5f} ({N_test:>3d} ptos) -> gamma = {g_:.6f}")

    # ---- 6.4 Rango ampliado (desviaciones respecto a Sommerfeld) ------------
    t_ext = np.linspace(T_MIN, T_MAX_EXT, N_EXTRA)
    mu_e, _, _, u_e = calcular_serie(t_ext)
    cv_e = derivada_numerica(u_e, t_ext)
    for tv in (0.1, 0.3, 0.5, 1.0):
        i = np.argmin(np.abs(t_ext - tv))
        print(f"   t = {t_ext[i]:.3f}:  C_V/C_V^Somm = {cv_e[i]/cv_somm(t_ext[i]):.4f}")

    # ---- 6.5 Tabla CSV ------------------------------------------------------
    tabla = np.column_stack([t, mu, iters, n, np.abs(n - 1), u, du, du_somm(t),
                             cv, cv_somm(t), cv / cv_somm(t)])
    np.savetxt("resultados_sommerfeld.csv", tabla, delimiter=",",
               header="t=T/TF,mu/EF,iter_Newton,N_calc,|N-1|,u,DeltaU,DeltaU_Somm,"
                      "Cv/NkB,Cv_Somm/NkB,ratio", comments="")
    print("\nTabla guardada: resultados_sommerfeld.csv")
    print("\n   t       mu/EF     |N-1|      ΔU        Cv_num    Cv_Somm   ratio")
    for i in range(0, N_T, N_T // 10):
        print(f" {t[i]:.3f}  {mu[i]:.6f}  {abs(n[i]-1):.1e}  {du[i]:.6f}  "
              f"{cv[i]:.5f}  {cv_somm(t[i]):.5f}  {cv[i]/cv_somm(t[i]):.4f}")

    # ---- 6.6 Unidades físicas (cobre) ---------------------------------------
    TF = EF_eV / KB_eV
    a_fis = Z_VAL * R_GAS / TF * 1e3                 # paso a mJ/(mol K^2)
    print(f"\nCobre: E_F = {EF_eV} eV  ->  T_F = {TF:.0f} K")
    print(f" A 300 K: t = T/T_F = {300/TF:.4f}  (régimen lineal: C_V/C_V^Somm ≈ "
          f"{1 + DELTA_TEO/GAMMA_TEO*(300/TF)**2:.6f})")
    print(f" gamma Sommerfeld  = {GAMMA_TEO*a_fis:.3f} mJ/(mol K^2)")
    print(f" gamma numérico    = {gamma_num*a_fis:.3f} mJ/(mol K^2)")
    print(f" gamma experimental= {GAMMA_EXP_CU:.3f} mJ/(mol K^2)  "
          f"-> m*/m ≈ {GAMMA_EXP_CU/(gamma_num*a_fis):.2f}")
    print(f" C_V electrónica a 300 K = {gamma_num*a_fis*300/1e3:.4f} J/(mol K)  "
          f"(vs 3R = {3*R_GAS:.2f} J/(mol K) de la red)")

    # ---- 6.7 Gráficas -------------------------------------------------------
    graficar(t, mu, du, t_ext, mu_e, cv_e, gamma_num)
    print("\nFiguras guardadas: sommerfeld_resultados.png y carpeta figuras/")
    if mostrar:
        plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--sin-ventana", action="store_true",
                        help="no abrir ventanas de matplotlib (solo guardar archivos)")
    main(mostrar=not parser.parse_args().sin_ventana)
