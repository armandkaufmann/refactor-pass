// The functions TypeScript's own parser finds in a repo's JavaScript and TypeScript, as JSON: {path: [[name,
// first line, last line], ...]}. Functions, methods, accessors, constructors, functions assigned to a name or a
// member, anonymous default exports, and variables, keys and properties given an arrow or a function.
// Usage: node ts_truth.js TYPESCRIPT_JS REPO FOLDER...
const ts = require(process.argv[2]); const fs = require("fs"); const path = require("path");
const repo = process.argv[3]; const subs = process.argv.slice(4); const out = {};
function walk(dir) { for (const e of fs.readdirSync(dir, {withFileTypes: true})) { const p = path.join(dir, e.name);
  if (e.isDirectory()) { if (!["node_modules", ".git", "dist"].includes(e.name)) walk(p); }
  else if (/\.(ts|tsx|js|jsx|mjs|cjs)$/.test(e.name) && !/\.d\.ts$/.test(e.name)) one(p); } }
function one(p) { const text = fs.readFileSync(p, "utf8"); const sf = ts.createSourceFile(p, text, ts.ScriptTarget.Latest, true, /\.(tsx|jsx)$/.test(p) ? ts.ScriptKind.TSX : undefined);
  const rows = []; const line = pos => sf.getLineAndCharacterOfPosition(pos).line + 1;
  const add = (nameNode, fn, kind) => { if (!fn.body) return; rows.push([nameNode ? nameNode.getText(sf) : kind, line(nameNode ? nameNode.getStart(sf) : fn.getStart(sf)), line(fn.getEnd() - 1)]); };
  (function visit(n) {
    if (ts.isFunctionDeclaration(n)) add(n.name, n, "function");
    else if (ts.isMethodDeclaration(n) || ts.isGetAccessor(n) || ts.isSetAccessor(n)) add(n.name, n, "method");
    else if (ts.isConstructorDeclaration(n)) { if (n.body) rows.push(["constructor", line(n.getStart(sf, false) ), line(n.getEnd() - 1)]); }
    else if (ts.isBinaryExpression(n) && n.operatorToken.kind === ts.SyntaxKind.EqualsToken && (ts.isArrowFunction(n.right) || ts.isFunctionExpression(n.right)) && (ts.isIdentifier(n.left) || ts.isPropertyAccessExpression(n.left)) && ts.isExpressionStatement(n.parent)) { if (n.right.body) rows.push([n.left.getText(sf), line(n.left.getStart(sf)), line(n.right.getEnd() - 1)]); }
    else if (ts.isExportAssignment(n) && (ts.isArrowFunction(n.expression) || ts.isFunctionExpression(n.expression))) { rows.push(["default", line(n.getStart(sf)), line(n.expression.getEnd() - 1)]); }
    else if ((ts.isVariableDeclaration(n) || ts.isPropertyAssignment(n) || ts.isPropertyDeclaration(n)) && n.initializer && (ts.isArrowFunction(n.initializer) || ts.isFunctionExpression(n.initializer))) add(n.name, n.initializer, "var");
    ts.forEachChild(n, visit); })(sf);
  out[path.relative(repo, p)] = rows; }
for (const s of subs) walk(path.join(repo, s));
process.stdout.write(JSON.stringify(out));
