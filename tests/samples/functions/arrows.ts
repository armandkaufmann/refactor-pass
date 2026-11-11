export const useOrders = async (
  shopId: string,
  options: { limit?: number } = {},
): Promise<Order[]> => {
  return fetchOrders(shopId, options);
};

const toRow = (order: Order) => ({
  id: order.id,
  total: order.total,
});

const total = (orders: Order[]) =>
  orders.reduce((sum, order) => sum + order.total, 0) +
  shipping(orders);

export const handler: Handler<Event, Result> = async (event) => {
  return { statusCode: 200, body: JSON.stringify(event) };
};

const format: (value: number) => string = (value) =>
  value.toFixed(2);

// Not a function: a typed declaration with no value.
let pending: Array<() => void>;
const compare = (a: number, b: number): number => a - b;
