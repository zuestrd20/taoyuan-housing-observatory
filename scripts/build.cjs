const fs=require('node:fs');
const files=['index.html','style.css','app.js','.nojekyll'];
fs.rmSync('dist',{recursive:true,force:true});fs.mkdirSync('dist',{recursive:true});
for(const f of files)fs.copyFileSync(f,'dist/'+f);
fs.cpSync('data','dist/data',{recursive:true});
console.log('Static public site prepared in dist/');
