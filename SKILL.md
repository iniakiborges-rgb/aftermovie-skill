---
name: aftermovie
description: Arma un aftermovie de fiesta/evento en DaVinci Resolve Studio con el estilo del editor (estilo.md) - filtra los clips por nitidez/exposición/movimiento, revisa hojas de contacto, crea bin "Filtrados" + timeline "Selects", busca el drop del tema y monta subida/hueco/drop con destellos, SFX y marcadores de zoom; al final aprende de las correcciones a mano y actualiza estilo.md. Usar con /aftermovie o cuando pidan un aftermovie/reel de evento en Resolve.
---

# /aftermovie

Scripts en `~/.claude/skills/aftermovie/scripts/`. Estilo y parámetros en `~/.claude/skills/aftermovie/estilo.md`
(leelo entero al empezar). Carpeta de trabajo: `~/Movies/aftermovie_work/<proyecto>/`.
Correr siempre con `cd ~/.claude/skills/aftermovie/scripts && PYTHONIOENCODING=utf-8 python3 <script> --project <proyecto> ...`

## Reglas fijas
- **No tocar nada existente** en el Media Pool ni en los timelines. Solo se crean bins y timelines nuevos; si el
  nombre existe, los scripts usan "v2", "v3"... No mover, renombrar ni borrar ítems del usuario.
- Requisitos: Resolve Studio abierto con el proyecto, scripting externo en Local y
  `pip3 install --user librosa opencv-python-headless imageio-ffmpeg` (verificar con un import; instalar si falta).
- La API **no** permite: volumen ni fundidos de audio, keyframes de zoom, transiciones ni efectos de Fusion.
  Volúmenes → checklist al final; zooms animados → marcadores azules "zoom in" / "zoom out".

## 0. Preguntas (máximo 3, en una sola AskUserQuestion)
1. **Clips:** bin del Media Pool (por ejemplo `Master`) o carpeta en disco. Antes de preguntar, listá los bins y las carpetas
   probables para ofrecerlos como opciones.
2. **Tema:** archivo o nombre en el Media Pool. Ofrecé los audios largos que encuentres.
3. **Duración máxima:** 30 / 35 / 45 s.
Todo lo demás sale de estilo.md:
- formato vertical 2160×3840;
- nombre del timeline "<Evento> Aftermovie v1";
- recursos de SFX y destellos buscados en todo el Media Pool.
Solo si el usuario lo menciona: reel de referencia, formato horizontal, otro nombre.
`<proyecto>` = nombre del proyecto de Resolve (o del evento).

## 1. Filtrado (automático)
1. `inventory.py --bin "<bin>"` (o `--folder`) → clips.json
2. `analyze_clips.py` (en segundo plano: tarda unos 0,6× la duración total del material) → metrics/
3. `select_windows.py` → windows.json + `sheets/sheet_NN.jpg` y `sheets/descartados_NN.jpg`
4. **Mirá todas las hojas con Read.**
   - **Quedate con:** gente pasándola bien (bailando, riendo, brindando), banda o DJ, buena luz y foco, y detalles de marca (logos, vasos, carteles, merch).
   - **Descartá:** salones vacíos, tomas fuera de foco, tapadas, oscuras, pies, celulares en primer plano.
   - **Revisá los descartados:** rescatá los momentos valiosos (usan el tramo `rescue_in` de 2 s).
   - **Clasificá cada toma** en `DJ | público | banda | general | marca | detalle`, marcá `"role": "open"` en la mejor marca para abrir (vaso o logo) y `"role": "close"` en un cartel o logo para cerrar.
   - **Tomas de costado:** si el contenido se ve girado, poné `"rotate": "cw"` o `"ccw"` (comprobalo rotando un cuadro con cv2).
5. Escribí `<work>/selection.json` (formato en el docstring de build_selects.py) y corré `build_selects.py` → bin
   "Filtrados" + timeline "Selects" en orden cronológico, con el In/Out exacto.
6. **ÚNICA PARADA:** mostrale al usuario el resumen: cuántas tomas por tipo, qué descartaste y por qué, apertura y cierre
   elegidos, y la ruta de las hojas. Esperá su OK o sus cambios (aplicalos editando selection.json y corriendo de nuevo
   build_selects, que crea "Selects v2" sin pisar el anterior).

