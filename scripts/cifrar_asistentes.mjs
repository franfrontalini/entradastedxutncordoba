// Cifra el listado de asistentes (salida de procesar_reporte.py --personas) para publicarlo en GitHub Pages.
// Uso: ASISTENTES_CODIGO='…' node scripts/cifrar_asistentes.mjs <personas.json> docs/asistentes.json
// El código de acceso se pasa por variable de entorno y no se guarda en el repo. La página lo pide y descifra
// en el navegador (PBKDF2-SHA256 → AES-256-GCM, mismos parámetros que docs/index.html).
import { readFileSync, writeFileSync } from 'node:fs';
import { randomBytes, pbkdf2Sync, createCipheriv } from 'node:crypto';

const [src, out] = process.argv.slice(2);
const codigo = (process.env.ASISTENTES_CODIGO || '').trim().toUpperCase();
if (!src || !out || !codigo) {
  console.error("Uso: ASISTENTES_CODIGO='…' node scripts/cifrar_asistentes.mjs <personas.json> docs/asistentes.json");
  process.exit(1);
}

const ITER = 600000;
const salt = randomBytes(16), iv = randomBytes(12);
const key = pbkdf2Sync(codigo, salt, ITER, 32, 'sha256');
const c = createCipheriv('aes-256-gcm', key, iv);
const plano = Buffer.from(JSON.stringify(JSON.parse(readFileSync(src, 'utf8'))), 'utf8');
// WebCrypto espera el tag de autenticación pegado al final del texto cifrado.
const data = Buffer.concat([c.update(plano), c.final(), c.getAuthTag()]);
writeFileSync(out, JSON.stringify({ v: 1, kdf: 'PBKDF2-SHA256', iter: ITER, salt: salt.toString('base64'), iv: iv.toString('base64'), data: data.toString('base64') }));
console.log(`${out}: ${data.length} bytes cifrados`);
