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

## Animaciones para la presentación

```bash
python animaciones.py                    # genera los 4 GIF en animaciones/
python animaciones.py --solo newton cv   # solo algunos
python animaciones.py --mp4              # además MP4 (requiere ffmpeg)
```

| Archivo | Diapositiva | Qué muestra |
|---|---|---|
| `1_fermi_dirac.gif` | 4 (Sebastián) | El escalón de Fermi-Dirac se suaviza al subir T; electrones excitados y huecos alrededor de E_F. |
| `2_newton.gif` | 7 (Joan) | Tangentes de Newton-Raphson sobre F(μ) = N − 1 y convergencia cuadrática de \|N − 1\|. |
| `3_cuadratura.gif` | 9 (Joan) | Subintervalos que elige `quad` al bajar T y comparación con Simpson de paso fijo. |
| `4_derivada_cv.gif` | 11–12 (Jorge) | La pendiente de ΔU(T) dibuja punto a punto la curva C_V(T) frente a Sommerfeld. |

Los GIF se insertan en Google Slides o PowerPoint con *Insertar > Imagen* y se reproducen en bucle.

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

**Versión animada (recomendada para exponer):** `presentacion/presentacion_animada.html`. Se abre con doble clic
en Chrome, Edge o Firefox, sin internet ni instalaciones. Las gráficas se dibujan paso a paso y la física
(Newton, cuadratura adaptativa, C_V y γ) se calcula en vivo en el navegador. Teclas: → / espacio avanzar,
← retroceder, P ventana del presentador (notas y cronómetro), N notas, F pantalla completa.

`presentacion/presentacion_sommerfeld.pptx`: 16 diapositivas en 16:9, estilo "limones"
(paleta y fuentes inspiradas en la plantilla Mantis & Lemon: IM Fell English y Arimo, de Google Fonts),
con ecuaciones editables de PowerPoint y el guion de cada orador en las notas.
`presentacion_sommerfeld_azul.pptx` es la versión anterior, en azul. Para incluir las animaciones, primero generen los GIF y luego vuelvan a
construir el archivo (solo usa la biblioteca estándar de Python):

```bash
python animaciones.py
python presentacion/generar_pptx.py
```

Si no están los GIF, en las diapositivas 4, 7, 9 y 11 se usan las imágenes estáticas de
`presentacion/img/`.

`presentacion/division_trabajo_presentacion.pdf` contiene la división del trabajo,
el cronograma remoto y el guion con diálogos para los 20 minutos.
