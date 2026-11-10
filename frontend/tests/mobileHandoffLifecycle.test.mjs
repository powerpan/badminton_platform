import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
import * as vue from 'vue';
const script=fs.readFileSync(new URL('../src/components/MobileHandoffDialog.vue',import.meta.url),'utf8').match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1];
const code=ts.transpileModule(script+'\nexport {generate,poll,handoff,loading,error};',{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const defer=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const state=id=>({id,status:'waiting',order_id:7,expires_at:Date.now()/1000+120,pairing_code:null,username:'fixture',user_id:1});
function fixture(api){
 const visible=vue.ref(false),unmount=[],watches=[];
 const context={exports:{},defineModel:()=>visible,defineProps:()=>({orderId:7}),setInterval:()=>1,clearInterval:()=>{},Date,
  require:name=> name==='vue'?{...vue,onUnmounted:fn=>unmount.push(fn),watch:(...args)=>{const stop=vue.watch(...args);watches.push(stop);return stop;}}:name.includes('/api/')?api:{terminalHandoff:s=>['consumed','denied','failed'].includes(s)}};
 vm.runInNewContext(code,context);
 return {...context.exports,visible,dispose(){watches.forEach(fn=>fn());unmount.forEach(fn=>fn());}};
}
const flush=async()=>{await vue.nextTick();await Promise.resolve();await Promise.resolve();};
test('closing while QR creation is in flight cancels the late authorization',async()=>{
 const create=defer(),canceled=[];const f=fixture({createHandoff:()=>create.promise,decideHandoff:async(id,decision)=>{canceled.push([id,decision]);return {data:state(id)};}});
 f.visible.value=true;await flush();f.visible.value=false;await flush();create.resolve({data:state('late')});await flush();
 assert.equal(f.handoff.value,undefined);assert.deepEqual(canceled,[['late','cancel']]);f.dispose();
});
test('regenerating QR waits for cancellation and stops if cancellation failed',async()=>{
 const cancellation=defer();let created=0;
 const f=fixture({createHandoff:async()=>({data:state('qr-'+(++created))}),decideHandoff:()=>cancellation.promise});
 f.visible.value=true;await flush();assert.equal(created,1);
 const generating=f.generate();await flush();assert.equal(created,1);
 cancellation.reject(new Error('network lost'));await generating;
 assert.equal(created,1);assert.equal(f.handoff.value.id,'qr-1');f.dispose();
});
test('an old status response cannot restore a dialog after it closes',async()=>{
 const status=defer();const f=fixture({createHandoff:async()=>({data:state('qr-1')}),getHandoff:()=>status.promise,decideHandoff:async()=>({data:{}})});
 f.visible.value=true;await flush();const polling=f.poll();f.visible.value=false;await flush();
 status.resolve({data:{...state('qr-1'),status:'claimed',pairing_code:'123456'}});await polling;
 assert.equal(f.handoff.value,undefined);f.dispose();
});
