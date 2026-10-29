import type { Order } from "./paper";

// Paper presentation only; authoritative live accounting must come from broker reconciliation.
export function ledger(orders: Order[], marks: {symbol: string; price: number}[]) {
  const books = new Map<string, {symbol: string; exchange: string; product: string; quantity: number; average: number; realized: number}>();
  // The adapter presents newest first. Reverse without sorting locale-formatted demo times.
  for (const order of [...orders].reverse()) {
    if (order.status !== "Filled") continue;
    const key = `${order.exchange}:${order.symbol}:${order.product}`;
    const book = books.get(key) ?? {symbol:order.symbol,exchange:order.exchange,product:order.product,quantity:0,average:0,realized:0};
    const delta = order.quantity * (order.side === "BUY" ? 1 : -1);
    if (book.quantity === 0 || book.quantity * delta > 0) {
      book.average = (Math.abs(book.quantity) * book.average + Math.abs(delta) * order.price) / Math.abs(book.quantity + delta);
    } else {
      book.realized += Math.min(Math.abs(book.quantity), Math.abs(delta)) * (order.price - book.average) * Math.sign(book.quantity);
      if (Math.abs(delta) > Math.abs(book.quantity)) book.average = order.price;
      else if (Math.abs(delta) === Math.abs(book.quantity)) book.average = 0;
    }
    book.quantity += delta;
    books.set(key, book);
  }
  return [...books.values()].map(book => {
    const mark = marks.find(item => item.symbol === book.symbol)?.price ?? book.average;
    return {...book, price:mark, netValue:book.average * book.quantity, pnl:(mark - book.average) * book.quantity};
  });
}
