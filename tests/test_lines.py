"""What each code line does: measure.py's line kinds, which tell a line that declares something from one of logic,
and the heatmap's mark on a file nearly all of whose lines declare things, with its logic by line."""

import json
import os
import unittest

try:
    from . import support
except ImportError:
    import support

# Per shape, a file and its logic lines, as the output writes them; None where nothing is said of its lines.
SHAPES = [
    # A route group's closure holds only more routes, and a branch picks one: the branch's line is logic. An
    # inline handler is; a closure or an arrow function that only names a view isn't.
    ("routes/web.php", "<?php\nRoute::prefix('admin')->middleware('auth')->group(function () {\n"
     "    Route::get('users', [UserController::class, 'index']);\n    if (config('app.beta')) {\n"
     "        Route::get('beta', BetaController::class);\n    }\n});\nRoute::get('up', function () {\n"
     "    return response()->json(['status' => 'ok']);\n});\n"
     "Route::get('/', function () { return view('welcome'); });\nRoute::get('home', fn () => view('home'));\n",
     "4, 9-10"),
    # A long array property and a short method: the method's body.
    ("app/Rules/Domains.php", "<?php\nclass Domains implements Rule\n{\n    protected $domains = [\n"
     + "        'a.com',\n" * 30 + "    ];\n\n    public function passes($attribute, $value)\n    {\n"
     "        return in_array(substr($value, 1), $this->domains);\n    }\n}\n", "38-40"),
    # Routes, each with its handler written inline: mostly logic, however short one is.
    ("server/routes/api/documents.ts", 'router.post("documents.list", auth(), async (ctx) => {\n'
     "  const { sort } = ctx.input.body;\n  ctx.body = { data: await Document.findAll({ order: sort }) };\n});\n"
     'router.get("/up", (req, res) => res.send("ok"));\n', "2-5"),
    # A spec's describe and it hold calls of other names than their own, and assertions: logic.
    ("cart.spec.js", 'describe("cart", () => {\n  it("adds", () => {\n    expect(add(1, 2)).toBe(3);\n  });\n});\n',
     "2-5"),
    # Types, a function type's arrow and lazy imports declare; a function with a body is logic.
    ("src/router.ts", 'import type { RouteRecordRaw } from "vue-router";\nexport interface Props {\n'
     "  onChange: (value: string) => void;\n}\nexport type Handler = (e: Event) => void;\n"
     "export const routes: RouteRecordRaw[] = [\n"
     '  { path: "/", component: () => import("./Home.vue") },\n'
     '  { path: "/about", component: () => import("./About.vue"), meta: { auth: true } },\n];\n'
     'export const isAdmin = (user) => user.role === "admin";\n', "10"),
    # An app made, configured by calls on it and exported: no statement reads what another worked out.
    ("app.js", "const express = require('express');\nconst app = express();\napp.use(express.json());\n"
     "app.get('/x', handlers.x);\nmodule.exports = app;\n", ""),
    # A group whose closure is handed the router by the router's name, and registers on it.
    ("src/routes.js", "router.group((router) => {\n  router.get('/a', A.index);\n  router.post('/a', A.store);\n});\n",
     ""),
    # Go's struct and composite literal declare; a list registered inside a function is that function's body.
    ("routes.go", "package routes\n\ntype Route struct {\n\tPath string\n}\n\nvar all = []Route{\n\t{Path: \"/\"},\n}\n"
     "\nfunc Mount(r chi.Router) {\n\tr.Route(\"/admin\", func(r chi.Router) {\n\t\tr.Get(\"/users\", users)\n"
     "\t})\n}\n", "12-15"),
    ("src/lib.rs", "pub struct Point {\n    x: i32,\n}\n\nimpl Point {\n    pub fn norm(&self) -> i32 {\n"
     "        self.x.abs()\n    }\n}\n", "7-8"),
    # Ruby's routes and a schema's columns, in blocks that go on with their call's list; a spec's block isn't.
    ("config/routes.rb", 'Rails.application.routes.draw do\n  namespace :admin do\n'
     '    resources :users, only: [:index]\n  end\n  if ENV["BETA"]\n    get "beta", to: "beta#index"\n  end\nend\n',
     "5"),
    ("db/schema.rb", 'ActiveRecord::Schema[7.1].define(version: 1) do\n  create_table "users" do |t|\n'
     '    t.string "email", null: false\n  end\nend\n', ""),
    ("spec/user_spec.rb", 'describe User do\n  it "is valid" do\n    user = build(:user)\n'
     "    expect(user).to be_valid\n  end\nend\n", "3-4"),
    ("settings.py", 'DEBUG = False\nAPPS = [\n    "admin",\n]\nif DEBUG:\n    APPS += ["toolbar"]\n\n\n'
     'class Config:\n    name = "app"\n\n    def ready(self):\n        load()\n', "5, 12-13"),
    # Markup, a language this doesn't read for its lines, and brackets that don't match: nothing said.
    ("resources/views/index.blade.php", "@if ($x)\n<p>{{ $x }}</p>\n@endif\n", None),
    ("App.java", "class App {}\n", None),
    ("broken.ts", "export const x = {\n  a: 1,\n", None),
]


