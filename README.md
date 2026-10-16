# Entradas TEDxUTNCórdoba · 6° edición

Tablero de control del consumo de entradas del evento: total habilitado, consumo por tipo de entrada
(con Sponsors agrupados por empresa y UTN por sector), consumo por día según la fecha de compra
y la variación entre un reporte y el siguiente.

## Qué hay en el repo

| Archivo | Para qué sirve |
|---|---|
| `docs/index.html` | La página del tablero. Publicada en GitHub Pages lee `docs/reportes.json`; publicada como artifact en claude.ai lee la base de datos del artifact. |
| `docs/reportes.json` | Todos los cortes agregados (solo totales, sin datos personales) que muestra GitHub Pages. |
| `scripts/procesar_reporte.py` | Convierte el CSV de entradas habilitadas en un resumen agregado, sin datos personales. Solo usa la librería estándar de Python 3.9+, no hace falta instalar nada. |

## Cómo se carga un reporte

1. Exportá el CSV de entradas habilitadas (`tickets_HABILITADAS-DD-MM-AAAA HH.MM pm.csv`).
2. Generá el resumen:

   ```bash
   python3 -I scripts/procesar_reporte.py "tickets_HABILITADAS-07-10-2026 19.19 pm.csv" 2026-10-07.json --acumular docs/reportes.json
   ```

   La fecha y la hora del corte se toman del nombre del archivo (acepta hora de 24 h o con am/pm), y las fechas de compra se pasan a hora de Córdoba.
3. Con `--acumular`, el corte se suma a `docs/reportes.json` (un corte del mismo día reemplaza al anterior).
   Hacé commit y push de ese archivo y GitHub Pages se actualiza en uno o dos minutos.
4. Para el artifact de claude.ai, el mismo resumen se guarda en la colección `reportes` de su base, con la fecha del corte como id.

## Emitidas vs usadas (corte final)

Después del evento, el export de habilitadas solo trae las entradas que no se usaron. Para el corte final se arma un CSV con
todas las emitidas (export de UTILIZADAS + export de HABILITADAS) y se procesa con `--usadas`:

```bash
python3 -I scripts/procesar_reporte.py "<emitidas.csv>" /tmp/corte.json --acumular docs/reportes.json --usadas "tickets_UTILIZADAS-….csv"
```

El tablero muestra entonces el panel *Emitidas vs usadas* con el porcentaje de uso por categoría.

## Perfil de asistentes (`docs/perfil.html`)

Página aparte con emitidas vs usadas por segmento: vínculo con UTN, especialidad, año de cursado, edad, si fue a ediciones
anteriores, cómo se enteró y si compró la entrada. Muestra los segmentos principales y un explorador para combinar filtros.
No hay campo de género en el formulario. Los datos (una fila por entrada, sin nombres, DNI ni mails) se generan con
`--perfil` y se publican cifrados con el mismo código de acceso:

```bash
python3 -I scripts/procesar_reporte.py "<emitidas.csv>" /tmp/corte.json --usadas "<usadas.csv>" --perfil /tmp/perfil.json
ASISTENTES_CODIGO='…' node scripts/cifrar_asistentes.mjs /tmp/perfil.json docs/perfil.json
```

## Asistentes por tipo de entrada

El panel muestra nombre, apellido, DNI, mail y teléfono de todas las entradas, filtrable por tipo.

- **claude.ai:** sale de la colección `personas` de la base privada del artifact, que solo lee quien puede editar el tablero.
- **GitHub Pages:** sale de `docs/asistentes.json`, que está **cifrado** (PBKDF2-SHA256 + AES-256-GCM) con el código de acceso.
  La página pide el código y descifra en el navegador. El código no está en el repo: se pasa al cifrar.

  ```bash
  python3 -I scripts/procesar_reporte.py "<csv>" /tmp/corte.json --personas /tmp/personas.json
  ASISTENTES_CODIGO='…' node scripts/cifrar_asistentes.mjs /tmp/personas.json docs/asistentes.json
  rm /tmp/personas.json
  ```

  También se puede abrir el CSV directamente en la página (botón *Abrir CSV de entradas*), sin subir nada.

## GitHub Pages

Settings → Pages → Build and deployment → Source: *Deploy from a branch*, rama `main`, carpeta `/docs`.

El repo es público, así que `docs/reportes.json` (recaudación y cantidades por sponsor y sector) queda visible para cualquiera.
Es temporal: al terminar, borrar el archivo no alcanza porque queda en el historial de git; hay que pasar el repo a privado o borrarlo.

## Cómo se clasifican las entradas

Se usa el nombre de la entrada:

Se evalúa en este orden y gana la primera regla que coincide:

- `PRE VENTA` → Pre venta
- `SPONSOR - <empresa>` → Sponsors, con una fila por empresa
- `UTN - <sector>` → UTN, con una fila por sector
- nombres que contienen `GENERAL` → General
- nombres que contienen `INVITACI` → Invitaciones, separadas según cómo empieza el campo Nombre: *Invitados de oradores* (`ORADOR`, `ORADORA`, `CONDUCTOR`, `CONDUCTORA`), *Coro* (`CORO`), *Sorteo* (`SORTEO`, o mail en `datos/sorteo.tsv`), *Referidos* (`REFE`, `REFERIDO`, `REFERIDA`), *Comunidad TEDx* y *Equipo interno* (listas en `datos/comunidad_tedx.tsv` y `datos/equipo_interno.tsv`, fuera del repo; se reconocen por mail o por nombre y apellido; en Comunidad TEDx se cuentan como pendientes quienes aún no tienen entrada) y *Otras invitaciones*
- cualquier otro nombre → Otros

## Datos personales

Los CSV exportados traen nombre, DNI, mail, teléfono y fecha de nacimiento de cada asistente.
No se suben al repo (ver `.gitignore`), y el tablero guarda solo totales.
