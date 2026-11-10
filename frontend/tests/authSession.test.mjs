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
 const clients=[];const navigations=[];let completeRefresh;
 const axios={create(){const client=config=>Promise.resolve(config);client.interceptors={request:{use(fn){client.request=fn;}},response:{use(ok,fail){client.fail=fail;}}};client.post=()=>new Promise(resolve=>{completeRefresh=resolve;});clients.push(client);return client;}};
 const context={exports:{},require:name=>{assert.equal(name,'axios');return {default:axios};},localStorage,window:{location:{pathname:'/mobile-handoff/test',assign:path=>navigations.push(path)}}};
 vm.runInNewContext(code,context);
 const failure=()=>clients[0].fail({response:{status:401,data:{message:'expired'}},config:{url:'/shop/orders',headers:{Authorization:'Bearer old-access'}}});
 const switchAccount=()=>{localStorage.setItem('bf_token','phone-access');localStorage.setItem('bf_refresh_token','phone-refresh');localStorage.setItem('bf_user','phone-user');};
 return {values,failure,switchAccount,navigations,complete:()=>completeRefresh({data:{data:{access_token:'old-renewed',refresh_token:'old-rotated',user:{id:1}}}})};
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