# A named function's lines after its first are logic, however its signature is written: over several lines, with
# a where clause, or with a return type that's an object's or ends in ]>; and a Go method that returns a field.
FUNCTIONS = [
    ("src/cmd.rs", "impl Cmd {\n    pub async fn run(\n        self,\n        db: Sqlite,\n    ) -> Result<()> {\n"
     "        let q = self.q;\n        db.save(q).await?;\n        Ok(())\n    }\n}\n", "3-9"),
    ("src/run.rs", "fn run<T>(db: T) -> Vec<T>\nwhere\n    T: Clone,\n{\n    let q = 1;\n    vec![db]\n}\n", "2-7"),
    ("src/pos.ts", "function pos(e: Ev): { x: number; y: number } {\n  const r = e.target.rect();\n"
     "  return { x: r.x, y: r.y };\n}\n", "2-4"),
    ("src/rows.ts", "export async function rows(\n  ids: string[],\n): Promise<{ id: string }[]> {\n"
     "  const found = await load(ids);\n  return found;\n}\n", "2-6"),
    ("src/ops.ts", "export class Client {\n  batch(\n    input: Input<'batch'>,\n  ): Promise<Output<'batch'>> {\n"
     "    return this.execute('batch', input);\n  }\n}\n", "3-6"),
    ("do.go", "package a\n\nfunc (s *S) Do(\n\ta int,\n) (int, error) {\n\tx := s.load(a)\n\treturn x, nil\n}\n\n"
     "func (p *Provider) Config() any {\n\treturn p.config\n}\n", "4-8, 11-12"),
]

# Closures passed to a call that run code on what they're handed, or on another receiver: a handler, a callback,
# a transaction, jQuery's ready, Ruby's each and define_method, and Ruby's brace blocks, a proc's and a lambda's.
CALLBACKS = [
    ("server.js", "app.get('/health', (req, res) => {\n  res.set('Cache-Control', 'no-store');\n  res.status(200);\n"
     "  res.send('ok');\n});\napp.get('/x', handlers.x);\n", "2-5"),
    ("purge.php", "<?php\n$users->each(function ($user) {\n    $user->notify(new Expired());\n"
     "    $user->delete();\n});\nDB::transaction(function () {\n    DB::table('users')->where('old', 1)->delete();\n"
     "    DB::table('logs')->insert(['what' => 'purged']);\n});\n", "3-5, 7-9"),
    ("each.ts", "items.forEach((item) => {\n  item.save();\n  item.publish();\n});\nfetchAll().then((conn) => {\n"
     "  conn.flush();\n  conn.close();\n});\n", "2-4, 6-8"),
    ("ready.js", "$(document).ready(function () {\n  $('#save').hide();\n  $('.menu').show();\n});\n", "2-4"),
    ("deactivate.rb", "users.each do |u|\n  u.deactivate!\n  u.notify\nend\nclass A\n  define_method(:go) do |y|\n"
     "    y.save\n    y.notify\n  end\nend\n", "2-3, 7-8"),
    # A handler whose body is all in a loop or a branch: the statements under it are read too.
    ("dns.js", "server.on('request', (request, send) => {\n  for (const q of request.questions) {\n"
     "    console.log(q.name);\n    send(answer(q));\n  }\n});\n", "2-6"),
    ("lib/tasks/purge.rb", 'namespace :admin do\n  if ENV["PURGE"]\n    User.delete_all\n  end\nend\n', "2-4"),
    ("config/routes.rb", "Rails.application.routes.draw do\n  resources :users\n"
     "  get '/up', to: proc { [200, {}, ['ok']] }\n  constraints(lambda { |req| req.env['warden'].user&.admin? }) do\n"
     "    mount Sidekiq::Web => '/sidekiq'\n  end\nend\n", "3-4"),
]

