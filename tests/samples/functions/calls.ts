// Not functions: calls split over lines, with and without semicolons.
foo(
  a,
  b
);
foo(
  a,
  b
)
bar()
describe('x', () => {
  it('y', async () => {
    expect(
      a
    ).toBe(1);
  });
});
// Not functions: control statements split over lines.
if (
  a &&
  b
) {
  x();
}
while (
  x
) {
  y();
}
for (
  let i = 0;
  i < n;
  i++
) {
  z();
}
switch (
  x
) {
  case 1:
    break;
}
const total = (
  a + b
) * 2;
try {
  a();
}
catch (e) {
  b();
}
const re = /[{(]/g;
const half = total / 2 / 3;
// Not functions: members typed as functions in a type and an interface.
type T = {
  onError: (e: Error) => void;
};
interface I {
  run(a: string): void;
  stop: () => void;
}
// Functions: a named function wrapped in a call, an object literal's methods, a class's methods.
const fn = useCallback(function handle() {
  return 1;
}, []);
const obj = {
  run(a) {
    return a;
  },
  stop: () => {
    return 1;
  },
  label: cond
    ? 'a'
    : 'b',
};
class K {
  catch(e: unknown) {
    return e;
  }
  get value(): { a: string } {
    return { a: '' };
  }
  handle = async <T,>(x: T): Promise<T> => {
    return x;
  };
}
