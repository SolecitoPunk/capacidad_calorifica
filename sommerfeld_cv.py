#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Capacidad calorífica electrónica a T finita (modelo de Sommerfeld)
===================================================================

Objetivos de la tarea
---------------------
1. Resolver la ecuación de ligadura  N = ∫ g(E) f(E,T) dE  para obtener mu(T)
   (método de Brent).
2. Calcular la energía interna  U(T) = ∫ E g(E) f(E,T) dE  con cuadratura
   adaptativa (scipy.integrate.quad).
3. Obtener C_V(T) = dU/dT por diferencias finitas y compararla con la
   aproximación lineal de Sommerfeld  C_V = gamma*T.

Unidades adimensionales (recomendadas en la consigna)
-----------------------------------------------------
    eps = E / E_F        t = T / T_F        m = mu / E_F      (T_F = E_F / k_B)

Densidad de estados 3D (ambos espines) normalizada de modo que
N = ∫_0^1 g(eps) d eps = 1   (a T = 0):

    g(eps) = (3/2) * sqrt(eps)          [unidades de N / E_F]

Entonces, en unidades de N*E_F:
    n(m,t) = ∫ g f d eps  = 1            (ligadura)
    u(m,t) = ∫ eps g f d eps             (energía interna)
    u(0)   = 3/5
y en unidades de N*k_B:
    c_v(t) = du/dt   (Sommerfeld:  c_v = (pi^2/2) t ,  Delta u = (pi^2/4) t^2)

Al final se convierte a unidades físicas para un metal de ejemplo.
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import expit          # función logística: estable numéricamente

# =============================================================================
# 0. PARÁMETROS DE LA SIMULACIÓN
# =============================================================================
T_MIN, T_MAX, N_T = 0.01, 0.50, 200   # rango de t = T/T_F (propuesto en la consigna)
T_MAX_EXT = 1.00                      # rango ampliado para ver desviaciones
N_EXTRA = 200
NSIG = 40.0                           # E_max = max(mu,0) + NSIG*t  (cola e^-40 ~ 4e-18)
EPSABS, EPSREL = 1e-13, 1e-13         # tolerancias de quad
T_LOW_FIT = 0.05                      # ajuste de gamma para t < T_LOW_FIT

# Metal de ejemplo para pasar a unidades físicas (valor típico del cobre)
EF_eV = 7.0                           # energía de Fermi [eV]
KB_eV = 8.617333262e-5                # constante de Boltzmann [eV/K]
R_GAS = 8.314462618                   # J/(mol K)  (para 1 mol de electrones)


# =============================================================================
# 1. MODELO FÍSICO: DOS y DISTRIBUCIÓN DE FERMI-DIRAC
# =============================================================================
def densidad_estados(eps):
    """g(eps) = (3/2) sqrt(eps): modelo de electrones libres 3D (con espín).
    Normalizada para que ∫_0^1 g d eps = 1  (N = 1)."""
    return 1.5 * np.sqrt(eps)


def fermi_dirac(eps, t, mu):
    """f = 1/(exp((eps-mu)/t)+1).  Se usa expit(-x) = 1/(1+e^x), que no
    desborda para argumentos grandes (a T pequeña (eps-mu)/t es enorme)."""
    return expit(-(eps - mu) / t)


# =============================================================================
# 2. INTEGRALES (cuadratura adaptativa)
# =============================================================================
def e_max(mu, t, nsig=NSIG):
    """Límite superior de integración: la cola decae como exp(-(E-mu)/t)."""
    return max(mu, 0.0) + nsig * t


def _integrar(integrando, mu, t, nsig=NSIG):
    """Integra de 0 a E_max con quad. Se indica 'points=[mu]' para que el
    algoritmo refine alrededor de la zona donde f cambia bruscamente."""
    emax = e_max(mu, t, nsig)
    puntos = [mu] if 0.0 < mu < emax else None
    val, _ = quad(integrando, 0.0, emax, points=puntos, limit=500,
                  epsabs=EPSABS, epsrel=EPSREL)
    return val


def numero_particulas(mu, t, nsig=NSIG):
    """n(mu,t) = ∫ g f d eps   (debe valer 1)."""
    return _integrar(lambda e: densidad_estados(e) * fermi_dirac(e, t, mu),
                     mu, t, nsig)


def energia_interna(mu, t, nsig=NSIG):
    """u(mu,t) = ∫ eps g f d eps   [unidades N*E_F]."""
    return _integrar(lambda e: e * densidad_estados(e) * fermi_dirac(e, t, mu),
                     mu, t, nsig)


