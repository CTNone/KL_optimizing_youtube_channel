const assert = require('node:assert/strict');
require('./folder-writer.js');
let exists=false,closed=false,aborted=false,size=0,deny=false;
const directory={name:'Images',getDirectoryHandle:async()=>({getFileHandle:async(name,options)=>{
  if(!options?.create){if(!exists || name.includes(' (1)'))throw Object.assign(new Error('missing'),{name:'NotFoundError'});return {};}
  return {createWritable:async()=>({write:async blob=>{if(deny)throw Error('disk full');size=blob.size;},close:async()=>{closed=true;},abort:async()=>{aborted=true;}}),getFile:async()=>({size})};
}})};
(async()=>{
 const data='data:image/png;base64,aGVsbG8=';
 const saved=await FlowFiles.write(directory,'run_123/0001_01.png',data);
 assert.equal(saved,'Images/run_123/0001_01.png');assert.equal(closed,true);assert.equal(size,5);
 exists=true;assert.equal(await FlowFiles.write(directory,'run_123/0001_01.png',data),'Images/run_123/0001_01 (1).png');
 exists=false;
 const cropped='data:image/jpeg;base64,aGVsbG8=';
 assert.equal(await FlowFiles.write(directory,'run_123/0001_01_16x9.jpg',cropped),'Images/run_123/0001_01_16x9.jpg');
 exists=true;assert.equal(await FlowFiles.write(directory,'run_123/0001_01_16x9.jpg',cropped),'Images/run_123/0001_01_16x9 (1).jpg');
 await assert.rejects(FlowFiles.write(directory,'run_123/0001_01_other.jpg',cropped),/không hợp lệ/);
 exists=false;deny=true;await assert.rejects(FlowFiles.write(directory,'run_123/0001_01.png',data),/disk full/);assert.ok(aborted);
 await assert.rejects(FlowFiles.write(directory,'../escape.png',data),/không hợp lệ/);
 console.log('PASS: folder write verifies bytes; name collisions get suffix; path traversal rejected; disk failure aborts.');
})().catch(e=>{console.error(e);process.exitCode=1;});
