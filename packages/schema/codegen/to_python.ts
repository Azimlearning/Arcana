// Schema codegen — TypeScript → Pydantic.
//
// Walks packages/schema/src/*.ts and emits api/genui/_generated.py.
// The generated file is committed; `codegen:check` diffs it against the
// freshly generated content and exits non-zero on drift. That is the
// mechanism behind R-10 ("no payload drift") and preflight 0.3 / the CI
// gate `codegen --check`.
//
// Supported TS constructs (slice scope — extend as the schema grows):
//   - export interface Foo { ... }                  → class Foo(BaseModel)
//   - export type X = 'a' | 'b' | 'c'               → X = Literal['a', 'b', 'c']
//   - export type X = Y                             → X = Y
//   - export type X = A | B | ...   (all class refs with `type:` lit)
//                                                   → Annotated[Union[A, B], Field(discriminator='type')]
//   - Field types: string | number | boolean | null | T[] | Array<T>
//                  | 'literal' | T | A | B | A | null | Foo
//
// Anything else fails loudly with the offending construct printed.

import { Project, SyntaxKind } from 'ts-morph';
import type {
  InterfaceDeclaration,
  PropertySignature,
  TypeAliasDeclaration,
  TypeNode,
  UnionTypeNode,
} from 'ts-morph';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PKG_ROOT = resolve(__dirname, '..');
const REPO_ROOT = resolve(PKG_ROOT, '..', '..');
const OUTPUT = resolve(REPO_ROOT, 'api', 'genui', '_generated.py');

const isCheck = process.argv.includes('--check');

// ─── Load source ──────────────────────────────────────────────
const project = new Project({
  tsConfigFilePath: resolve(PKG_ROOT, 'tsconfig.json'),
  skipAddingFilesFromTsConfig: false,
});

interface IfaceItem { kind: 'iface'; name: string; node: InterfaceDeclaration }
interface AliasItem { kind: 'alias'; name: string; node: TypeAliasDeclaration }
type Item = IfaceItem | AliasItem;

const items: Item[] = [];
// ts-morph returns POSIX-style paths even on Windows; normalize for the prefix check.
const SRC_DIR = resolve(PKG_ROOT, 'src').replace(/\\/g, '/');
for (const sf of project.getSourceFiles()) {
  const fp = sf.getFilePath().replace(/\\/g, '/');
  if (!fp.startsWith(SRC_DIR)) continue;
  for (const iface of sf.getInterfaces()) {
    if (iface.isExported()) items.push({ kind: 'iface', name: iface.getName(), node: iface });
  }
  for (const alias of sf.getTypeAliases()) {
    if (alias.isExported()) items.push({ kind: 'alias', name: alias.getName(), node: alias });
  }
}

if (items.length === 0) {
  process.stderr.write('codegen: no exported interfaces or type aliases found under src/.\n');
  process.exit(1);
}

// ─── Type mapping ─────────────────────────────────────────────
function fail(ctx: string, detail: string): never {
  process.stderr.write(`codegen: unsupported construct at ${ctx}: ${detail}\n`);
  process.exit(1);
}

