from typing import Set, Tuple

ExchangeId = str
SymbolId = str

# exchange, symbol pair
Ticker = Tuple[ExchangeId, SymbolId]

SymbolSet = Set[SymbolId]
TickerSet = Set[Ticker]