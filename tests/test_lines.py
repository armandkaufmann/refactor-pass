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
        self.assertIn("Logic: 58% of its code lines, in a function's or a closure's body or on a branch's line.\n",
                      shown.out)

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
