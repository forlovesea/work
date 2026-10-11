"""Build a provenance-bearing ETF research snapshot; never sends brokerage orders."""
import argparse
from pathlib import Path
from live import ROOT, Store, SafetyStop, now_kst, process_lock
from etf_research import universe, holdings, news_summary, assess
from research_sources import Sources


def build(catalog,composition,as_of,output,sources=None,now=None):
    now=now or now_kst()
    from datetime import date
    if not 0<=(now.date()-date.fromisoformat(as_of)).days<=10:
        raise SafetyStop('Snapshot date must be recent and cannot be in the future')
    top=universe(catalog,as_of)
    if not top: raise SafetyStop('No KOSDAQ-related ETFs in supplied complete universe')
    components=holdings(composition,as_of)
    sources=sources or Sources(ROOT/'research'/'cache',now)
    financials={}
    assessments={}
    for etf in top:
        rows=components.get(etf['symbol'],[])
        print(f"분석 {etf['rank']}/{len(top)}: {etf['symbol']} {etf['name']}",flush=True)
        if etf['tradable']:
            for row in rows:
                corp=row['corp_code']
                if corp not in financials: financials[corp]=sources.financial(corp)
            # ETF-specific news plus the three largest constituent names; never execute news text.
            names=[etf['name']]+[r['name'] for r in sorted(rows,key=lambda r:-float(r['weight']))[:3]]
            items=[]
            for name in names: items.extend(sources.news(name))
            news=news_summary(items,names,now)
        else:
            news={'count':0,'risk':False,'positive_count':0,'articles':[]}
        assessments[etf['symbol']]=assess(etf,rows,financials,news,now)
    book=dict(schema=1,ranking='net_assets_won',as_of=as_of,generated_at=now.isoformat(),
              scope='Name or benchmark explicitly contains KOSDAQ; supplied complete universe',
              universe=top,assessments=assessments,composition=components)
    store=Store(output)
    store.data=book
    store.save()
    archive=Store(Path(output).parent/(now.strftime('%Y%m%d_%H%M%S_%f')+'.json'))
    archive.data=book
    archive.save()
    import csv
    with (Path(output).parent/'latest_summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['기준일','순위','종목코드','ETF명','순자산_원','분석통과','재무점수','재무확인비중','뉴스수','보류사유','출처'])
        for row in top:
            a=assessments[row['symbol']]
            writer.writerow([as_of,row['rank'],row['symbol'],row['name'],row['net_assets_won'],a['allow_buy'],
                             a['score'],a['coverage'],a['news']['count'],';'.join(a['reasons']),row['source_url']])
    return book


def main():
    p=argparse.ArgumentParser(description='Build KOSDAQ ETF top-20 research from complete official snapshots')
    p.add_argument('--universe',type=Path,required=True)
    p.add_argument('--holdings',type=Path,required=True)
    p.add_argument('--as-of',required=True,help='Official common valuation date YYYY-MM-DD')
    p.add_argument('--output',type=Path,default=ROOT/'research'/'latest.json')
    args=p.parse_args()
    with process_lock(ROOT/'research'/'build.lock'):
        book=build(args.universe,args.holdings,args.as_of,args.output)
    print(f"저장 완료: {args.output} / {len(book['universe'])}개 중 매수 분석 통과 {sum(a['allow_buy'] for a in book['assessments'].values())}개")


if __name__=='__main__':
    try: main()
    except (SafetyStop,OSError,ValueError,KeyError,TypeError) as exc:
        print('분석 중단:',str(exc) if isinstance(exc,SafetyStop) else type(exc).__name__)
        print('완성된 최신 분석 없이 신규 ETF 매수를 허용하지 않습니다.')
        raise SystemExit(1)
