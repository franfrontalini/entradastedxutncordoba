"""Convierte un CSV de entradas habilitadas en el resumen agregado (sin datos personales) que usa el tablero.
Uso: python3 -I procesar_reporte.py <csv> <salida.json> [--acumular docs/reportes.json]
Con --acumular, además agrega el corte al archivo que lee el tablero en GitHub Pages
(un corte del mismo día reemplaza al anterior).
Con --personas <archivo.json>, además genera el listado de asistentes de todas las entradas
(nombre, apellido, DNI, mail, teléfono). Ese archivo tiene datos personales: nunca va al repo sin cifrar
(ver scripts/cifrar_asistentes.mjs).
Solo usa la librería estándar (Python 3.9+)."""
import sys, re, json, os, csv, hashlib, unicodedata
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

# Las invitaciones se marcan en el campo Nombre: "ORADOR/ORADORA …" y "CONDUCTOR/CONDUCTORA …" van a
# Invitados de oradores; "CORO …" va a Coro; el resto, a Otras invitaciones.
ORADOR = re.compile(r'\s*(ORADOR|CONDUCTOR)(A|ES|AS)?\b', re.I)
CORO = re.compile(r'\s*COROS?\b', re.I)

# Listas fijas de invitados (en datos/, fuera del repo). Una invitación cuyo mail o nombre y apellido (en cualquier
# orden) figura en una lista va a esa categoría. Con pendientes=True se cuenta quiénes de la lista no tienen entrada.
INVITACIONES = 'INVITACIONES ESPECIALES'
LISTAS = [
    {'nombre': 'Comunidad TEDx', 'archivo': 'comunidad_tedx.tsv', 'pendientes': True},
    {'nombre': 'Equipo interno', 'archivo': 'equipo_interno.tsv', 'pendientes': False},
]

def clave(nombre, apellido):
    t = unicodedata.normalize('NFKD', f'{nombre} {apellido}').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'\s+', ' ', t).strip()

def mail(t):
    t = (t or '').strip().lower()
    return t[:-4] + '.com' if t.endswith('.con') else t

def claves(nombre, apellido):
    return {clave(nombre, apellido), clave(apellido, nombre)} if clave(nombre, apellido) else set()

def leer_listas():
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'datos')
    for L in LISTAS:
        L['miembros'] = []
        ruta = os.path.join(base, L['archivo'])
        if os.path.exists(ruta):
            with open(ruta, encoding='utf-8', newline='') as f:
                L['miembros'] = [{'nombre': (r.get('nombre') or '').strip(), 'apellido': (r.get('apellido') or '').strip(), 'email': (r.get('email') or '').strip()}
                                 for r in csv.DictReader(f, delimiter='\t') if (r.get('email') or '').strip() or (r.get('nombre') or '').strip()]
        L['mails'] = {mail(m['email']) for m in L['miembros'] if m['email']}
        L['claves'] = set().union(*(claves(m['nombre'], m['apellido']) for m in L['miembros']))
    return [L for L in LISTAS if L['miembros']]

LISTAS_ACTIVAS = leer_listas()

def lista_de(r):
    m, k = mail(r.get('Email')), clave(r.get('Nombre') or '', r.get('Apellido') or '')
    for L in LISTAS_ACTIVAS:
        if (m and m in L['mails']) or (k and k in L['claves']): return L['nombre']
    return None

def invitacion(nombre):
    if ORADOR.match(nombre): return 'Invitados de oradores'
    if CORO.match(nombre): return 'Coro'
    return 'Otras invitaciones'

def entrada_de(r):
    e = r['Entrada'].strip()
    if grupo(e) == 'invitacion':
        e += ' - ' + (lista_de(r) or invitacion(r.get('Nombre') or ''))
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
# Pendientes: integrantes de una lista con pendientes=True que no tienen entrada en este corte.
p_mails = {mail(r.get('Email')) for r in crudas}
p_claves = {clave(r.get('Nombre') or '', r.get('Apellido') or '') for r in crudas}
pendientes = {}
for L in LISTAS_ACTIVAS:
    if not L['pendientes']: continue
    t = f"{INVITACIONES} - {L['nombre']}"
    pendientes[t] = [m for m in L['miembros'] if not (m['email'] and mail(m['email']) in p_mails) and not (claves(m['nombre'], m['apellido']) & p_claves)]
    if not any(x['nombre'] == t for x in tipos):
        tipos.append({'nombre': t, 'grupo': 'invitacion', 'cantidad': 0, 'precio': 0, 'recaudacion': 0})
tipos.sort(key=lambda t: (-t['cantidad'], t['nombre']))

dias = [{'dia': k, 'total': sum(c.values()),
         'tipos': [{'nombre': n, 'cantidad': q} for n, q in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))]}
        for k, c in sorted(por_dia.items())]

doc = {'fecha': fecha, 'hora': hora, 'archivo': base, 'total': len(filas),
       'pagas': sum(r['precio'] > 0 for r in filas), 'sinCargo': sum(r['precio'] <= 0 for r in filas),
       'recaudacion': int(sum(r['precio'] for r in filas)), 'tipos': tipos, 'dias': dias}
if pendientes: doc['pendientes'] = {t: len(ps) for t, ps in pendientes.items()}
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
    # Para clasificar un CSV abierto en la página sin publicar la lista: solo hashes de mail y de nombre.
    h = lambda t: hashlib.sha256(t.encode()).hexdigest()
    listas_pub = [{'nombre': L['nombre'], 'pendientes': L['pendientes'],
                   'miembros': [{'e': h(mail(m['email'])) if m['email'] else '', 'n': sorted(h(k) for k in claves(m['nombre'], m['apellido']))} for m in L['miembros']]}
                  for L in LISTAS_ACTIVAS]
    with open(acumular, 'w', encoding='utf-8') as f:
        json.dump({'reportes': todos, 'listas': listas_pub}, f, ensure_ascii=False, separators=(',', ':'))
    print(f'{acumular}: {len(todos)} cortes')
if personas:
    # Una entrada por documento de la colección `personas`, con id derivado del nombre de la entrada.
    campo = lambda r, k: (r.get(k) or '').strip()
    listas = defaultdict(list)
    for r in crudas:
        e = entrada_de(r)
        listas[e].append({'nombre': campo(r, 'Nombre'), 'apellido': campo(r, 'Apellido'), 'documento': campo(r, 'Documento'),
                         'email': campo(r, 'Email'), 'telefono': campo(r, 'Teléfono'), 'dia': dia(r['Fecha de compra'])})
    def slug(t):
        import unicodedata
        t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode().lower()
        return re.sub(r'[^a-z0-9]+', '-', t).strip('-')
    for t in pendientes: listas.setdefault(t, [])
    salida = [{'id': slug(e), 'entrada': e, 'grupo': grupo(e), 'corte': fecha + ' ' + hora,
               'personas': sorted(ps, key=lambda x: (x['apellido'].lower(), x['nombre'].lower()))}
              for e, ps in sorted(listas.items())]
    for x in salida:
        if x['entrada'] in pendientes: x['pendientes'] = pendientes[x['entrada']]
    with open(personas, 'w', encoding='utf-8') as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    print(f'{personas}: ' + ', '.join(f"{x['entrada']} ({len(x['personas'])})" for x in salida))
print(json.dumps({k: doc[k] for k in ('fecha', 'hora', 'total', 'pagas', 'sinCargo', 'recaudacion')}, ensure_ascii=False))
for t in tipos: print(t)
print(dias[-3:])
