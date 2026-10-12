"""Explicit user-approved rank scope, separate from the account ledger configuration."""
import json
from pathlib import Path
from live import Store, SafetyStop

OPTIONS={'전체 1~20위':(1,20),'상위 1~10위':(1,10),'하위 11~20위':(11,20)}


def read_symbols(path,binding):
    path=Path(path)
    if not path.exists():return None
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('binding')!=binding or 'symbols' not in data:return None
    symbols=data['symbols']
    import re
    if not isinstance(symbols,list) or not symbols or len(symbols)>20 or any(not isinstance(s,str) or not re.fullmatch(r'[0-9]{6}',s) for s in symbols):
        raise SafetyStop('Invalid ETF selected symbols; no new buy')
    return set(symbols)


def write_symbols(path,binding,symbols):
    import re
    symbols=sorted(set(symbols))
    if not symbols or len(symbols)>20 or any(not re.fullmatch(r'[0-9]{6}',s) for s in symbols):raise ValueError('Invalid symbols')
    store=Store(path)
    store.data=dict(binding=binding,min_rank=1,max_rank=20,symbols=symbols)
    store.save()


def candidate_rows(details):
    """Unique measured candidates; never invent a recommendation for missing data."""
    rows={}
    for row in (details or {}).get('rows',[]):
        rows.setdefault(row['symbol'],row)
    return sorted(rows.values(),key=lambda r:(r.get('state') not in ('ELIGIBLE','SELECTED'),-float(r.get('score',0)),r.get('rank',99)))


def read_scope(path,binding):
    path=Path(path)
    if not path.exists():return (1,20)
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('binding')!=binding:return (1,20)
    low,high=data.get('min_rank'),data.get('max_rank')
    if type(low) is not int or type(high) is not int or not 1<=low<=high<=20:
        raise SafetyStop('Invalid ETF rank scope; no new buy')
    return low,high


def write_scope(path,binding,low,high):
    if type(low) is not int or type(high) is not int or not 1<=low<=high<=20:raise ValueError('Invalid rank range')
    store=Store(path);store.data=dict(binding=binding,min_rank=low,max_rank=high);store.save()


def proposals(details):
    result=[]
    rows=(details or {}).get('rows',[])
    budget=float((details or {}).get('budget',0))
    for label,(low,high) in OPTIONS.items():
        group=[row for row in rows if low<=row.get('rank',0)<=high]
        eligible=[row for row in group if 'required' in row and 0<float(row['required'])<=budget
                  and row['state'] not in ('STRUCTURE','RESEARCH','QUOTE_UNAVAILABLE')]
        known=sum('required' in row for row in group)
        result.append(dict(label=label,low=low,high=high,total=len(group),priced=known,affordable=len(eligible)))
    return result
