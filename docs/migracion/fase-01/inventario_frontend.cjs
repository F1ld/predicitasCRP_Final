// Herramienta de fase 1; TypeScript se lee de un node_modules de laboratorio.
// No ejecuta componentes ni modifica el frontend.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../../..');
const src = path.join(root, 'frontend-predicitas/src');
const ts = require(process.argv[2]);
const cache = new Map();
const relative = value => path.relative(root, value).replaceAll('\\', '/');
function resolveFile(base, specifier) {
  const basePath = path.resolve(path.dirname(base), specifier);
  return [basePath, ...['.ts', '.tsx', '.js', '.jsx'].map(ext => basePath + ext), ...['.ts', '.tsx', '.js', '.jsx'].map(ext => path.join(basePath, 'index' + ext))].find(file => fs.existsSync(file) && fs.statSync(file).isFile());
}
function parse(file) {
  if (cache.has(file)) return cache.get(file);
  const text = fs.readFileSync(file, 'utf8');
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const variables = new Map(), imports = new Map(), edges = [];
  for (const statement of source.statements) {
    if (ts.isVariableStatement(statement)) for (const declaration of statement.declarationList.declarations) if (ts.isIdentifier(declaration.name)) variables.set(declaration.name.text, declaration.initializer);
    if ((ts.isImportDeclaration(statement) || ts.isExportDeclaration(statement)) && statement.moduleSpecifier && ts.isStringLiteral(statement.moduleSpecifier)) {
      const specifier = statement.moduleSpecifier.text;
      if (!specifier.startsWith('.')) continue;
      const target = resolveFile(file, specifier);
      if (!target) throw Error(`Import relativo no resuelto: ${relative(file)} -> ${specifier}`);
      if (!statement.isTypeOnly && !statement.importClause?.isTypeOnly && /\.[jt]sx?$/.test(target)) edges.push(target);
      if (ts.isImportDeclaration(statement) && statement.importClause?.namedBindings && ts.isNamedImports(statement.importClause.namedBindings)) for (const item of statement.importClause.namedBindings.elements) imports.set(item.name.text, {file: target, name: (item.propertyName ?? item.name).text});
    }
  }
  const result = {source, variables, imports, edges};
  cache.set(file, result);
  return result;
}
function literal(node, file, seen = new Set()) {
  if (ts.isStringLiteral(node) || ts.isNumericLiteral(node)) return ts.isNumericLiteral(node) ? Number(node.text) : node.text;
  if (ts.isArrayLiteralExpression(node)) return node.elements.map(item => literal(item, file, seen));
  if (ts.isAsExpression(node) || ts.isSatisfiesExpression(node) || ts.isParenthesizedExpression(node)) return literal(node.expression, file, seen);
  if (ts.isIdentifier(node)) {
    const key = `${file}:${node.text}`;
    if (seen.has(key)) throw Error(`Referencia circular ${key}`);
    const next = new Set([...seen, key]), info = parse(file);
    if (info.variables.has(node.text)) return literal(info.variables.get(node.text), file, next);
    const imported = info.imports.get(node.text);
    if (imported) return literal({kind: ts.SyntaxKind.Identifier, text: imported.name}, imported.file, next);
  }
  throw Error(`Constante no resuelta en ${relative(file)}: ${node.getText?.() ?? node.text}`);
}
const routes = [], menu = [], roots = [path.join(src, 'main.tsx')];
for (const moduleName of fs.readdirSync(path.join(src, 'modulos'))) for (const [filename, output] of [['rutas.tsx', routes], ['menu.ts', menu]]) {
  const file = path.join(src, 'modulos', moduleName, filename);
  if (!fs.existsSync(file)) continue;
  roots.push(file);
  const info = parse(file);
  function visit(node) {
    if (ts.isObjectLiteralExpression(node)) {
      const properties = new Map(node.properties.filter(ts.isPropertyAssignment).map(prop => [prop.name.getText(info.source), prop.initializer]));
      if (properties.has('ruta') && properties.has('roles')) output.push({module: moduleName, route: literal(properties.get('ruta'), file), roles: literal(properties.get('roles'), file), label: properties.has('etiqueta') ? literal(properties.get('etiqueta'), file) : null, order: properties.has('orden') ? literal(properties.get('orden'), file) : null, source: relative(file), line: info.source.getLineAndCharacterOfPosition(node.getStart(info.source)).line + 1, test_only: info.source.text.includes('import.meta.env.MODE === "test"')});
    }
    ts.forEachChild(node, visit);
  }
  visit(info.source);
}
const reached = new Set();
function walk(file) { if (reached.has(file)) return; reached.add(file); for (const next of parse(file).edges) walk(next); }
for (const file of roots) walk(file);
const legacy = [];
for (const dirname of ['pages', 'auth', 'components', 'lib']) for (const filename of fs.readdirSync(path.join(src, dirname))) {
  const file = path.join(src, dirname, filename);
  if (/\.[jt]sx?$/.test(file)) legacy.push({file: relative(file), reachable_from_current_entry_and_discovered_modules: reached.has(file)});
}
const result = {typescript_tool_version: ts.version, production_module_routes: routes.filter(row => !row.test_only).length, test_only_routes: routes.filter(row => row.test_only).length, routes, menu, shell_routes: [{route: '/', roles: ['ADMINISTRADOR', 'RECEPCION', 'TECNICO_IA'], behavior: 'inicioPorRol; actualmente /citas'}, {route: '/importar', roles: ['ADMINISTRADOR', 'RECEPCION', 'TECNICO_IA'], behavior: 'redirect /citas/importar; destino aplica su propio permiso'}, {route: '*', roles: ['publico'], behavior: 'pagina no encontrada'}], legacy, limitations: 'Grafo estatico de imports relativos y ranuras conocidas; no prueba navegacion HTTP ni consumidores externos. Imports de solo tipo no cuentan; ramas de prueba se identifican aparte. No autoriza borrar legacy.'};
const out = path.join(__dirname, 'frontend_rutas_menu_alcance.json');
fs.writeFileSync(out, JSON.stringify(result, null, 2) + '\n', {flag: 'wx'});
console.log(JSON.stringify({production_routes: result.production_module_routes, test_routes: result.test_only_routes, menu_entries: menu.length, legacy_code_files: legacy.length, legacy_reachable: legacy.filter(row => row.reachable_from_current_entry_and_discovered_modules).length}));
