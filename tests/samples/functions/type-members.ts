export type Instance<
  P = {},
  E = {},
> = {
  $props: P
  $forceUpdate: () => void
  $emit: (event: string) => void
}
export type Context<E> = E extends any
  ? {
      expose: <T extends object>(
        exposed?: T,
      ) => void
    }
  : never
export type Emits<E> =
  E extends Record<string, any[]>
    ? {
        [K in keyof E]: (...args: E[K]) => any
      }
    : false
export type Router<TType> = TType extends 'query'
  ? {
      query: Resolver;
      revalidate: (
        input?: string,
      ) => Promise<
        { revalidated: false } | { revalidated: true }
      >;
    }
  : never
declare function valueToPoint(
  value: number,
): Point
function after() {
  return 1
}
