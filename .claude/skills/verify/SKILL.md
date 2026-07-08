---
name: verify
description: Cómo verificar cambios de esta app customtkinter corriendo la app real y capturando evidencia (no hay tests; la verificación es manual por diseño).
---

# Verificar Arch Productivity Hub

No hay Xvfb ni xdotool en esta máquina; sí hay sesión gráfica (XWayland, `DISPLAY` definido)
e ImageMagick `import`. La app se corre en el display real — la ventana aparece unos
segundos en el escritorio del usuario y el compositor puede tilearla más angosta que el
`geometry()` pedido (se ha visto ~670px pese a `minsize(1200,800)`).

## Receta que funciona

Driver Python en el scratchpad que importa `main` (está guardado por `__name__`, no arranca
solo), instancia `main.ArchProductivityApp()` y encadena pasos con `app.after(ms, ...)`:

- Cambiar de pestaña: `app.tabview.set("Tesorería")` + `app.orquestar_refrescos()` (el set
  NO dispara el command).
- Clic programático: `boton.invoke()` (customtkinter 5.3.0; NO existe `_clicked`).
- Encontrar widgets: recorrer `winfo_children()` recursivo filtrando por `isinstance`
  (ctk.CTkButton/CTkLabel/CTkEntry/CTkToplevel) y `cget("text")` / `.title()`. OJO: el
  recorrido con pila es LIFO — no asumas orden de creación; identifica entries por
  `cget("placeholder_text")`.
- Screenshot por ventana: `import -window hex(widget.winfo_id()) out.png` (sirve para la
  ventana principal y para cada CTkToplevel).
- Los messagebox nativos BLOQUEAN sin usuario: parchear antes
  `tabs.<modulo>.messagebox.showerror = lambda *a, **k: registro.append(a)` para probar
  rutas de validación.

## Datos: la BD es la COMPARTIDA real

Todo corre contra el MariaDB del servidor. Para ejercitar escrituras: crear una cuenta/fila
de prueba con nombre inconfundible (`ZZ TEST ...`), y borrarla al inicio Y al final del
driver. **El proceso vuelca core al salir** (teardown de Tk en este entorno, preexistente,
también sin cambios en el repo) — `atexit` NO corre, así que la limpieza de arranque es la
que de verdad garantiza no dejar basura; verifica residuos con un query aparte al terminar.

## Qué mirar en las capturas

- Modo claro: el sistema está en light mode; los frames hardcodeados `#1e293b` necesitan
  `text_color` explícito o el texto por defecto queda oscuro sobre oscuro.
- La barra de cuentas de Tesorería usa un carril horizontal scrolleable; si agregas líneas
  a las tarjetas revisa que la altura del carril no las recorte (height fijo).