# Scripts: statements at the top level that run, an await, or a value worked out from one statement read by the
# next, in a branch's block too, are logic; a call on what an earlier one made, or a literal named, isn't.
SCRIPTS = [
    ("total.php", "<?php\n$pdo = new PDO($dsn);\n$rows = $pdo->query('select * from t')->fetchAll();\n"
     "$total = array_sum(array_column($rows, 'amount'));\n$pdo->exec(\"update s set total = $total\");\n"
     "mail($to, 'done', \"total $total\");\n", "3-4"),
    ("log.mjs", "const db = await connect(url);\nconst rows = await db.query('select 1');\n"
     "await db.insert('log', { n: rows.length });\nawait db.close();\nconsole.log('done');\n", "1-4"),
    ("fixture.mjs", "const root = path.join(__dirname, '..');\ntry {\n  const db = open(path.join(root, 'kuma.db'));\n"
     "  db.exec('VACUUM');\n} finally {\n  fs.rmSync(root, { recursive: true });\n}\n", "2-3, 5-6"),
    ("run.py", "import os\ndata = load(os.environ['F'])\nresult = [transform(x) for x in data if x.ok]\nwrite(result)\n"
     "A = 1\nB = 2\n", "3-4"),
    # A loop's variable is worked out too, so its body reads it; a branch's block is read as the top's, after
    # <?php or a statement with no semicolon as well. A PHP file that's a template, its HTML outside <?php ?>,
    # is markup: nothing is said of it.
    ("sum.py", 'import json\nrows = json.load(open("data.json"))\ntotal = 0\nfor row in rows:\n'
     '    total += row["amount"]\n    print(row["name"])\nprint(total)\n', "4-7"),
    ("routes/resources.php", "<?php\nforeach (['users', 'posts'] as $name) {\n"
     "    Route::resource($name, ResourceController::class);\n}\n", "2-3"),
    ("vite.config.js", "import a from 'a'\nconst plugins = [a()]\nif (process.env.ANALYZE) {\n"
     "  plugins.push(analyzer())\n}\nexport default { plugins }\n", "3"),
    ("single.php", "<?php get_header(); ?>\n<main>\n  <?php the_title(); ?>\n</main>\n<?php get_footer(); ?>\n",
     None),
    # A value got from a call on what the file made is worked out, so the statement reading it runs.
    ("cli.py", 'import argparse\nparser = argparse.ArgumentParser()\nparser.add_argument("--n")\n'
     "args = parser.parse_args()\nrun(args.n)\n", "5"),
]

# A closure that returns a string or another literal serves a value, as a stub's handler does: it names nothing.
LITERALS = [
    ("routes/admin.php", "<?php\nRoute::get('/a', function () {\n    return 'stubbed admin.invoices.index';\n});\n"
     "Route::get('/', fn () => view('home'));\n", "3-4"),
    ("src/titles.js", "export const titles = {\n  home: () => 'Home',\n  about: AboutTitle,\n};\n", "2"),
    ("spec/factories.rb", 'FactoryBot.define do\n  factory :user do\n    name { "John" }\n    admin { false }\n'
     "  end\nend\n", "3-4"),
]


def logic_of(shapes):
    """Each shape's path and its logic lines, as the output writes them; None where nothing is said of them."""
    measure = support.load("measure")
    return [(path, None if kinds is None else measure.logic_lines(kinds))
            for path, kinds in ((path, measure.line_kinds(path, text)) for path, text, _ in shapes)]


