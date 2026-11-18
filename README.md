# Capacidad calorífica electrónica a T finita (modelo de Sommerfeld)

Sebastián Sánchez · Joan Tovar · Jorge Garzón

Simulación numérica de la contribución electrónica a la capacidad calorífica de un
metal (gas de electrones libres 3D) integrando la densidad de estados con la
distribución de Fermi-Dirac.

## Cómo ejecutar

```bash
pip install -r requirements.txt
python sommerfeld_cv.py               # imprime validaciones y abre las gráficas
python sommerfeld_cv.py --sin-ventana  # solo guarda CSV y figuras
```

Salidas:

- `resultados_sommerfeld.csv`: t, μ, iteraciones de Newton, N, U, ΔU, C_V y comparación con Sommerfeld.
- `sommerfeld_resultados.png`: figura resumen 2×3.
- `figuras/*.png`: cada gráfica por separado, lista para las diapositivas.

## Qué hace cada parte (requisitos del proyecto)

| Requisito | Implementación |
|---|---|
| Ecuación de ligadura μ(T) | `potencial_quimico`: Newton-Raphson con salvaguarda de bisección; ∂N/∂μ se integra numéricamente. Contraste con Brent (`brentq`). |
| Integración adaptativa de U(T) | `energia_interna`: `scipy.integrate.quad` (Gauss-Kronrod adaptativo, QUADPACK) con punto de ruptura en μ y corte en μ + 40 k_BT. |
| Diferenciación numérica y γ | `derivada_numerica` (diferencias centrales O(h²)) y `ajustar_gamma` (ajuste C_V = γT + δT³). |

## Unidades

ε = E/E_F, t = T/T_F, g(ε) = (3/2)√ε normalizada a N = 1. Resultado esperado:
C_V/(N k_B) = (π²/2) t, es decir γ = π²/2 ≈ 4.9348. Para el cobre (E_F = 7.0 eV)
el script convierte γ a mJ/(mol K²) y lo compara con el valor experimental.

## Presentación

`presentacion/division_trabajo_presentacion.pdf` contiene la división del trabajo,
el cronograma remoto y el guion con diálogos para los 20 minutos.
