"""One managed position selected from a common-date, net-assets-ranked ETF universe."""
from decimal import Decimal
from live import LiveBot, ROOT, SafetyStop, dec, stamp
from etf_research import ResearchBook, number
from etf_scope import read_scope,read_symbols


class EtfBot(LiveBot):
    def __init__(self,*args,research=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.symbol=(self.s or {}).get('managed_symbol','')
        self.research=research or ResearchBook(ROOT/self.c['research_file'])
        self.latest=None
        self.previous_day=None
        self.scope_path=self.store.path.parent/'etf_scope.json'

    def initialize(self):
        super().initialize()
        if self.s['quantity'] and not self.symbol:
            raise SafetyStop('Managed ETF identity missing')

    def check_stock(self,stock):
        detail=stock.get('koreanMarketDetail')
        if (stock['currency']!='KRW' or stock['market'] not in ('KOSPI','KOSDAQ') or
                stock['securityType']!='ETF' or stock['status']!='ACTIVE' or
                dec(stock.get('leverageFactor'))!=1 or not detail or
                detail['liquidationTrading'] or detail['krxTradingSuspended']):
            raise SafetyStop('Only active unleveraged domestic ETFs can trade')

    def cost_buffer(self):
        # Conservative configurable liquidation reserve, not a statutory tax rate.
        return dec(self.c['liquidation_cost_buffer'])

    def profit_reached(self,last,bid,entry,fee):
        return bid*(1-fee-self.cost_buffer())>=entry*(1+dec(self.c['take_profit']))

    def research_gate(self,previous_day):
        try:
            book=self.research.load(self.clock(),previous_day)
            self.latest=book
            row=book['assessments'].get(self.symbol)
            universe_row=next((r for r in book['universe'] if r['symbol']==self.symbol),None)
            if row and universe_row:
                return dict(row,allow_buy=row['allow_buy'] and universe_row['tradable'])
            return {'allow_buy':False,'exit':False,'reasons':['NOT_IN_CURRENT_TOP20']}
        except (OSError,ValueError,KeyError,TypeError,SafetyStop):
            return {'allow_buy':False,'exit':False,'reasons':['RESEARCH_MISSING_OR_STALE']}

    def select(self,previous_day,preview=False):
        self.selection_details={'checked_at':self.clock().isoformat(),'rows':[],'complete':False}
        book=self.research.load(self.clock(),previous_day)
        self.latest=book
        power=dec(self.b.get('buying-power',{'currency':'KRW'},account=True)['cashBuyingPower'])
        budget=min(dec(self.s['cash']),dec(self.c['max_order_won']),dec(self.s['cash'])*dec(self.c['allocation']),power)
        details=self.selection_details
        low,high=read_scope(self.scope_path,self.binding)
        approved=read_symbols(self.scope_path,self.binding)
        details.update(min_rank=low,max_rank=high)
        details.update(cash=str(self.s['cash']),power=str(power),allocation=str(self.c['allocation']),
            cap=str(self.c['max_order_won']),budget=str(budget),as_of=book.get('as_of',previous_day),
            generated_at=book.get('generated_at'),fast=self.c['fast'],slow=self.c['slow'])
        by_symbol={}
        for row in book['universe']:
            assessment=book['assessments'][row['symbol']]
            item=dict(symbol=row['symbol'],name=row['name'],rank=row['rank'],score=assessment['score'],coverage=assessment['coverage'],
                      news_count=assessment.get('news',{}).get('count'),reasons=list(assessment['reasons']),state='NOT_CHECKED')
            if not row['tradable']:item['state']='STRUCTURE'
            elif not assessment['allow_buy']:item['state']='RESEARCH'
            details['rows'].append(item); by_symbol[row['symbol']]=item
        candidates=[r for r in book['universe'] if r['tradable'] and book['assessments'][r['symbol']]['allow_buy']]
        candidates.sort(key=lambda r:(-number(book['assessments'][r['symbol']]['score']),r['rank']))
        if not candidates:
            details['complete']=True
            return None
        quotes=self.b.get('prices',{'symbols':','.join(r['symbol'] for r in candidates)})
        valid_quotes={}
        stale_quotes=set()
        for q in quotes:
            try: self.fresh(q['timestamp'])
            except SafetyStop:
                try:
                    if (self.clock()-stamp(q['timestamp'])).total_seconds()>self.c['max_quote_age_seconds']:stale_quotes.add(q['symbol'])
                except (SafetyStop,ValueError,TypeError):pass
                continue
            valid_quotes[q['symbol']]=q
        quotes=valid_quotes
        # Price all research-qualified candidates so the UI can compare alternative scopes.
        for row in candidates:
            item=by_symbol[row['symbol']]
            quote=quotes.get(row['symbol'])
            if not quote or quote['currency']!='KRW':
                item['state']='QUOTE_STALE' if row['symbol'] in stale_quotes else 'QUOTE_UNAVAILABLE';continue
            required=dec(quote['lastPrice'])*Decimal('1.01')+10
            item.update(price=str(quote['lastPrice']),required=str(required),shortfall=str(max(Decimal(0),required-budget)))
            if not 0<required<=budget:
                item['state']='BUDGET';continue
            item['state']='NOT_CHECKED' if preview or (low<=row['rank']<=high and (approved is None or row['symbol'] in approved)) else 'OUTSIDE_RANGE'
        selected=None
        for row in candidates:
            item=by_symbol[row['symbol']]
            if item['state']!='NOT_CHECKED':continue
            candles=self.b.get('candles',{'symbol':row['symbol'],'interval':'1d','count':self.c['slow']+10,'adjusted':'true'})['candles']
            completed={}
            for c in candles:
                day=stamp(c['timestamp']).date().isoformat()
                if day<=previous_day:
                    if day in completed or c['currency']!='KRW': raise SafetyStop('Invalid ETF candle series')
                    completed[day]=dec(c['closePrice'])
            days=sorted(completed)
            item.update(candles=len(days),last_day=days[-1] if days else None)
            if len(days)<self.c['slow'] or days[-1]!=previous_day or any(v<=0 for v in completed.values()):
                item['state']='CANDLES';continue
            values=[completed[d] for d in days]
            fast=sum(values[-self.c['fast']:])/self.c['fast']; slow=sum(values[-self.c['slow']:])/self.c['slow']
            item.update(fast_ma=str(fast),slow_ma=str(slow))
            if fast<=slow:
                item['state']='TREND';continue
            item['state']='ELIGIBLE'
            if selected is None:selected=row
        details['complete']=True
        if selected is not None and not preview:
            row=selected
            by_symbol[row['symbol']]['state']='SELECTED'
            self.s['selection']=dict(symbol=row['symbol'],rank=row['rank'],name=row['name'],
                net_assets_won=row['net_assets_won'],research_digest=book['digest'],
                assessment=book['assessments'][row['symbol']],selected_at=self.clock().isoformat())
            self.s['managed_symbol']=row['symbol'];self.store.save()
            return row['symbol']
        return None

    def step(self,stop=False):
        # Never change identity while any intent is outstanding, including unknown outcomes.
        if not stop and not self.active() and not self.s['quantity']:
            if self.b.orders() or self.holdings(): raise SafetyStop('Unexpected account position/order')
            if self.s['halted']: return {'status':'HALTED','quantity':0}
            window=self.market()
            if not window: return self.market_status
            self.previous_day=window[0]['previousBusinessDay']['date']
            # Period rollover and target latches also apply while cash-only.
            hit,loss=self.observe(dec(self.s['cash']),self.clock())
            if hit or loss or self.s['last_buy_day']==self.clock().date().isoformat():
                return {'status':'ENTRY_PAUSED','returns':self.s['returns']}
            try:
                selected=self.select(self.previous_day)
            except (OSError,ValueError,KeyError,TypeError,SafetyStop):
                return {'status':'RESEARCH_OR_CANDIDATE_DATA_UNAVAILABLE','selection_details':getattr(self,'selection_details',{})}
            if not selected: return {'status':'NO_ELIGIBLE_AFFORDABLE_ETF','selection_details':self.selection_details}
            self.symbol=selected
        result=super().step(stop=stop)
        if 'selected' in locals():result['selection_details']=self.selection_details
        return result
