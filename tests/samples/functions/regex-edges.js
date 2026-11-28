// Spaces after *; regular expressions with \/, / or \] in a class, [] and classes at one column.
const o = {
  * gen () {
    yield 1
  },
}
function g() {
  return 1
}
class A {
  * return() {
    yield 1
  }
}
function g() {
  return 1
}
const c = memo(function * Card(p) {
  return p
})
function g() {
  return 1
}
function f(s) {
  return s.replace(/\/"/g, '')
}
function g() {
  return 1
}
function f(s) {
  return s.split(/[/"]/)
}
function g() {
  return 1
}
function f(s) {
  return s.split(/[\]"]/)
}
function g() {
  return 1
}
function f(s) {
  if (/[]"/.test(s)) { y() }
  return 1
}
function g() {
  return 1
}
function f(s) {
  if (/a//2) { y() }
  return 1
}
function g() {
  return 1
}
function f(s) {
  a = /[a]bcdef/
  b = /[}]/; g({})
  return 1
}
function g() {
  return 1
}
function f(x) {
  t = `${(x.return   / 2) + {a: 1 / 2}.a}`
  return t
}
function g() {
  return 1
}
function f(x) {
  t = `${(x.return    / 2) + {a: 1 / 2}.a}`
  return t
}
function g() {
  return 1
}
