const pick = <T extends Item>(
  items: readonly T[],
) =>
  items.filter((item) => item.ok) as Array<
    T extends Shape ? Shape : never
  >;
const isLate = (due: number) =>
  Date.now()
    > due;
const after = () => 1
