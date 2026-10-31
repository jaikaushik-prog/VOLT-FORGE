import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, writeFile, copyFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {readAIAvailability} from '../site/ai-status.mjs';

test('optional AI metadata times out even if a fetcher ignores cancellation',async()=>{
  let signal;
  const result=await readAIAvailability((_url,options)=>{signal=options.signal;return new Promise(()=>{});},10);
  assert.equal(result,false);
  assert.equal(signal.aborted,true);
});

test('optional AI metadata also bounds a stalled response body',async()=>{
  assert.equal(await readAIAvailability(async()=>({ok:true,json:()=>new Promise(()=>{})}),10),false);
  assert.equal(await readAIAvailability(async()=>({ok:true,json:async()=>({available:true})}),1000),true);
  assert.equal(await readAIAvailability(async()=>({ok:false,json:()=>{throw Error('must not parse');}}),1000),false);
  assert.equal(await readAIAvailability(async()=>{throw Error('offline');},1000),false);
});

test('AI configuration metadata never sends a provider request or exposes credentials',async()=>{
  const dir=await mkdtemp(path.join(tmpdir(),'voltforge-ai-metadata-'));
  const previous=process.env.GEMINI_API_KEY,originalFetch=globalThis.fetch;
  try{
    await writeFile(path.join(dir,'package.json'),JSON.stringify({type:'module'}));
    await writeFile(path.join(dir,'_prompt.js'),'export const SCHEMA={}; export const SYSTEM="Synthetic test";');
    await copyFile(new URL('../site/api/ai.js',import.meta.url),path.join(dir,'ai.js'));
    const {default:handler}=await import(pathToFileURL(path.join(dir,'ai.js')));
    globalThis.fetch=()=>{throw new Error('Metadata must not make external calls');};
    const invoke=async(method)=>{
      const output={};
      const response={setHeader:(key,value)=>{output[key]=value;},
        status:code=>{output.status=code;return response;},json:value=>{output.body=value;return response;}};
      await handler({method,headers:{host:'localhost'},body:{}},response);return output;
    };
    delete process.env.GEMINI_API_KEY;
    assert.deepEqual((await invoke('GET')).body,{available:false,connection_verified:false});
    assert.equal((await invoke('POST')).status,503);
    process.env.GEMINI_API_KEY='synthetic-private-test-value';
    const configured=await invoke('GET');
    assert.deepEqual(configured.body,{available:true,connection_verified:false});
    assert.equal(configured['Cache-Control'],'no-store');
    assert.ok(!JSON.stringify(configured).includes('synthetic-private-test-value'));
  }finally{
    if(previous===undefined)delete process.env.GEMINI_API_KEY;else process.env.GEMINI_API_KEY=previous;
    globalThis.fetch=originalFetch;
    assert.equal(path.dirname(path.resolve(dir)),path.resolve(tmpdir()));
    assert.ok(path.basename(dir).startsWith('voltforge-ai-metadata-'));
    await rm(dir,{recursive:true,force:true});
  }
});