## 2. Reel de referencia (opcional, solo si lo pasan)
`analyze_reel.py --reel <ruta>`. Mirá `reel/reel_shots.jpg` y reel_analysis.json. Resumí el estilo en 5–7 puntos.
Si contradice estilo.md, preguntá cuál manda **antes** de montar. Lo nuevo y compatible se agrega a estilo.md, con fecha.

## 3. Montaje (sin paradas)
1. `analyze_song.py --song "<ruta>" --max <s>` → muestra 3 candidatos a drop. Usá el 1, salvo que otro tenga
   claramente un break previo más largo (en ese caso `--candidate N`, o `--drop <s>`).
2. `find_resources.py` → resources.json + `sheets/destellos.jpg`. Mirá la hoja: si un "destello" no es luz o burn,
   agregá su nombre a `flash_exclude` en una copia local, no en estilo.md, salvo que el usuario lo confirme.
3. `build_montage.py --name "<Evento> Aftermovie v1" --dry-run`. Revisá la lista de tomas: tipos alternados,
   tomas largas con buen material, sin la misma escena cerca. Si hace falta, ajustá selection.json (tipo, in/len) y repetí.
   Después corré lo mismo sin `--dry-run`.
4. **Verificá:**
   - exportá 8–12 fotogramas con `project.ExportCurrentFrameAsStill` y miralos: apertura, drop, cierre y tomas rotadas;
   - V1 sin huecos y con la misma duración que el tema;
   - que no haya dos tipos iguales seguidos;
   - que no haya dos planos casi idénticos cerca. Si los hay, ajustá selection.json o el plan y rearmá (el script crea una versión nueva; la
     versión mala que **vos** acabás de crear en esta sesión sí la podés borrar con `mp.DeleteTimelines`).
5. **Reportá:** la estructura (subida, hueco, drop, cierre), las pistas, los marcadores y la **checklist de volúmenes**, más lo que la API no deja hacer.

## 4. Aprender de las correcciones (siempre al final)
1. Pedile al usuario que corrija el timeline a mano y te avise. Preguntale también lo que la API no ve:
   volúmenes finales, fundidos, efectos o zooms agregados, y lo que no le gustó o prefiere.
2. `learn_diff.py` (solo lectura) → learn_report.json: tomas sacadas o cambiadas, duraciones, ripple, zooms,
   rotaciones, modos, zoom y duración de los destellos, pistas vaciadas.
3. Resumí lo aprendido en una lista corta. Después actualizá **estilo.md**:
   - agregá una entrada con fecha en "Aprendizajes (historial)" (nunca borres entradas);
   - ajustá las secciones y el bloque JSON solo si el cambio es consistente o el usuario lo confirmó;
   - **si contradice algo anterior, preguntá cuál vale** (AskUserQuestion) antes de cambiar el parámetro;
   - lo ambiguo queda como "A CONFIRMAR" en el historial;
   - un ripple (cortes corridos) o un final de V1 distinto del tema se toma como **accidente**, no como estilo: avisalo
     y no cambies la grilla;
   - si el editor deja ítems sin completar (placeholders entre corchetes), no los inventes: quedan los valores actuales.

## Versionado (automático, sin preguntar)
La carpeta del skill es un repo git privado (`github.com/iniakiborges-rgb/aftermovie-skill`, rama `main`).
**Cada vez que modifiques `estilo.md`, `SKILL.md` o cualquier archivo de `scripts/`**, apenas termines ese cambio
(no al final de la sesión), hacé commit y push sin pedir confirmación:
```
cd ~/.claude/skills/aftermovie && git add -A && git commit -m "<qué cambió y por qué, en una línea>" && git push
```
- Mensaje concreto: p. ej. `estilo: destellos 6→4 frames (aprendizaje <Evento>)` o `build_montage: fix huecos en V1`.
- Nunca subas material de proyectos (clips, hojas, JSON de `~/Movies/aftermovie_work/`): solo viven fuera del repo.
- Si el push falla (sin red, sesión de gh vencida), avisale al usuario con el error; el commit queda local y se sube
  en el próximo push. No uses `--force`.