# =============================================================================
# 3. ECUACIÓN DE LIGADURA: mu(T) por el método de Brent
# =============================================================================
def potencial_quimico(t):
    """Resuelve F(mu) = n(mu,t) - 1 = 0 con brentq.
    n es monótona creciente en mu, así que el cero es único.
    Intervalo [-30, 5]: n(-30) ≈ 0 < 1 y n(5) > 1 para todo t del estudio."""
    F = lambda mu: numero_particulas(mu, t) - 1.0
    return brentq(F, -30.0, 5.0, xtol=1e-14, rtol=1e-13, maxiter=200)


# =============================================================================
# 4. CAPACIDAD CALORÍFICA
# =============================================================================
def calcular_serie(t_arr):
    """Para cada t: mu, comprobación de N, y u(t)."""
    mu = np.array([potencial_quimico(t) for t in t_arr])
    n = np.array([numero_particulas(m, t) for m, t in zip(mu, t_arr)])
    u = np.array([energia_interna(m, t) for m, t in zip(mu, t_arr)])
    return mu, n, u


def derivada_numerica(u, t):
    """C_V/(N k_B) = du/dt.  np.gradient usa diferencias centrales en puntos
    interiores (O(h^2)) y de 2º orden en los extremos (edge_order=2)."""
    return np.gradient(u, t, edge_order=2)


# --- Predicciones teóricas de Sommerfeld (unidades adimensionales) -----------
u0 = 3.0 / 5.0                                        # u(0)
du_somm = lambda t: (np.pi**2 / 4.0) * t**2           # Delta u
cv_somm = lambda t: (np.pi**2 / 2.0) * t              # C_V/(N k_B)
mu_somm = lambda t: 1.0 - (np.pi**2 / 12.0) * t**2    # mu/E_F (1er orden)


