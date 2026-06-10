# Diseño: YouTube Downloader (self-hosted, web)

**Fecha:** 2026-06-09
**Estado:** Aprobado por el usuario

## Resumen

Aplicación web self-hosted y open-source para descargar contenido de YouTube.
El público objetivo final usa solo el navegador; quien despliega el sitio levanta
una imagen Docker con un comando. El motor real de descarga corre del lado del
servidor (no del navegador), porque una descarga 100% client-side de YouTube no es
viable de forma confiable (CORS de googlevideo.com + cifrado de firmas que cambia
constantemente).

## Decisiones tomadas (brainstorming)

- **Interfaz:** app web, UI simple. El visitante no instala nada.
- **Arquitectura:** self-hosted open-source. El operador despliega su propia
  instancia. Hostear una instancia pública es decisión aparte del usuario y NO es
  parte del código de este proyecto (trae riesgo legal, costo de ancho de banda y
  bloqueo de IP).
- **Despliegue:** Docker, un solo comando. Todo empaquetado (web + yt-dlp + ffmpeg).
- **Stack (Enfoque A):** Python + FastAPI usando `yt-dlp` como librería nativa +
  frontend HTML/CSS/JS liviano servido por el mismo servidor.
- **Funciones:** video MP4 con resolución seleccionable, audio MP3/M4A con bitrate
  seleccionable (128/192/256/320 kbps), playlists enteras, subtítulos.

## Arquitectura general

Una sola app FastAPI sirve tanto el frontend como la API. El navegador habla con
la app; la app usa `yt-dlp` como librería y `ffmpeg` para procesar. Todo va en una
imagen Docker.

```
Navegador (UI simple)  ──HTTP/SSE──>  FastAPI
                                        ├── yt-dlp (extracción + descarga)
                                        └── ffmpeg (MP3 / unir video+audio)
        contenedor Docker  ───────────────┘
```

## Flujo de uso

1. Usuario pega la URL → la UI pide metadata (`POST /api/info`).
2. Backend usa yt-dlp para devolver: título, miniatura, duración, si es playlist,
   y calidades disponibles.
3. La UI muestra esa info + opciones: video (con resolución) o audio (con bitrate),
   subtítulos sí/no.
4. Usuario da "Descargar" → `POST /api/download` crea un job y devuelve `job_id`.
5. La UI abre un stream SSE (`GET /api/progress/{job_id}`) y muestra una barra de
   progreso en tiempo real (yt-dlp expone el % vía progress hook).
6. Al terminar, la UI baja el archivo final (`GET /api/file/{job_id}`).
7. El backend limpia los temporales tras la entrega (o por TTL).

## Componentes (módulos)

- **`main.py`** — app FastAPI, rutas, sirve el frontend estático.
- **`downloader.py`** — envuelve yt-dlp: extraer info, lógica de selección de
  formato/calidad, descarga con progress hook.
- **`jobs.py`** — registro de jobs en memoria (`job_id → estado, progreso, ruta de
  archivo, error). En memoria es suficiente para self-hosted (YAGNI: sin DB ni Redis).
- **`models.py`** — esquemas Pydantic de requests/responses.
- **`static/`** — `index.html`, `app.js`, `style.css` (UI simple).

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| `GET`  | `/` | Sirve la UI |
| `POST` | `/api/info` | `{url}` → metadata + formatos disponibles |
| `POST` | `/api/download` | `{url, tipo, resolucion, bitrate, subtítulos, idioma_sub}` → `{job_id}` |
| `GET`  | `/api/progress/{job_id}` | Stream SSE con el progreso |
| `GET`  | `/api/file/{job_id}` | Entrega el archivo final |

## Manejo de formatos

- **Video:** selector yt-dlp `bestvideo[height<=N]+bestaudio/best`, unido a MP4 con
  ffmpeg. N viene de la calidad elegida (1080, 720, 480, ...).
- **Audio:** `bestaudio` + postprocesador `FFmpegExtractAudio` para MP3 o M4A, con
  bitrate seleccionable (128/192/256/320 kbps vía `preferredquality`).
- **Subtítulos:** `writesubtitles` / `writeautomaticsub` con idioma seleccionable.
  Se entregan como archivo `.srt` separado junto al video (no incrustados), dentro
  de un ZIP cuando se piden subtítulos. Esto evita complejidad extra de ffmpeg.
- **Playlists:** se detectan en `/api/info`; se descargan en secuencia (progreso por
  ítem) y se entregan como un ZIP.

## Manejo de errores

- URL inválida / video no disponible / privado → mensaje claro en la UI (no stack trace).
- Errores de yt-dlp (geobloqueo, bloqueo de IP) → mensaje amigable.
- Job inexistente o expirado → 404.

## Límites y concurrencia

- Semáforo que limita descargas simultáneas (no martillar YouTube ni reventar el server).
- Carpeta temporal por job, borrada tras la entrega o por TTL.

## Docker

- `Dockerfile` sobre `python:slim`, instala `ffmpeg` vía apt + `pip install fastapi
  uvicorn yt-dlp`.
- Arranque: `docker run -p 8000:8000 ytdl` → abrir `localhost:8000`.
- `docker-compose.yml` opcional para comodidad.

## Testing (TDD)

Siguiendo la metodología de Superpowers (red/green TDD):
- Tests unitarios de la lógica de selección de formato y del registro de jobs.
- Tests de integración de los endpoints con yt-dlp mockeado (no pegarle a YouTube
  real en tests → sería frágil).

## Fuera de alcance (YAGNI)

Sin cuentas de usuario, sin historial, sin base de datos, sin autenticación, sin el
tema de hosting público (decisión aparte del usuario, no código de este proyecto).
