const circle = () =>
  (length -
    strokeWidth * 2) /
  (size *
    scale);

const isDrag = (x: number) =>
  Math.abs(x - origin) *
    zoom >
  THRESHOLD;

export const pages = function* <
  E extends Env = Env,
  P extends string = '/',
>(
  app: App<E, P>,
) {
  yield app;
}
function after() {
  return 1
}
