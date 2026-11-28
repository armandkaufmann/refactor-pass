// Spaces after a name's ! and ?.
handler! = function () {
  return 1
}
function g() {
  return 1
}
class A {
  static handler? :
    (a: number) => void = (a) => {
    return
  }
}
function g() {
  return 1
}
