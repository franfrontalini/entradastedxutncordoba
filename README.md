# Entradas TEDxUTNCórdoba · 6° edición

Tablero de control del consumo de entradas del evento: total habilitado, consumo por tipo de entrada
(con Sponsors agrupados por empresa y UTN por sector), consumo por día según la fecha de compra
y la variación entre un reporte y el siguiente.

## Qué hay en el repo

| Archivo | Para qué sirve |
|---|---|
| `tablero/entradas.html` | La página del tablero. Está publicada como artifact en claude.ai y lee los reportes de la base de datos del artifact. |
| `scripts/procesar_reporte.py` | Convierte el CSV de entradas habilitadas en un resumen agregado, sin datos personales. Solo usa la librería estándar de Python 3.9+, no hace falta instalar nada. |

## Cómo se carga un reporte

1. Exportá el CSV de entradas habilitadas (`tickets_HABILITADAS-DD-MM-AAAA HH.MM pm.csv`).
2. Generá el resumen:

   ```bash
   python3 -I scripts/procesar_reporte.py "tickets_HABILITADAS-07-10-2026 19.19 pm.csv" 2026-10-07.json
   ```

   La fecha y la hora del corte se toman del nombre del archivo (acepta hora de 24 h o con am/pm), y las fechas de compra se pasan a hora de Córdoba.
3. Ese resumen se guarda en la colección `reportes` del tablero, con la fecha del corte como id.
   Un reporte nuevo del mismo día reemplaza al anterior.

## Cómo se clasifican las entradas

Se usa el nombre de la entrada:

Se evalúa en este orden y gana la primera regla que coincide:

- `PRE VENTA` → Pre venta
- `SPONSOR - <empresa>` → Sponsors, con una fila por empresa
- `UTN - <sector>` → UTN, con una fila por sector
- nombres que contienen `GENERAL` → General
- nombres que contienen `INVITACI` → Invitaciones
- cualquier otro nombre → Otros

## Datos personales

Los CSV exportados traen nombre, DNI, mail, teléfono y fecha de nacimiento de cada asistente.
No se suben al repo (ver `.gitignore`), y el tablero guarda solo totales.
