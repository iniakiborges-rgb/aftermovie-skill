# Estilo de edición — aftermovies

Fuente: análisis del reel de referencia `UOPAFIESTA.mp4` (28,8 s, 123 BPM) y correcciones a mano sobre
"UOPA Aftermovie v1" (proyecto Resolve `uopafiestafffds`, 2026-11-26). Cada aprendizaje nuevo se agrega
abajo con fecha; no se borra lo anterior. Si algo nuevo contradice lo de acá, **preguntar antes de cambiarlo**.

## Ritmo
- Corte sobre el beat (±4 cuadros); algunos apenas después del golpe (+0,2 s) para empujarlo.
- Unidad de corte ≈ 0,6 s. Por eso a 92 BPM es 1 beat; a 123 BPM, 1–1,5 beats; a 170 BPM, 2 beats.
- Ráfagas de 4–6 tomas de 1 unidad (o media) que cierran con una toma larga de 3–4 unidades para respirar.
- La toma más rápida (media unidad, unos 8 cuadros) se reserva para el arranque del drop.
- **Los cortes no se salen de la grilla:** si una toma se acorta, la siguiente se alarga para compensar. Nunca se usa ripple
  que corra el resto. **V1 termina exactamente con el tema.**

## Estructura
- **Apertura con marca:** un detalle con logo (vaso, cartel proyectado).
- **Subida:** cortes cada 2 unidades que se aceleran a 1, con un riser que crece.
- **Hueco:** unos 0,6 s casi en silencio (se corta el tema 1 beat antes del drop). La toma de antes lo cruza.
- **Drop:** impacto + film burn grande + ráfaga de medias unidades. Después, las ráfagas y las tomas largas alternadas.
- **Cierre con marca:** cartel o logo durante unas 3 unidades.

## Orden de planos
- El ciclo es DJ → público → banda → plano general. Nunca dos tomas seguidas del mismo tipo.
- Intercalar detalles (manos en el controlador, brindis, corazones) y caras que miran a cámara y sonríen.
- No poner cerca dos planos casi iguales, aunque sean de tipos distintos (por ejemplo, dos generales desde el mismo balcón).

## Cámara y zooms
- La cámara se mueve siempre: acercamientos suaves, algún giro o cámara inclinada, barridos con estela como transición.
- Zoom fijo de 1,15–1,2 en tomas alternas de las ráfagas, para dar golpe.
- **Los zooms animados los hace el editor con sus presets.** El skill solo deja marcadores **azules** "zoom in" / "zoom out":
  en la apertura, en la toma que cruza el hueco, en las tomas largas (alternando in y out) y en el cierre.
- Las tomas grabadas de costado se rotan en el timeline y se les pone zoom para llenar el cuadro.

## Destellos (V2)
- Film burn, light leak o flash con el **pico de luz justo en el corte**, en el drop, al entrar a cada toma larga y en el cierre.
- **Modo de composición (corregido a mano):** prefiere **Add** (3 de 6), después Screen (2) y un Linear Dodge.
  El burn grande del drop va en Add.
- **Tamaño (corregido a mano):** zoom de unos 1,0–1,1. Escalarlos para llenar el cuadro (2,9–3,2) quedó demasiado grande.
- **Duración (corregido a mano):** destellos cortos de unos 0,45–0,6 s. El burn del drop dura unos 2 s.
- Los leaks largos se recortan a 1–1,2 s y se elige la parte con más color.

## SFX y mezcla
- Whooshes con el pico en los cortes que entran a las tomas largas y al cierre. En los cortes rápidos, no.
- Riser que termina justo donde empieza el hueco. Impacto (thud) en el cuadro del drop.
- **Ambiente:** nada de pads ni drones (el "TC - SERENE DRONE" se sacó a mano). **Sí** público: "Cheering Crowd Sound Effects"
  **bajito**, debajo del tema durante todo el aftermovie.
- **Volúmenes (confirmados por el editor):** tema 0 dB · riser −5 dB · whooshes −8 dB · impacto 0 dB · público bajito (unos −18 dB, a ajustar a oído).
- **Fundido:** fade out de 1 s al final (tema y ambiente). Se hace a mano; la API no permite fundidos.

