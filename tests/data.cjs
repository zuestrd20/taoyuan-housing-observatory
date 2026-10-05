const fs=require('node:fs'),assert=require('node:assert/strict');
const data=JSON.parse(fs.readFileSync('data/housing.json','utf8'));
const geo=JSON.parse(fs.readFileSync('data/taoyuan-districts.geojson','utf8'));
assert.equal(geo.features.length,13);
const districts=geo.features.map(f=>f.properties.TOWNNAME);
assert.equal(new Set(districts).size,13);
assert.deepEqual(data.years,[2016,2017,2018,2019,2020,2021,2022,2023,2024,2025]);
assert(data.types.length>=4);
const keys=new Set();
for(const r of data.records){
 assert(districts.includes(r.district));assert(data.years.includes(r.year));assert(data.types.some(t=>t.id===r.type));
 const key=[r.district,r.year,r.type].join('|');assert(!keys.has(key),key);keys.add(key);
 assert(Number.isInteger(r.count)&&r.count>=0);
 assert(r.medianPrice===null||(Number.isFinite(r.medianPrice)&&r.medianPrice>0));
 if(r.count<5)assert.equal(r.medianPrice,null,'Small samples must be suppressed');
}
assert.equal(keys.size,13*data.years.length*data.types.length,'Complete matrix, including missing cells');
assert(data.metadata.checkedAt);assert(data.metadata.methodSections?.length>=4);
for(const f of geo.features){assert(f.properties.labelPoint);assert(['Polygon','MultiPolygon'].includes(f.geometry.type));}
const joined=fs.readFileSync('data/housing.json','utf8');
for(const forbidden of ['土地位置建物門牌','建物移轉總面積平方公尺','買受人','出賣人','/workspace/','ghp_','github_pat_'])assert(!joined.includes(forbidden),forbidden);
console.log(`PASS: verified schema, ${keys.size} aggregate cells, missing/small samples, 13 district geometry, privacy field scan.`);
