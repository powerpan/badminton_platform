import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
const source = fs.readFileSync(new URL('../src/api/http.ts', import.meta.url), 'utf8').replaceAll('import.meta.env.VITE_API_BASE_URL', 'undefined');
const code = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
function fixture() {
 const values=new Map([['bf_token','old-access'],['bf_refresh_token','old-refresh'],['bf_user','old-user']]);
 const localStorage={getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)};
 const clients=[];const navigations=[];const refreshRequests=[];let completeRefresh,rejectRefresh;
 const axios={create(){const client=config=>Promise.resolve(config);client.interceptors={request:{use(fn){client.request=fn;}},response:{use(ok,fail){client.fail=fail;}}};client.post=(url,body)=>{refreshRequests.push({url,body});return new Promise((resolve,reject)=>{completeRefresh=resolve;rejectRefresh=reject;});};clients.push(client);return client;}};
 const context={exports:{},require:name=>{assert.equal(name,'axios');return {default:axios};},localStorage,window:{location:{pathname:'/mobile-handoff/test',assign:path=>navigations.push(path)}}};
 vm.runInNewContext(code,context);
 const failure=(url='/shop/orders',config={})=>clients[0].fail({response:{status:401,data:{message:'expired'}},config:{url,headers:{Authorization:'Bearer old-access'},...config}});
 const switchAccount=()=>{localStorage.setItem('bf_token','phone-access');localStorage.setItem('bf_refresh_token','phone-refresh');localStorage.setItem('bf_user','phone-user');};
 return {values,failure,switchAccount,navigations,refreshRequests,reject:message=>rejectRefresh({response:{status:401,data:{message}}}),complete:()=>completeRefresh({data:{data:{access_token:'old-renewed',refresh_token:'old-rotated',user:{id:1}}}})};
}
test('a late 401 from the previous account cannot erase a phone login',async()=>{
 const f=fixture();f.switchAccount();await assert.rejects(f.failure());
 assert.equal(f.values.get('bf_token'),'phone-access');assert.equal(f.values.get('bf_user'),'phone-user');assert.deepEqual(f.navigations,[]);
});
test('an in-flight refresh cannot restore the old account after a phone handoff',async()=>{
 const f=fixture();const result=f.failure();f.switchAccount();f.complete();await assert.rejects(result);
 assert.equal(f.values.get('bf_token'),'phone-access');assert.equal(f.values.get('bf_refresh_token'),'phone-refresh');assert.deepEqual(f.navigations,[]);
});
test('an unchanged session still refreshes and retries the original request',async()=>{
 const f=fixture();const result=f.failure();f.complete();const retried=await result;
 assert.equal(f.values.get('bf_token'),'old-renewed');assert.equal(retried.headers.Authorization,'Bearer old-renewed');assert.deepEqual(f.navigations,[]);
});

test('protected auth endpoints refresh an expired access token and retry once',async()=>{
 for (const url of ['/auth/profile','/auth/password']) {
  const f=fixture();
  const result=f.failure(url).then(value=>({value}),error=>({error}));
  assert.equal(f.refreshRequests.length,1,`${url} must renew the session`);
  assert.equal(f.refreshRequests[0].body.refresh_token,'old-refresh');
  f.complete();
  const {value,error}=await result;
  assert.equal(error,undefined);
  assert.equal(value.url,url);
  assert.equal(value._retry,true);
  assert.equal(value.headers.Authorization,'Bearer old-renewed');
  assert.equal(f.values.get('bf_refresh_token'),'old-rotated');
  assert.deepEqual(f.navigations,[]);
 }
});

test('an expired or wrong-type refresh token clears the rejected session',async()=>{
 for (const message of ['登录已过期，请重新登录','刷新登录状态无效，请重新登录']) {
  const f=fixture();const result=f.failure();f.reject(message);
  await assert.rejects(result,error=>error.status===401);
  assert.equal(f.values.size,0);
  assert.equal(f.refreshRequests.length,1);
  assert.deepEqual(f.navigations,['/login']);
 }
});

test('a missing refresh token returns to login without a refresh request',async()=>{
 const f=fixture();f.values.delete('bf_refresh_token');
 await assert.rejects(f.failure(),error=>error.status===401);
 assert.equal(f.refreshRequests.length,0);
 assert.equal(f.values.size,0);
 assert.deepEqual(f.navigations,['/login']);
});

test('public authentication failures do not refresh or erase the current session',async()=>{
 for (const url of ['/auth/login','/auth/refresh','/auth/password-reset/confirm']) {
  const f=fixture();await assert.rejects(f.failure(url));
  assert.equal(f.refreshRequests.length,0);
  assert.equal(f.values.get('bf_token'),'old-access');
  assert.deepEqual(f.navigations,[]);
 }
});

test('a retried protected request returning 401 does not refresh in a loop',async()=>{
 const f=fixture();
 await assert.rejects(f.failure('/auth/profile',{_retry:true}));
 assert.equal(f.refreshRequests.length,0);
 assert.equal(f.values.size,0);
 assert.deepEqual(f.navigations,['/login']);
});

test('simultaneous 401 responses share one refresh request',async()=>{
 const f=fixture();const first=f.failure();const second=f.failure();
 assert.equal(f.refreshRequests.length,1);
 f.complete();
 for (const retried of await Promise.all([first,second])) {
  assert.equal(retried.headers.Authorization,'Bearer old-renewed');
 }
 assert.deepEqual(f.navigations,[]);
});
