// Conversion operators named with *, &, ::, <>, two spaces or one letter; and = default.
struct A {
  operator char*() {
    return 0;
  }
  operator T&() {
    return t;
  }
  operator std::string() {
    return s;
  }
  operator std::vector<int>() {
    return v;
  }
  operator unsigned  int() {
    return 1;
  }
  operator T() {
    return t;
  }
};
Foo::Foo()
    = default;
int f() {
  return 0;
}
