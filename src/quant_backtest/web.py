"""Local browser dashboard backed by the same Python research engine."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path

from .data import load_csv
from .engine import backtest, buy_and_hold
from .metrics import performance_metrics
from .strategies import mean_reversion, moving_average


def evaluate(prices, config):
    if not isinstance(config, dict):
        raise ValueError("Request must be a JSON object.")
    name = config.get("strategy", "ma")
    if name == "ma":
        signal = moving_average(prices, config.get("fast", 20), config.get("slow", 100))
    elif name == "mean-reversion":
        signal = mean_reversion(prices, config.get("window", 20),
                                config.get("entry_z", 1.5), config.get("exit_z", 0))
    else:
        raise ValueError("Unknown strategy.")
    cash = config.get("cash", 100_000)
    settings = dict(initial_cash=cash, commission_bps=config.get("commission_bps", 1),
                    slippage_bps=config.get("slippage_bps", 4))
    result = backtest(prices, signal, **settings)
    benchmark = buy_and_hold(prices, **settings)
    metric_settings = dict(initial_cash=cash, risk_free_rate=config.get("risk_free_rate", 0),
                           periods_per_year=config.get("periods_per_year", 252))
    return {
        "metrics": {"strategy": performance_metrics(result, **metric_settings),
                    "buy_and_hold": performance_metrics(benchmark, **metric_settings)},
        "dates": [str(d.date()) for d in result.index],
        "equity": {"strategy": result.equity.tolist(), "buy_and_hold": benchmark.equity.tolist()},
        "drawdown": {"strategy": result.drawdown.tolist(), "buy_and_hold": benchmark.drawdown.tolist()},
        "csv": result.to_csv(index_label="Date"),
    }


def make_handler(prices, source):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, body, content_type="application/json"):
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path == "/":
                self.respond(200, HTML, "text/html")
            elif self.path == "/api/info":
                self.respond(200, json.dumps({"source": source, "rows": len(prices),
                    "first": str(prices.index[0].date()), "last": str(prices.index[-1].date())}))
            else:
                self.respond(404, json.dumps({"error": "Not found"}))

        def do_POST(self):
            if self.path != "/api/backtest":
                self.respond(404, json.dumps({"error": "Not found"}))
                return
            if self.headers.get_content_type() != "application/json":
                self.respond(415, json.dumps({"error": "Use application/json."}))
                return
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers.get("Host", ""):
                self.respond(403, json.dumps({"error": "Cross-origin requests are not allowed."}))
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16_384:
                    raise ValueError("Request must contain at most 16 KB of JSON.")
                config = json.loads(self.rfile.read(length))
                body = json.dumps(evaluate(prices, config), allow_nan=False)
            except (ValueError, TypeError, OverflowError) as exc:
                self.respond(400, json.dumps({"error": str(exc)}))
                return
            self.respond(200, body)

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=Path("data/synthetic.csv"))
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    try:
        prices = load_csv(args.csv)
        server = HTTPServer(("127.0.0.1", args.port), make_handler(prices, args.csv.name))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Dashboard: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Quant Backtest Lab</title><style>
:root{font:15px system-ui,sans-serif;color:#17243d;background:#f8f7f3}*{box-sizing:border-box}body{margin:0}header{padding:28px 5%;background:#14233d;color:white}header p{color:#becbe1;margin-bottom:0}h1{font-size:27px;margin:4px 0}h2{font-size:18px;margin:0 0 16px}.eyebrow{font-size:11px;letter-spacing:2px;color:#9cc3ff}main{max-width:1400px;margin:auto;padding:26px;display:grid;grid-template-columns:280px minmax(0,1fr);gap:24px}.panel{background:white;border:1px solid #dbe3ef;border-radius:12px;padding:22px}.inputs{align-self:start}label{display:block;font-size:13px;font-weight:600;margin:14px 0 6px}input,select,button{font:inherit;width:100%;border:1px solid #c8d3e3;border-radius:6px;padding:10px;background:white;color:#17243d}button{background:#215bd5;color:white;border:0;margin-top:20px;cursor:pointer;font-weight:600}button:disabled{opacity:.5;cursor:wait}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.muted{font-size:12px;line-height:1.6;color:#536681}.notice{background:#eaf1ff;border-radius:6px;padding:12px;line-height:1.6;font-size:12px;margin:16px 0}.content{min-width:0;display:grid;gap:20px}.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.card{padding:18px;background:white;border:1px solid #dbe3ef;border-radius:10px}.card span{font-size:12px;color:#536681}.card strong{display:block;font-size:24px;margin-top:8px;font-variant-numeric:tabular-nums}svg{display:block;width:100%;height:auto}.legend{display:flex;gap:20px;font-size:12px;margin-bottom:10px}.blue{color:#215bd5}.gray{color:#64748b}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:13px}th,td{text-align:right;border-bottom:1px solid #e7edf5;padding:10px}th:first-child,td:first-child{text-align:left}#error{background:#fff0ee;color:#a01b10;padding:12px;border-radius:6px;font-size:13px}#download{width:auto;background:#eef3fc;color:#215bd5;border:1px solid #c8d3e3;margin:0}#status{margin:0;font-size:13px;color:#536681}[hidden]{display:none!important}input:focus,select:focus,button:focus{outline:2px solid #75a5ff;outline-offset:2px}@media(max-width:900px){main{grid-template-columns:1fr;padding:16px}.cards{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:400px){.card strong{font-size:20px}.panel{padding:14px}th,td{padding:8px 4px;font-size:12px}}

/* Research notebook: a deliberately restrained typographic hierarchy. */
:root{color:#26302e;background:#f6f5f0}header{background:#f6f5f0;color:#25312d;border-bottom:1px solid #c6c9bc;padding:36px max(26px,calc((100% - 1350px)/2)) 30px}header p{color:#59655c;max-width:620px;line-height:1.5}h1{font-family:Georgia,serif;font-size:clamp(30px,3.4vw,48px);font-weight:normal;letter-spacing:-1px}.eyebrow,.section-id{font:700 10px/1.4 system-ui,sans-serif;letter-spacing:1.5px;color:#62785d}.section-id{margin-bottom:10px}.panel,.card{border:1px solid #d7d9cc;border-radius:2px;background:#fffefa;box-shadow:none}main{max-width:1400px;gap:30px}.panel{padding:25px}.inputs{border-top:3px solid #b07745}.cards{gap:0;background:#fffefa;border:1px solid #d7d9cc}.card{border:0;border-right:1px solid #d7d9cc;border-radius:0}.card:last-child{border:0}.card strong{font-family:Georgia,serif;font-weight:normal;letter-spacing:-.6px;color:#25312d}.muted{color:#59655c}.notice{background:#f3f0e9;border-left:3px solid #b07745;border-radius:0;color:#424c46}.legend .blue{color:#35695b}.legend .gray{color:#5f6772}input,select{border-radius:2px;border-color:#bfc7b9;background:#fffefa;color:#26302e}button{border-radius:2px;background:#35695b}button:hover{background:#254e44}#download{color:#35695b;background:#f3f5f0;border-color:#bcc8b9}#status{font-size:13px;color:#35695b}#error{border-radius:2px;background:#fbefeb;color:#9f392a}th{background:#f3f4ed;color:#435047}h2{font-family:Georgia,serif;font-size:22px;font-weight:normal}svg{margin-top:10px}@media(max-width:600px){header{padding:24px 16px}.cards{grid-template-columns:repeat(2,minmax(0,1fr))}.card:nth-child(2){border-right:0}.card:nth-child(-n+2){border-bottom:1px solid #d7d9cc}main{gap:16px}}
</style></head><body><header><div class="eyebrow">FIELD NOTES / 01</div><h1>Quant Backtest Lab</h1><p>A small, inspectable trading experiment. Change the assumptions; see what follows.</p></header>
<main><form id="controls" class="panel inputs" novalidate><h2>Set the assumptions</h2><p id="source" class="muted">Loading dataset…</p>
<label for="strategy">Strategy</label><select id="strategy"><option value="ma">Moving average crossover</option><option value="mean-reversion">Mean reversion</option></select>
<div id="ma-fields" class="row"><div><label for="fast">Fast window</label><input id="fast" type="number" value="20" min="1" required></div><div><label for="slow">Slow window</label><input id="slow" type="number" value="100" min="2" required></div></div>
<div id="mr-fields" hidden><label for="window">Rolling window</label><input id="window" type="number" value="20" min="2" required><div class="row"><div><label for="entry_z">Entry z-score</label><input id="entry_z" type="number" value="1.5" min="0.01" step="any" required></div><div><label for="exit_z">Exit z-score</label><input id="exit_z" type="number" value="0" min="0" step="any" required></div></div></div>
<label for="cash">Initial capital</label><input id="cash" type="number" value="100000" min="1" step="any" required>
<div class="row"><div><label for="commission_bps">Commission (bps)</label><input id="commission_bps" type="number" value="1" min="0" step="any" required></div><div><label for="slippage_bps">Slippage (bps)</label><input id="slippage_bps" type="number" value="4" min="0" step="any" required></div></div>
<label for="risk_free_rate">Annual risk-free rate (%)</label><input id="risk_free_rate" type="number" value="0" min="-99" max="100" step="any" aria-describedby="rf-hint" required><span class="muted" id="rf-hint">Enter 5 for 5%. This changes Sharpe and Sortino, not the equity curve.</span>
<button id="run" type="button">Run backtest</button><div class="notice"><b>How to read this.</b> Window and threshold settings change when trades happen. Capital rescales the equity chart; the risk-free rate only changes the risk ratios. Signals execute at the next close.</div><p class="muted">The default dataset is synthetic. Its results demonstrate the software and do not establish an investment edge. Use your own adjusted-close CSV through the server's --csv option.</p></form>
<section class="content"><p id="status" role="status" aria-live="polite">Preparing dashboard…</p><div id="error" role="alert" hidden></div><div class="cards"><div class="card"><span>Total return</span><strong id="total">—</strong></div><div class="card"><span>Sharpe ratio</span><strong id="sharpe">—</strong></div><div class="card"><span>Sortino ratio</span><strong id="sortino">—</strong></div><div class="card"><span>Max drawdown</span><strong id="drawdown">—</strong></div></div>
<div class="panel"><div class="section-id">FIGURE 01 / PORTFOLIO</div><h2>Equity over time</h2><p class="muted">The shape reflects trading decisions and costs. Capital changes the dollar scale.</p><div class="legend"><span class="blue">● Strategy</span><span class="gray">● Buy &amp; hold</span></div><svg id="equity-chart" viewBox="0 0 840 260" role="img" aria-label="Strategy and buy-and-hold equity over time"></svg></div>
<div class="panel"><div class="section-id">FIGURE 02 / RISK</div><h2>Drawdown</h2><svg id="drawdown-chart" viewBox="0 0 840 180" role="img" aria-label="Strategy and buy-and-hold drawdowns over time"></svg></div>
<div class="panel"><div class="section-id">TABLE 01 / COMPARISON</div><h2>Performance comparison</h2><table><thead><tr><th>Metric</th><th>Strategy</th><th>Buy &amp; hold</th></tr></thead><tbody id="metrics"></tbody></table><p class="muted">252 trading periods per year. Warm-up stays in the evaluation window. Undefined ratios appear as —. Positions are marked to market without final liquidation.</p><button id="download" type="button" disabled>Download backtest CSV</button></div></section></main>
<script>
const $=id=>document.getElementById(id);let current=null;
const percent=v=>v===null?'—':(v*100).toFixed(2)+'%';
const number=v=>v===null?'—':v.toFixed(3);
const fields=['fast','slow','window','entry_z','exit_z','cash','commission_bps','slippage_bps','risk_free_rate'];
const definitions=[['total_return','Total return',percent],['cagr','CAGR',percent],['annualized_volatility','Annualized volatility',percent],['sharpe_ratio','Sharpe ratio',number],['sortino_ratio','Sortino ratio',number],['max_drawdown','Maximum drawdown',percent],['calmar_ratio','Calmar ratio',number],['exposure','Exposure',percent],['one_way_trades','Entries + exits',String],['observations','Return observations',String]];
function selectStrategy(){const ma=$('strategy').value==='ma';$('ma-fields').hidden=!ma;$('mr-fields').hidden=ma;for(const id of ['fast','slow'])$(id).disabled=!ma;for(const id of ['window','entry_z','exit_z'])$(id).disabled=ma;}$('strategy').addEventListener('change',selectStrategy);selectStrategy();
function chart(id,series,dates,isPercent){
 const svg=$(id),H=id==='equity-chart'?260:180,W=840,L=70,R=15,T=15,B=30;
 const all=[...series.strategy,...series.buy_and_hold];let low=Math.min(...all),high=Math.max(...all);if(high===low){low-=1;high+=1;}
 const x=i=>L+i*(W-L-R)/(dates.length-1),y=v=>T+(high-v)*(H-T-B)/(high-low);
 const ns='http://www.w3.org/2000/svg';svg.replaceChildren();
 function add(tag,attrs,text){const el=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);if(text!==undefined)el.textContent=text;svg.append(el);return el;}
 for(let i=0;i<4;i++){const v=low+(high-low)*i/3,py=y(v);add('line',{x1:L,x2:W-R,y1:py,y2:py,stroke:'#e7edf5'});add('text',{x:L-8,y:py+4,'text-anchor':'end',fill:'#536681','font-size':11},isPercent?percent(v):Math.round(v).toLocaleString());}
 for(const [key,color] of [['buy_and_hold','#5f6772'],['strategy','#35695b']])add('path',{d:series[key].map((v,i)=>(i?'L':'M')+x(i).toFixed(2)+','+y(v).toFixed(2)).join(' '),fill:'none',stroke:color,'stroke-width':2});
 add('text',{x:L,y:H-5,fill:'#536681','font-size':11},dates[0]);add('text',{x:W-R,y:H-5,'text-anchor':'end',fill:'#536681','font-size':11},dates.at(-1));
}
async function run(event){if(event)event.preventDefault();$('run').disabled=true;$('download').disabled=true;current=null;$('error').hidden=true;$('status').textContent='Running Python backtest…';
 try{const active=$('strategy').value==='ma'?['fast','slow']:['window','entry_z','exit_z'];for(const key of [...active,'cash','commission_bps','slippage_bps','risk_free_rate']){const field=$(key);if(!field.checkValidity()){field.focus();throw Error('Check '+field.labels[0].textContent+': '+(field.validity.valueMissing?'enter a value.':field.validity.rangeOverflow?'the value is too high.':field.validity.rangeUnderflow?'the value is too low.':'enter a valid number.'));}}const config={strategy:$('strategy').value};for(const key of fields)config[key]=Number($(key).value);config.risk_free_rate/=100;
 const response=await fetch('/api/backtest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config)});const result=await response.json();if(!response.ok)throw Error(result.error);
 const m=result.metrics.strategy;$('total').textContent=percent(m.total_return);$('sharpe').textContent=number(m.sharpe_ratio);$('sortino').textContent=number(m.sortino_ratio);$('drawdown').textContent=percent(m.max_drawdown);
 $('metrics').replaceChildren();for(const [key,label,format] of definitions){const row=document.createElement('tr');for(const text of [label,format(m[key]),format(result.metrics.buy_and_hold[key])]){const cell=document.createElement('td');cell.textContent=text;row.append(cell);}$('metrics').append(row);}
 chart('equity-chart',result.equity,result.dates,false);chart('drawdown-chart',result.drawdown,result.dates,true);current=result;$('download').disabled=false;$('status').textContent='Updated · '+m.one_way_trades+' entries or exits · '+m.observations+' return observations · '+($('strategy').value==='ma'?'Moving average crossover':'Mean reversion');
 }catch(error){$('error').textContent=error.message;$('error').hidden=false;$('status').textContent='Run failed. Any displayed results are from the previous successful run.';}
 finally{$('run').disabled=false;}
}
$('run').addEventListener('click',run);$('controls').addEventListener('submit',run);$('controls').addEventListener('input',()=>{$('status').textContent='Settings changed · press Run backtest to update the results.';});$('strategy').addEventListener('change',()=>{$('status').textContent='Strategy changed · press Run backtest to update the results.';});
$('download').addEventListener('click',()=>{if(!current)return;const url=URL.createObjectURL(new Blob([current.csv],{type:'text/csv'}));const a=document.createElement('a');a.href=url;a.download='backtest.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
fetch('/api/info').then(r=>{if(!r.ok)throw Error('Cannot load dataset');return r.json();}).then(info=>{$('source').textContent=info.source+' · '+info.rows+' prices · '+info.first+' to '+info.last;return run();}).catch(error=>{$('status').textContent='Dashboard unavailable';$('error').textContent=error.message;$('error').hidden=false;});
</script></body></html>'''


if __name__ == "__main__":
    main()
