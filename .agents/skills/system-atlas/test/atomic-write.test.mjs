import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { atomicWrite } from '../design/authority.mjs';

function fixture(t){
  const directory=fs.mkdtempSync(path.join(os.tmpdir(),'atlas-atomic-write-'));
  t.after(()=>fs.rmSync(directory,{recursive:true,force:true}));
  return {directory,file:path.join(directory,'state.json')};
}

test('atomic write creates and replaces complete state, without leftover temporary files',t=>{
  const {directory,file}=fixture(t);
  atomicWrite(file,'{"cursor":1}\n');atomicWrite(file,'{"cursor":2,"value":"更新"}\n');
  assert.deepEqual(JSON.parse(fs.readFileSync(file,'utf8')),{cursor:2,value:'更新'});
  assert.deepEqual(fs.readdirSync(directory),['state.json']);
});

test('file flush failure propagates and preserves the previous accepted file',t=>{
  const {directory,file}=fixture(t);fs.writeFileSync(file,'old');
  const original=fs.fsyncSync;
  t.mock.method(fs,'fsyncSync',fd=>{
    if(fs.fstatSync(fd).isFile())throw Object.assign(new Error('file flush denied'),{code:'EPERM'});
    return original(fd);
  });
  assert.throws(()=>atomicWrite(file,'new'),{code:'EPERM'});
  assert.equal(fs.readFileSync(file,'utf8'),'old');
  assert.deepEqual(fs.readdirSync(directory),['state.json']);
});

test('write failure propagates and preserves the previous accepted file',t=>{
  const {directory,file}=fixture(t);fs.writeFileSync(file,'old');
  t.mock.method(fs,'writeFileSync',()=>{throw Object.assign(new Error('full disk'),{code:'ENOSPC'});});
  assert.throws(()=>atomicWrite(file,'new'),{code:'ENOSPC'});
  assert.equal(fs.readFileSync(file,'utf8'),'old');
  assert.deepEqual(fs.readdirSync(directory),['state.json']);
});

test('replacement failure is not mistaken for unsupported directory flushing',t=>{
  const {directory,file}=fixture(t);fs.writeFileSync(file,'old');
  t.mock.method(fs,'renameSync',()=>{throw Object.assign(new Error('replace denied'),{code:'EACCES'});});
  assert.throws(()=>atomicWrite(file,'new'),{code:'EACCES'});
  assert.equal(fs.readFileSync(file,'utf8'),'old');
  assert.deepEqual(fs.readdirSync(directory),['state.json']);
});

test('file content is always flushed; directory flushing follows the host capability',t=>{
  const {file}=fixture(t),original=fs.fsyncSync,kinds=[];
  t.mock.method(fs,'fsyncSync',fd=>{kinds.push(fs.fstatSync(fd).isDirectory()?'directory':'file');return original(fd);});
  atomicWrite(file,'new');
  assert.deepEqual(kinds,process.platform==='win32'?['file']:['file','directory']);
});

test('POSIX directory flush errors still propagate', {skip:process.platform==='win32'},t=>{
  const {file}=fixture(t),original=fs.fsyncSync;
  t.mock.method(fs,'fsyncSync',fd=>{
    if(fs.fstatSync(fd).isDirectory())throw Object.assign(new Error('directory I/O failure'),{code:'EIO'});
    return original(fd);
  });
  assert.throws(()=>atomicWrite(file,'new'),{code:'EIO'});
});
