"""Convierte un CSV de entradas habilitadas en el resumen agregado (sin datos personales) que usa el tablero.
Uso: python3 -I procesar_reporte.py <csv> <salida.json> [--acumular docs/reportes.json]
Con --acumular, además agrega el corte al archivo que lee el tablero en GitHub Pages
(un corte del mismo día reemplaza al anterior).
Con --personas <archivo.json>, además genera el listado de asistentes de Sponsors, UTN e Invitaciones
(nombre, apellido, DNI, mail, teléfono) para la base privada del artifact. Ese archivo tiene datos
personales: nunca va al repo ni a GitHub Pages.
Solo usa la librería estándar (Python 3.9+)."""
import sys, re, json, os, csv
from collections import Counter, defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo('America/Argentina/Cordoba')

def grupo(nombre):
    n = nombre.upper().strip()
    if n.startswith('PRE VENTA') or n.startswith('PREVENTA'): return 'preventa'
    if n.startswith('SPONSOR'): return 'sponsor'
    if n.startswith('UTN'): return 'utn'
    if 'GENERAL' in n: return 'general'
    if 'INVITACI' in n: return 'invitacion'
    return 'otros'

# Los invitados de oradores vienen con el nombre cargado como "ORADOR …" u "ORADORA …".
ORADOR = re.compile(r'\s*ORADOR(A|ES|AS)?\b', re.I)

def entrada_de(r):
    e = r['Entrada'].strip()
    if grupo(e) == 'invitacion':
        e += ' - ' + ('Invitados de oradores' if ORADOR.match(r.get('Nombre') or '') else 'Otras invitaciones')
    return e

def precio(v):
    try: return float(v)
    except (TypeError, ValueError): return 0.0

def dia(v):
    # Viene en UTC con Z (2026-08-28T02:26:42.184Z); se pasa a hora de Córdoba.
    return datetime.fromisoformat(v.strip().replace('Z', '+00:00')).astimezone(TZ).strftime('%Y-%m-%d')

def opcion(args, nombre):
    if nombre not in args: return None
    i = args.index(nombre)
    if i + 1 >= len(args): sys.exit(__doc__)
    v = args[i + 1]
    del args[i:i + 2]
    return v

args = sys.argv[1:]
acumular = opcion(args, '--acumular')
personas = opcion(args, '--personas')
if len(args) != 2: sys.exit(__doc__)
src, out = args
base = os.path.basename(src)
m = re.search(r'(\d{2})-(\d{2})-(\d{4})[ _](\d{1,2})[._](\d{2})(?:\s*([ap])\.?\s*m)?', base, re.I)
if not m: sys.exit('No pude leer fecha y hora del nombre del archivo: ' + base)
d, mo, y, hh, mi, ampm = m.groups()
h = int(hh)
if ampm and h <= 12:
    if ampm.lower() == 'p' and h < 12: h += 12
    if ampm.lower() == 'a' and h == 12: h = 0
fecha, hora = f'{y}-{mo}-{d}', f'{h:02d}:{mi}'

with open(src, encoding='utf-8-sig', newline='') as f:
    crudas = list(csv.DictReader(f))
filas = [{'entrada': entrada_de(r), 'precio': precio(r['Precio']), 'dia': dia(r['Fecha de compra'])} for r in crudas]

por_tipo = defaultdict(list)
por_dia = defaultdict(Counter)
for r in filas:
    por_tipo[r['entrada']].append(r['precio'])
    por_dia[r['dia']][r['entrada']] += 1

tipos = []
for nombre, ps in por_tipo.items():
    moda = min(Counter(ps).most_common(), key=lambda kv: (-kv[1], kv[0]))[0]
    tipos.append({'nombre': nombre, 'grupo': grupo(nombre), 'cantidad': len(ps),
                  'precio': int(moda), 'recaudacion': int(sum(ps))})
tipos.sort(key=lambda t: (-t['cantidad'], t['nombre']))

dias = [{'dia': k, 'total': sum(c.values()),
         'tipos': [{'nombre': n, 'cantidad': q} for n, q in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))]}
        for k, c in sorted(por_dia.items())]

doc = {'fecha': fecha, 'hora': hora, 'archivo': base, 'total': len(filas),
       'pagas': sum(r['precio'] > 0 for r in filas), 'sinCargo': sum(r['precio'] <= 0 for r in filas),
       'recaudacion': int(sum(r['precio'] for r in filas)), 'tipos': tipos, 'dias': dias}
if not (sum(t['cantidad'] for t in tipos) == doc['total'] == sum(x['total'] for x in dias)):
    sys.exit('Los totales no cierran entre tipos, días y filas.')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(doc, f, ensure_ascii=False, indent=1)
if acumular:
    try:
        with open(acumular, encoding='utf-8') as f: todos = json.load(f).get('reportes', [])
    except FileNotFoundError:
        todos = []
    todos = sorted([r for r in todos if r.get('fecha') != fecha] + [doc], key=lambda r: r['fecha'])
    with open(acumular, 'w', encoding='utf-8') as f:
        json.dump({'reportes': todos}, f, ensure_ascii=False, separators=(',', ':'))
    print(f'{acumular}: {len(todos)} cortes')
if personas:
    # Una entrada por documento de la colección `personas`, con id derivado del nombre de la entrada.
    GRUPOS_CON_NOMBRES = ('sponsor', 'utn', 'invitacion')
    campo = lambda r, k: (r.get(k) or '').strip()
    listas = defaultdict(list)
    for r in crudas:
        e = entrada_de(r)
        if grupo(e) in GRUPOS_CON_NOMBRES:
            listas[e].append({'nombre': campo(r, 'Nombre'), 'apellido': campo(r, 'Apellido'), 'documento': campo(r, 'Documento'),
                              'email': campo(r, 'Email'), 'telefono': campo(r, 'Teléfono'), 'dia': dia(r['Fecha de compra'])})
    def slug(t):
        import unicodedata
        t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode().lower()
        return re.sub(r'[^a-z0-9]+', '-', t).strip('-')
    salida = [{'id': slug(e), 'entrada': e, 'grupo': grupo(e), 'corte': fecha + ' ' + hora,
               'personas': sorted(ps, key=lambda x: (x['apellido'].lower(), x['nombre'].lower()))}
              for e, ps in sorted(listas.items())]
    with open(personas, 'w', encoding='utf-8') as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    print(f'{personas}: ' + ', '.join(f"{x['entrada']} ({len(x['personas'])})" for x in salida))
print(json.dumps({k: doc[k] for k in ('fecha', 'hora', 'total', 'pagas', 'sinCargo', 'recaudacion')}, ensure_ascii=False))
for t in tipos: print(t)
print(dias[-3:])
