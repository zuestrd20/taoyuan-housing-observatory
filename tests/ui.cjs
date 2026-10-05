/* DOM integration tests. Synthetic fixtures are generated in memory only. */
const {JSDOM}=require('jsdom');
const fs=require('node:fs');const assert=require('node:assert/strict');
const html=fs.readFileSync('index.html','utf8'),script=fs.readFileSync('app.js','utf8');
const map=JSON.parse(fs.readFileSync('data/taoyuan-districts.geojson','utf8'));
const names=map.features.map(f=>f.properties.TOWNNAME);
const years=Array.from({length:10},(_,i)=>2016+i);
const fixture={years,types:[{id:'all',label:'集合住宅',unit:'萬元／坪'},{id:'house',label:'透天厝',unit:'萬元／件',metricLabel:'透天厝成交總價中位數'}],metadata:{checkedAt:'2026-10-05',methodSections:[{title:'Test',paragraphs:['Test source']} ]},records:[]};
for(const [i,district]of names.entries())for(const year of years)for(const type of ['all','house'])fixture.records.push({district,year,type,medianPrice:district==='復興區'?null:type==='house'?1500+i*100:20+i+(year-2016),count:district==='復興區'?0:80});
async function setup(data=fixture,search=''){
 let dom=new JSDOM(html,{url:'https://example.org/site/'+search,runScripts:'outside-only',pretendToBeVisual:true});let w=dom.window;
 w.fetch=async u=>({ok:true,json:async()=>u.includes('housing')?data:map});w.matchMedia=()=>({matches:true});w.HTMLElement.prototype.scrollIntoView=()=>{};w.Blob=class{constructor(parts){this.parts=parts}};w.URL.createObjectURL=b=>{w.downloaded=b.parts.join('');return 'blob:test'};w.HTMLAnchorElement.prototype.click=function(){w.downloadName=this.download};w.URL.revokeObjectURL=()=>{};w.console.error=()=>{};
 w.eval(script);await new Promise(r=>setTimeout(r,20));return dom;
}
(async()=>{let dom=await setup(),w=dom.window,d=w.document;
 assert.equal(d.querySelectorAll('.district-shape').length,13);assert.equal(d.querySelectorAll('.compare-row').length,13);assert.equal(d.querySelector('#year').value,'2025');assert.equal(d.querySelector('#price').textContent,'29.0');
 const choose=(id,v)=>{d.querySelector(id).value=v;d.querySelector(id).dispatchEvent(new w.Event('change'))};
 choose('#year','2016');assert.equal(d.querySelector('#change').textContent,'無可比較資料');
 let shape=d.querySelector('[data-district="中壢區"]');shape.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));assert.equal(d.querySelector('#district').value,'中壢區');assert.equal(shape.getAttribute('aria-pressed'),'true');
 shape.dispatchEvent(new w.KeyboardEvent('keydown',{key:' ',bubbles:true}));assert.equal(d.querySelectorAll('.district-shape.selected').length,1);
 choose('#district','復興區');assert.equal(d.querySelector('#price').textContent,'—');assert.equal(d.querySelector('#count').textContent,'0 筆');assert.match(d.querySelector('#sample-warning').textContent,/缺值不視為零/);assert.equal(d.querySelectorAll('#trend circle').length,0);
 choose('#district','桃園區');choose('#type','house');assert.equal(d.querySelector('.price>span:last-child').textContent,'萬元／件');assert.equal(d.querySelector('#price').textContent,'1500.0');assert.equal(d.querySelector('#annual-table th:nth-child(2)').textContent,'萬元／件');
 d.querySelector('#download').click();assert.equal(w.downloadName,'taoyuan-housing-annual-aggregates.csv');assert.equal(w.downloaded.split('\r\n').length,261);assert.match(w.downloaded,/樣本狀態/);assert.match(w.downloaded,/萬元／件/);assert.match(w.downloaded,/萬元／坪/);
 let qs=w.location.search;w.location.hash='method';await new Promise(r=>setTimeout(r,10));assert.equal(w.location.search,qs);assert.equal(d.querySelector('#type').value,'house');
 d.querySelector('#reset').click();assert.equal(d.querySelector('#year').value,'2025');assert.equal(d.querySelector('#type').value,'all');assert.equal(d.querySelector('#district').value,'桃園區');
 w.history.back();await new Promise(r=>setTimeout(r,30));assert.equal(d.querySelector('#type').value,'house');
 dom.window.close();
 dom=await setup(fixture,'?year=banana&type=evil&district=bogus');assert.equal(dom.window.document.querySelector('#year').value,'2025');dom.window.close();
 dom=await setup({...fixture,records:[]});assert.match(dom.window.document.querySelector('#status').className,/error/);assert.equal(dom.window.document.querySelector('#download').disabled,true);dom.window.close();
 console.log('PASS: 13 districts, keyboard/repeated selection, null/zero, type/unit, year, reset, anchors, Back, invalid URL, load failure, complete CSV download.');
})().catch(e=>{console.error(e);process.exitCode=1});
