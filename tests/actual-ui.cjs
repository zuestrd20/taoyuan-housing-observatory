const {JSDOM}=require('jsdom'),fs=require('node:fs'),assert=require('node:assert/strict');
const data=JSON.parse(fs.readFileSync('data/housing.json')),geo=JSON.parse(fs.readFileSync('data/taoyuan-districts.geojson'));
const dom=new JSDOM(fs.readFileSync('index.html','utf8'),{url:'https://example.org/',runScripts:'outside-only'}),w=dom.window;
w.fetch=async p=>({ok:true,json:async()=>p.includes('housing')?data:geo});w.matchMedia=()=>({matches:true});w.HTMLElement.prototype.scrollIntoView=()=>{};
w.eval(fs.readFileSync('app.js','utf8'));
setTimeout(()=>{try{let checked=0;const d=w.document;
 for(const r of data.records){for(const k of ['year','type','district']){let e=d.querySelector('#'+k);if(e.value!==String(r[k])){e.value=r[k];e.dispatchEvent(new w.Event('change'))}}
  assert.equal(d.querySelector('#price').textContent,r.medianPrice===null?'—':r.medianPrice.toFixed(1));
  assert.equal(d.querySelector('#count').textContent,r.count.toLocaleString()+' 筆');
  assert.equal(d.querySelector('.price>span:last-child').textContent,data.types.find(t=>t.id===r.type).unit);
  assert.equal(d.querySelectorAll('.district-shape.selected').length,1);checked++;
 }
 console.log('PASS: all '+checked+' actual data combinations render correct price/count/unit/selection.');
}catch(e){console.error(e);process.exitCode=1}finally{w.close()}},30);