class Shapes(unittest.TestCase):

    def test_each_shape(self):
        measure = support.load("measure")
        for path, text, logic in SHAPES:
            with self.subTest(path=path):
                kinds = measure.line_kinds(path, text)
                self.assertEqual(None if kinds is None else measure.logic_lines(kinds), logic)

    def test_a_named_functions_lines(self):
        self.assertEqual(logic_of(FUNCTIONS), [(path, logic) for path, _, logic in FUNCTIONS])

    def test_a_callbacks_lines(self):
        self.assertEqual(logic_of(CALLBACKS), [(path, logic) for path, _, logic in CALLBACKS])

    def test_a_scripts_lines(self):
        self.assertEqual(logic_of(SCRIPTS), [(path, logic) for path, _, logic in SCRIPTS])

    def test_a_literals_lines(self):
        self.assertEqual(logic_of(LITERALS), [(path, logic) for path, _, logic in LITERALS])

    @unittest.expectedFailure
    def test_a_docstring_is_no_code_line(self):
        """Python's docstrings are left out of the code lines, as measure.py's counts leave them out."""
        kinds = support.load("measure").line_kinds("models.py", '"""Models."""\nimport os\n\n\nclass A:\n'
                                                   '    """A, over\n    two lines."""\n\n    name = "a"\n')
        self.assertEqual(kinds, [None, "declaration", None, None, "declaration", None, None, None, "declaration", None])

    def test_a_found_functions_lines_are_logic(self):
        """Every code line of a function measure.functions finds, after its first, is logic: over the samples of
        its tests, in every language whose lines are read."""
        measure = support.load("measure")
        folder, declared = os.path.join(support.SAMPLES, "functions"), []
        for name in sorted(os.listdir(folder)):
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                text = f.read()
            kinds = measure.line_kinds(name, text)
            if kinds is not None:
                declared += ["%s:%d" % (name, k + 1) for _, first, last, _, _ in measure.functions(name, text)[1]
                             for k in range(first, last) if kinds[k] == "declaration"]
        self.assertEqual(declared, [])


class Marked(unittest.TestCase):
    """The heatmap marks a file of its table nearly all of whose code lines declare things, and lists its logic by
    line; the page carries it, and measure.py --show says it."""

    @classmethod
    def setUpClass(cls):
        repo = cls.repo = support.Repo("declarations")
        for day in range(1, 4):
            routes = "".join("Route::get('r%d', C%d::class);\n" % (n, n) for n in range(day * 10))
            repo.commit("2026-01-%02d" % day, "Add routes", {
                "routes/web.php": "<?php\n" + routes + "Route::get('up', function () {\n    return now();\n});\n",
                "app/Cart.php": "<?php\nclass Cart\n{\n    public function total($items)\n    {\n        $sum = %d;\n"
                                "        foreach ($items as $item) {\n            $sum += $item;\n        }\n"
                                "        return $sum;\n    }\n}\n" % day})
        repo.done()

    def test_the_mark_and_the_logic_by_line(self):
        out = support.run("heatmap.py", "-C", self.repo.path).out
        self.assertIn("  routes/web.php  [declarations]\n", out)
        self.assertNotIn("app/Cart.php  [", out)
        self.assertIn("\n  routes/web.php: 33-34\n", out)
        self.assertEqual(set(support.heatmap_rows(out)), {"routes/web.php", "app/Cart.php"})
        shown = support.run("measure.py", "-C", self.repo.path, "--show", "routes/web.php", "--show", "app/Cart.php")
        self.assertIn("Declarations: all but 6% of its code lines; its logic, by line: 33-34.\n", shown.out)
        self.assertIn("Logic: 58% of its code lines, in a function's or a closure's body, on a branch's line or in a "
                      "statement at the top that runs.\n", shown.out)

    def test_the_page_carries_it(self):
        page = os.path.join(support.new_folder("declarations"), "p.html")
        support.run("heatmap.py", "-C", self.repo.path, "--page", page)
        with open(page, encoding="utf-8") as f:
            text = f.read()
        files = dict((f["path"], f) for f in json.loads(support.block(text, "heatmap"))["files"])
        self.assertEqual((files["routes/web.php"].get("declarations"), "declarations" in files["app/Cart.php"]),
                         ("33-34", False))
        check_page = support.load("check_page")
        self.assertEqual(check_page.check(text)[0], [])
        heat = json.loads(support.block(text, "heatmap"))
        heat["files"][0]["declarations"] = "lines 3 to 4"
        errors = check_page.check(support.page_with(heatmap=heat, template=page))[0]
        self.assertIn("The heatmap's row for routes/web.php: its declarations should be its logic lines, as 23-31, 88, "
                      "or empty.", errors)


if __name__ == "__main__":
    unittest.main()