function isStringLiteralText(t: string): boolean {
  return /^(['"]).*\1$/.test(t);
}

function normalizeStringLiteral(t: string): string {
  // 'foo' or "foo" → 'foo'
  const inner = t.slice(1, -1);
  return `'${inner}'`;
}

function mapPrimitive(text: string, ctx: string): string {
  switch (text) {
    case 'string':  return 'str';
    // 'number' maps to 'int' — fine for the slice (page numbers, order).
    // When a non-integer field appears (score, confidence, temperature, etc.)
    // either bump this to 'float' globally or split the mapping by field-name
    // hint. Drift detection won't catch the mistype on its own — caller types
    // will. Track when adding the first non-int field.
    case 'number':  return 'int';
    case 'boolean': return 'bool';
    case 'null':    return 'None';
  }
  if (isStringLiteralText(text)) return `Literal[${normalizeStringLiteral(text)}]`;
  // Bare identifier — assume it's a defined interface/alias (forward refs ok via __future__ annotations)
  if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(text)) return text;
  fail(ctx, `cannot map type "${text}"`);
}

function mapTypeNode(node: TypeNode, ctx: string): string {
  // Array: Foo[]
  if (node.getKind() === SyntaxKind.ArrayType) {
    const elemText = (node.asKindOrThrow(SyntaxKind.ArrayType)).getElementTypeNode().getText();
    return `list[${mapPrimitive(elemText, ctx)}]`;
  }
  // Array<Foo>
  if (node.getKind() === SyntaxKind.TypeReference) {
    const ref = node.asKindOrThrow(SyntaxKind.TypeReference);
    const name = ref.getTypeName().getText();
    if (name === 'Array') {
      const args = ref.getTypeArguments();
      if (args.length !== 1) fail(ctx, `Array<...> needs exactly 1 type arg`);
      const a = args[0];
      if (!a) fail(ctx, `Array<...> missing element type`);
      return `list[${mapPrimitive(a.getText(), ctx)}]`;
    }
    // Plain reference (Foo)
    return mapPrimitive(name, ctx);
  }
  // Union
  if (node.getKind() === SyntaxKind.UnionType) {
    return mapUnionTypeNode(node.asKindOrThrow(SyntaxKind.UnionType), ctx);
  }
  // LiteralType wrapper (e.g. 'foo' or null)
  if (node.getKind() === SyntaxKind.LiteralType) {
    const text = node.getText();
    if (text === 'null') return 'None';
    if (isStringLiteralText(text)) return `Literal[${normalizeStringLiteral(text)}]`;
    fail(ctx, `unsupported literal "${text}"`);
  }
  // Primitive keyword nodes (StringKeyword, NumberKeyword, etc.)
  const text = node.getText();
  return mapPrimitive(text, ctx);
}

function mapUnionTypeNode(union: UnionTypeNode, ctx: string): string {
  const parts = union.getTypeNodes();

  // Detect `T | null` → `T | None`
  const nonNull = parts.filter((p) => p.getText() !== 'null');
  const hasNull = nonNull.length !== parts.length;

  // All string literals → Literal['a', 'b', ...]
  if (nonNull.every((p) => isStringLiteralText(p.getText()))) {
    const lits = nonNull.map((p) => normalizeStringLiteral(p.getText())).join(', ');
    const py = `Literal[${lits}]`;
    return hasNull ? `${py} | None` : py;
  }

  // General union of refs / primitives
  const mapped = nonNull.map((p) => mapTypeNode(p, ctx));
  if (mapped.length === 0) fail(ctx, `empty union`);
  const py = mapped.length === 1 ? mapped[0]! : `Union[${mapped.join(', ')}]`;
  return hasNull ? `${py} | None` : py;
}

// ─── Emitters ─────────────────────────────────────────────────
function emitInterface(iface: InterfaceDeclaration): string {
  const name = iface.getName();
  const ctx = `interface ${name}`;
  const props: PropertySignature[] = iface.getProperties();
  const lines: string[] = [`class ${name}(BaseModel):`];
  if (props.length === 0) {
    lines.push('    pass');
    return lines.join('\n');
  }
  for (const prop of props) {
    const propName = prop.getName();
    const optional = prop.hasQuestionToken();
    const typeNode = prop.getTypeNode();
    if (!typeNode) fail(`${ctx}.${propName}`, 'missing type annotation');
    let py = mapTypeNode(typeNode, `${ctx}.${propName}`);
    if (optional && !py.endsWith(' | None')) py = `${py} | None`;
    const defaultVal = optional ? ' = None' : '';
    lines.push(`    ${propName}: ${py}${defaultVal}`);
  }
  return lines.join('\n');
}

function emitAlias(alias: TypeAliasDeclaration): string {
  const name = alias.getName();
  const typeNode = alias.getTypeNode();
  if (!typeNode) fail(`type ${name}`, 'missing body');
  const ctx = `type ${name}`;

  // Union of class references with `type:` literal discriminator → discriminated union
  if (typeNode.getKind() === SyntaxKind.UnionType) {
    const union = typeNode.asKindOrThrow(SyntaxKind.UnionType);
    const parts = union.getTypeNodes();
    // All references to declared interfaces?
    const allRefs = parts.every((p) => /^[A-Z][A-Za-z0-9_]*$/.test(p.getText()));
    if (allRefs && parts.length > 1) {
      const pipedRefs = parts.map((p) => p.getText()).join(' | ');
      return `${name} = Annotated[${pipedRefs}, Field(discriminator='type')]`;
    }
    // Otherwise fall through to plain union mapping (handles literal unions)
    return `${name} = ${mapUnionTypeNode(union, ctx)}`;
  }

  // Single reference: type UIBlock = CitedSummary;
  if (typeNode.getKind() === SyntaxKind.TypeReference) {
    return `${name} = ${typeNode.getText()}`;
  }

  // Primitive / literal alias
  return `${name} = ${mapTypeNode(typeNode, ctx)}`;
}

// ─── Topological order: ifaces first (sorted), then aliases (sorted) ──
const interfaces = items.filter((i): i is IfaceItem => i.kind === 'iface');
const aliases    = items.filter((i): i is AliasItem => i.kind === 'alias');
interfaces.sort((a, b) => a.name.localeCompare(b.name));
aliases.sort((a, b) => a.name.localeCompare(b.name));

const body: string[] = [];
// Classes first, then aliases. Class annotations are deferred to strings
// by `from __future__ import annotations`, so they can reference Literal
// aliases defined below. But module-level alias bindings (e.g.
// `UIBlock = CitedSummary`) are evaluated immediately, so the class
// they reference must already exist by that point.
for (const item of interfaces) {
  body.push(emitInterface(item.node));
  body.push('');
  body.push('');
}
for (const item of aliases) {
  body.push(emitAlias(item.node));
  body.push('');
}

// Build import header from what the body actually uses.
// (Avoids unused-import lint findings while keeping the generator honest.)
const bodyJoined = body.join('\n');
const typingNames: string[] = [];
if (bodyJoined.includes('Annotated[')) typingNames.push('Annotated');
if (bodyJoined.includes('Literal['))   typingNames.push('Literal');
if (bodyJoined.includes('Union['))     typingNames.push('Union');

const pydanticNames: string[] = ['BaseModel'];
if (bodyJoined.includes('Field('))     pydanticNames.push('Field');

const header: string[] = [
  '# DO NOT EDIT — generated by packages/schema/codegen/to_python.ts.',
  '# Regenerate with: pnpm --filter @arcana/schema codegen',
  '# Drift is caught by: pnpm --filter @arcana/schema codegen:check',
  '#',
  '# Sources: packages/schema/src/*.ts (UIBlock + payloads + api + entities).',
  '# Wire-contract invariant: R-10, NFR-MNT-02, NFR-SEC-04 (validate.py).',
  '',
  'from __future__ import annotations',
  '',
];
if (typingNames.length > 0) {
  header.push(`from typing import ${typingNames.join(', ')}`);
  header.push('');
}
header.push(`from pydantic import ${pydanticNames.join(', ')}`);
header.push('');
header.push('');

// Collapse excess blank lines, ensure single trailing newline.
let content = [...header, ...body].join('\n');
content = content.replace(/\n{4,}/g, '\n\n\n');
if (!content.endsWith('\n')) content += '\n';

// ─── Write or check ───────────────────────────────────────────
if (isCheck) {
  if (!existsSync(OUTPUT)) {
    process.stderr.write(`codegen:check FAILED — ${OUTPUT} does not exist.\n`);
    process.stderr.write('Run: pnpm --filter @arcana/schema codegen\n');
    process.exit(1);
  }
  const existing = readFileSync(OUTPUT, 'utf-8');
  if (existing !== content) {
    process.stderr.write(`codegen:check FAILED — ${OUTPUT} is out of sync with packages/schema/src/.\n`);
    process.stderr.write('Run: pnpm --filter @arcana/schema codegen\n');
    process.exit(1);
  }
  process.stdout.write('codegen:check OK\n');
} else {
  mkdirSync(dirname(OUTPUT), { recursive: true });
  writeFileSync(OUTPUT, content, 'utf-8');
  process.stdout.write(`codegen: wrote ${OUTPUT}\n`);
}
