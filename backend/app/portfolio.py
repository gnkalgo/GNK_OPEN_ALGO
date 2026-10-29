"""Derived paper positions using weighted average cost, never broker holdings."""

from decimal import Decimal


def positions(orders, quotes):
    books = {}
    for order in orders:
        if order.status != "Filled":
            continue
        ticket = order.ticket
        key = (ticket["symbol"], ticket["exchange"], ticket["product"])
        book = books.setdefault(key, {"quantity": 0, "average": Decimal(0), "realized": Decimal(0)})
        delta = ticket["quantity"] * (1 if ticket["side"] == "BUY" else -1)
        price = Decimal(str(ticket["price"]))
        quantity = book["quantity"]
        if quantity == 0 or quantity * delta > 0:
            book["average"] = (abs(quantity) * book["average"] + abs(delta) * price) / abs(
                quantity + delta
            )
        else:
            closed = min(abs(quantity), abs(delta))
            book["realized"] += closed * (price - book["average"]) * (1 if quantity > 0 else -1)
            if abs(delta) > abs(quantity):
                book["average"] = price
            elif abs(delta) == abs(quantity):
                book["average"] = Decimal(0)
        book["quantity"] += delta
    result = []
    for (symbol, exchange, product), book in sorted(books.items()):
        mark = Decimal(str(quotes[symbol]))
        result.append(
            {
                "symbol": symbol,
                "exchange": exchange,
                "product": product,
                "quantity": book["quantity"],
                "average_price": str(book["average"]),
                "mark_price": str(mark),
                "market_value": str(mark * book["quantity"]),
                "realized_pnl": str(book["realized"]),
                "unrealized_pnl": str((mark - book["average"]) * book["quantity"]),
            }
        )
    return result