## Aprendizajes (historial)
- **2026-11-26 · UOPA Aftermovie v1:**
  - Modos de los destellos: Screen → Add, Linear Dodge en el cierre.
  - Zoom de los destellos: 2,9–3,2 → 1,0–1,1.
  - Chemistry recortado a 0,44 s y leak recortado a 1,16 s, de otra parte del clip.
  - Ambiente (drone) eliminado.
  - Toma larga de banda en 15,0 s acortada 9 cuadros (4 → 3,5 beats), con ripple: todo lo posterior se corrió −0,36 s y el video ahora termina 0,36 s antes que el tema.
    **Confirmado (2026-11-26):** solo quería achicar esa toma; el ripple fue sin querer. Los cortes siguientes quedan en la grilla
    y **el video termina junto con el tema**. La toma larga de banda puede durar 3,5 beats (la siguiente absorbe la diferencia).
  - Volúmenes, fundidos y ambiente: en una primera respuesta quedaron sin completar.
  - **Confirmado después (2026-11-26):** whooshes −8 dB, riser −5 dB (antes sugerido −4), impacto 0 dB, tema 0 dB;
    fade out de 1 s al final; ambiente de público "Cheering Crowd" bajito (antes: sin ambiente).
  - Sin cambios en la elección de tomas, el orden, los zooms fijos, las rotaciones, el riser, el impacto ni los whooshes.

## Parámetros (los leen los scripts)
```json
{
  "shot_unit_seconds": 0.6,
  "gap_seconds": 0.6,
  "build_seconds": 8,
  "type_cycle": ["DJ", "público", "banda", "general"],
  "pattern": {
    "open_units": 3,
    "build_units": [2, 2, 2, 1, 1],
    "burst_count": 8,
    "burst_len_units": 0.5,
    "burst_zoom": 1.2,
    "drop_blocks": [
      {"hold": 3}, {"run": [1, 1, 1, 1]}, {"hold": 4}, {"run": [0.5, 0.5, 1, 1, 1]},
      {"hold": 4}, {"run": [1, 1, 1, 1, 0.5, 0.5]}, {"hold": 4}, {"run": [1, 1, 1, 2]}
    ],
    "close_units": 3
  },
  "flashes": {
    "len": 0.5,
    "drop_len": 2.0,
    "peak_position": 0.5,
    "zoom": 1.05,
    "composite_cycle": ["Add", "Screen", "Screen", "Add", "Add", "LinearDodge"]
  },
  "ambience": {"enabled": true, "level": "bajito (~-18 dB, a oído)"},
  "fade_out_seconds": 1.0,
  "volumes_db": {
    "Tema": "0 dB",
    "Riser": "-5 dB",
    "Whooshes": "-8 dB",
    "Impacto": "0 dB",
    "Ambiente": "bajito, ~-18 dB (a oído)",
    "Fundido": "fade out de 1 s al final (Tema y Ambiente)"
  },
  "resource_keywords": {
    "flash": "burn|leak|flash|chemistry|destello|light ?fx",
    "flash_exclude": "grain|scratch|border|borde|frame|countdown|how to use|hud|emoji|rotate your phone|persona_andando_3",
    "riser": "riser|raiser",
    "whoosh": "whoosh|woosh|swoosh|swipe",
    "impact": "impact|hit|thud|boom|bass ?drop|bombo",
    "ambience": "crowd|public|ambien|atmos"
  },
  "preferred_resources": {
    "flashes": ["Filmburn1 (Screen).mov", "16mm Film Burn (4).mov", "Chemistry 2.mov"],
    "riser": ["Riser Sound Effect.mp3"],
    "ambience": ["Cheering Crowd"],
    "impact": ["Trailer Thud Hit.wav"],
    "whoosh": ["Woosh Effect 4.wav", "Woosh Effect 14.wav", "15. Whoosh Swoosh.wav", "Paper Whoosh 2 (0-01).wav", "Woosh Effect 6.wav", "Woosh Effect 5.wav"]
  }
}
```