# =============================================================================
# 5. PROGRAMA PRINCIPAL
# =============================================================================
def main():
    # ---- 5.1 Rejilla de temperaturas ---------------------------------------
    t = np.linspace(T_MIN, T_MAX, N_T)
    mu, n, u = calcular_serie(t)
    du = u - u0                       # energía térmica ΔU = U(T) - U(0)
    cv = derivada_numerica(u, t)

    # ---- 5.2 Validaciones ---------------------------------------------------
    print("=" * 66)
    print(" VALIDACIONES")
    print("=" * 66)
    print(f"[1] Conservación de N: max|n-1| = {np.max(np.abs(n - 1)):.2e}")
    print(f"[2] mu(t={T_MIN}) = {mu[0]:.8f}  (-> 1 cuando t -> 0)")
    # Ajuste ΔU = a t^2 (T bajas)
    m_low = t <= T_LOW_FIT
    a = np.sum(du[m_low] * t[m_low]**2) / np.sum(t[m_low]**4)
    print(f"[3] ΔU ≈ a t^2 :  a_num = {a:.5f}   a_Sommerfeld = {np.pi**2/4:.5f}")
    # Ajuste C_V = c t (a través del origen)
    gam = np.sum(cv[m_low] * t[m_low]) / np.sum(t[m_low]**2)
    print(f"[4] C_V ≈ gamma t: gamma_num = {gam:.5f}   "
          f"gamma_Sommerfeld = {np.pi**2/2:.5f}   "
          f"(error {abs(gam/(np.pi**2/2)-1)*100:.2f} %)")

    # ---- 5.3 Sensibilidad a E_max, tolerancia y paso de T -------------------
    print("\n Sensibilidad (t = 0.1):")
    t0 = 0.1
    mu0 = potencial_quimico(t0)
    for ns in (10, 20, 30, 40, 60):
        print(f"   E_max = mu + {ns:>2d} t -> u = {energia_interna(mu0, t0, ns):.14f}")
    for N_test in (50, 100, 200, 400):
        tt = np.linspace(T_MIN, T_MAX, N_test)
        _, _, uu = calcular_serie(tt)
        g_ = np.sum((np.gradient(uu, tt, edge_order=2)[tt <= T_LOW_FIT]) * tt[tt <= T_LOW_FIT]) \
             / np.sum(tt[tt <= T_LOW_FIT]**2)
        print(f"   paso con {N_test:>3d} puntos -> gamma = {g_:.6f}")

    # ---- 5.4 Rango ampliado (desviaciones respecto a Sommerfeld) ------------
    t_ext = np.linspace(T_MIN, T_MAX_EXT, N_EXTRA)
    mu_e, _, u_e = calcular_serie(t_ext)
    cv_e = derivada_numerica(u_e, t_ext)

    # ---- 5.5 Tablas CSV -----------------------------------------------------
    tabla = np.column_stack([t, mu, n, abs(n - 1), u, du, du_somm(t), cv, cv_somm(t),
                             cv / cv_somm(t)])
    np.savetxt("resultados_sommerfeld.csv", tabla, delimiter=",",
               header="t=T/TF, mu/EF, N_calc, |N-1|, u, DeltaU, DeltaU_Somm, "
                      "Cv/NkB, Cv_Somm/NkB, ratio", comments="")
    print("\nTabla guardada: resultados_sommerfeld.csv")
    print("\n   t       mu/EF     |N-1|      ΔU        Cv_num    Cv_Somm   ratio")
    for i in range(0, N_T, N_T // 10):
        print(f" {t[i]:.3f}  {mu[i]:.6f}  {abs(n[i]-1):.1e}  {du[i]:.6f}  "
              f"{cv[i]:.5f}  {cv_somm(t[i]):.5f}  {cv[i]/cv_somm(t[i]):.4f}")

    # ---- 5.6 Unidades físicas ----------------------------------------------
    TF = EF_eV / KB_eV
    gamma_fis = (np.pi**2 / 2) * R_GAS / TF * 1e3        # mJ/(mol K^2), 1 mol e-
    print(f"\nMetal de ejemplo: E_F = {EF_eV} eV -> T_F = {TF:.0f} K")
    print(f"gamma (teoría)    = {gamma_fis:.3f} mJ/(mol K^2)")
    print(f"gamma (numérico)  = {gam*R_GAS/TF*1e3:.3f} mJ/(mol K^2)")

    # ---- 5.7 GRÁFICAS -------------------------------------------------------
    plt.rcParams.update({"font.size": 10})
    fig, ax = plt.subplots(2, 3, figsize=(15, 8.5))

    # (1) Densidad de estados
    e = np.linspace(0, 2, 400)
    ax[0, 0].plot(e, densidad_estados(e), 'b')
    ax[0, 0].axvline(1, color='gray', ls='--', label=r'$E_F$')
    ax[0, 0].set(title=r"1. DOS  $g(\epsilon)=\frac{3}{2}\sqrt{\epsilon}$",
                 xlabel=r"$\epsilon=E/E_F$", ylabel=r"$g$ [$N/E_F$]")
    ax[0, 0].legend()

    # (2) Fermi-Dirac a varias T (con mu(T) calculado)
    for tv in (0.01, 0.05, 0.1, 0.2, 0.5):
        mv = potencial_quimico(tv)
        ax[0, 1].plot(e, fermi_dirac(e, tv, mv), label=f"t={tv}")
    ax[0, 1].set(title="2. Fermi-Dirac", xlabel=r"$\epsilon$", ylabel=r"$f$")
    ax[0, 1].legend()

    # (3) mu(T)
    ax[0, 2].plot(t_ext, mu_e, 'b', label="numérico")
    ax[0, 2].plot(t_ext, mu_somm(t_ext), 'r--', label=r"$1-\frac{\pi^2}{12}t^2$")
    ax[0, 2].set(title=r"3. Potencial químico $\mu(T)$", xlabel="t=T/T_F",
                 ylabel=r"$\mu/E_F$", ylim=(-0.2, 1.05))
    ax[0, 2].legend()

    # (4) ΔU
    ax[1, 0].plot(t, du, 'b', label="numérico")
    ax[1, 0].plot(t, du_somm(t), 'r--', label=r"$\frac{\pi^2}{4}t^2$")
    ax[1, 0].set(title=r"4. Energía térmica $\Delta U$", xlabel="t=T/T_F",
                 ylabel=r"$\Delta U/(N E_F)$")
    ax[1, 0].legend()

    # (5) C_V (gráfica principal)
    ax[1, 1].plot(t_ext, cv_e, 'b', label="numérico (dU/dT)")
    ax[1, 1].plot(t_ext, cv_somm(t_ext), 'r--', label=r"Sommerfeld $\frac{\pi^2}{2}t$")
    ax[1, 1].axhline(1.5, color='gray', ls=':', label="clásico 3/2")
    ax[1, 1].set(title=r"5. Capacidad calorífica $C_V/Nk_B$", xlabel="t=T/T_F",
                 ylabel=r"$C_V/(Nk_B)$")
    ax[1, 1].legend()

    # (6) Razón numérico/Sommerfeld
    ax[1, 2].plot(t_ext, cv_e / cv_somm(t_ext), 'g')
    ax[1, 2].axhline(1, color='k', ls='--', lw=0.8)
    ax[1, 2].set(title=r"6. $C_V^{num}/C_V^{Somm}$", xlabel="t=T/T_F",
                 ylabel="razón")

    for a_ in ax.flat:
        a_.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("sommerfeld_resultados.png", dpi=150)
    print("\nFigura guardada: sommerfeld_resultados.png")
    plt.show()


if __name__ == "__main__":
    main()
