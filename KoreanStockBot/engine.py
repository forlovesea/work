"""Single-symbol, daily-bar paper trading. No broker orders are sent."""
import csv
import math
import random
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from pathlib import Path


@dataclass
class Config:
    capital: float = 30000
    allocation: float = 0.30
    fast: int = 5
    slow: int = 20
    stop_loss: float = 0.03
    take_profit: float = 0.06
    max_drawdown: float = 0.10
    fee: float = 0.00015
    sell_tax: float = 0.002
    slippage: float = 0.001

    def validate(self):
        for name, value in asdict(self).items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"잘못된 설정: {name}")
        if self.capital <= 0 or not 0 < self.allocation <= 1:
            raise ValueError("원금은 양수, 투자비중은 0~1 사이여야 합니다.")
        if not 1 <= self.fast < self.slow or int(self.slow) != self.slow or int(self.fast) != self.fast:
            raise ValueError("이동평균 기간은 정수이며 단기 < 장기여야 합니다.")
        for key in ('stop_loss', 'take_profit', 'max_drawdown', 'fee', 'sell_tax', 'slippage'):
            if not 0 <= getattr(self, key) < 1:
                raise ValueError(f"{key} 값은 0 이상 1 미만이어야 합니다.")
        if self.fee + self.sell_tax >= 1:
            raise ValueError("거래비용이 너무 큽니다.")


@dataclass
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


def read_bars(path):
    bars = []
    with open(path, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not set(Bar.__annotations__).issubset(reader.fieldnames or []):
            raise ValueError('CSV 열: date,open,high,low,close,volume')
        for row in reader:
            day = date.fromisoformat(row['date']).isoformat()
            b = Bar(day, **{k: float(row[k]) for k in ('open', 'high', 'low', 'close', 'volume')})
            values = (b.open, b.high, b.low, b.close, b.volume)
            if not all(math.isfinite(v) for v in values) or min(values[:4]) <= 0 or b.volume < 0:
                raise ValueError(f'{day}: 가격/거래량 오류')
            if b.low > min(b.open, b.close) or b.high < max(b.open, b.close) or b.low > b.high:
                raise ValueError(f'{day}: OHLC 범위 오류')
            if bars and day <= bars[-1].date:
                raise ValueError('날짜는 중복 없이 오름차순이어야 합니다.')
            bars.append(b)
    if not bars:
        raise ValueError('CSV가 비어 있습니다.')
    return bars


def demo_bars():
    rng = random.Random(7)
    bars, day, price = [], date(2025, 1, 2), 3000.0
    while len(bars) < 252:
        if day.weekday() < 5:
            op = price * (1 + rng.uniform(-0.015, 0.015))
            price = op * (1 + 0.005 * math.sin(len(bars) / 12) + rng.uniform(-0.022, 0.022))
            bars.append(Bar(day.isoformat(), op, max(op, price)*1.01, min(op, price)*0.99, price, 100000))
        day += timedelta(days=1)
    return bars


class PaperEngine:
    def __init__(self, config=None):
        self.cfg = config or Config()
        self.cfg.validate()
        self.cash = self.cfg.capital
        self.qty = 0
        self.entry = 0
        self.peak = self.cash
        self.halted = False
        self.pending = None
        self.closes = []
        self.trades = []
        self.equity = []

    def sell(self, bar, reason):
        price = bar.open * (1-self.cfg.slippage)
        proceeds = price*self.qty*(1-self.cfg.fee-self.cfg.sell_tax)
        self.cash += proceeds
        self.trades.append(dict(date=bar.date, side='SELL', quantity=self.qty, price=price, cash=self.cash, reason=reason))
        self.qty = 0

    def step(self, bar):
        if self.equity and bar.date <= self.equity[-1]['date']:
            raise ValueError('이미 처리한 날짜 또는 역순 데이터입니다.')
        c = self.cfg
        # A signal from yesterday's close is filled at today's open only.
        if bar.volume > 0:
            if self.pending and self.pending != 'BUY' and self.qty:
                self.sell(bar, self.pending)
            elif self.pending == 'BUY' and not self.qty and not self.halted:
                price = bar.open*(1+c.slippage)
                quantity = int(min(self.cash, self.cash*c.allocation)/(price*(1+c.fee)))
                if quantity:
                    self.cash -= quantity*price*(1+c.fee)
                    self.qty, self.entry = quantity, price
                    self.trades.append(dict(date=bar.date, side='BUY', quantity=quantity, price=price, cash=self.cash, reason='추세 진입'))
            self.pending = None
        value = self.cash + self.qty*bar.close
        self.peak = max(self.peak, value)
        drawdown = 1-value/self.peak
        if drawdown >= c.max_drawdown:
            self.halted = True
        self.closes.append(bar.close)
        if self.halted:
            self.pending = '최대 낙폭 중단' if self.qty else None
        elif self.qty and bar.close <= self.entry*(1-c.stop_loss):
            self.pending = '손절 신호'
        elif self.qty and bar.close >= self.entry*(1+c.take_profit):
            self.pending = '익절 신호'
        elif len(self.closes) >= c.slow:
            fast = sum(self.closes[-c.fast:])/c.fast
            slow = sum(self.closes[-c.slow:])/c.slow
            if fast > slow and not self.qty:
                self.pending = 'BUY'
            elif fast < slow and self.qty:
                self.pending = '추세 이탈'
        self.equity.append(dict(date=bar.date, equity=value, cash=self.cash, quantity=self.qty, drawdown=drawdown))
        return self.equity[-1]

    def report(self):
        final = self.equity[-1]['equity'] if self.equity else self.cash
        periods = {}
        previous = self.cfg.capital
        for row in self.equity:
            d = date.fromisoformat(row['date'])
            iso = d.isocalendar()
            for kind, key in [('day', d.isoformat()), ('week', f'{iso.year}-W{iso.week:02}'), ('month', d.strftime('%Y-%m'))]:
                bucket = periods.setdefault((kind, key), [previous, row['equity']])
                bucket[1] = row['equity']
            previous = row['equity']
        return dict(initial=self.cfg.capital, final=final, return_pct=(final/self.cfg.capital-1)*100,
                    max_drawdown_pct=max((r['drawdown'] for r in self.equity), default=0)*100,
                    trades=len(self.trades), open_quantity=self.qty, halted=self.halted,
                    periods=[dict(period=k[0], date=k[1], return_pct=(v[1]/v[0]-1)*100) for k,v in periods.items()])

    def export(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        for name, rows in [('trades', self.trades), ('equity', self.equity), ('periods', self.report()['periods'])]:
            with (directory / f'{name}.csv').open('w', encoding='utf-8-sig', newline='') as f:
                if rows:
                    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
