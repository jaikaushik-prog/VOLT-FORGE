// Optional metadata must never hold the manual simulator's startup indefinitely.
export async function readAIAvailability(fetcher=fetch,timeoutMs=2000) {
  const controller=new AbortController();
  let timer;
  const expired=new Promise(resolve=>{timer=setTimeout(()=>{controller.abort();resolve(false);},timeoutMs);});
  const request=Promise.resolve().then(()=>fetcher('/api/ai',{
    method:'GET',cache:'no-store',signal:controller.signal
  })).then(async response=>response.ok&&(await response.json()).available===true).catch(()=>false);
  try{return await Promise.race([request,expired]);}
  finally{clearTimeout(timer);controller.abort();}
}
