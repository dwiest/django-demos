const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function setup(responses) {
  const timers=[], nodes={};
  for (const id of ['#job-state','#job-stage','#job-poll-error']) {
    nodes[id]={textContent:''};
    Object.defineProperty(nodes[id], 'innerHTML', {set() {throw new Error('unsafe rendering');}});
  }
  const panel={dataset:{jobPoll:'/jobs/id/status/'}};
  let reloads=0, onhide;
  const context={document:{querySelector:key=>key==='[data-job-poll]'?panel:nodes[key]},
    window:{addEventListener:(name,fn)=>onhide=fn,setTimeout:fn=>timers.push(fn), location:{reload:()=>reloads++}},
    fetch:async(url,opts)=>{assert.equal(url,panel.dataset.jobPoll);assert.equal(opts.cache,'no-store');return responses.shift();}};
  vm.runInNewContext(fs.readFileSync('dwiest/django/demos/static/dwiest-django-demos/whisper/jobs.js','utf8'),context);
  return {nodes,timers,step:()=>timers.shift()(),hide:()=>onhide(),reloads:()=>reloads};
}
test('polling uses text rendering and stops/reloads on terminal state', async()=>{
  const run=setup([{ok:true,json:async()=>({job:{status:'running',stage:'<script>unsafe</script>'}})},
                   {ok:true,json:async()=>({job:{status:'completed',stage:'completed'}})}]);
  await run.step();
  assert.equal(run.nodes['#job-stage'].textContent,'Stage: <script>unsafe</script>');
  await run.step();
  assert.equal(run.reloads(),1);
  assert.equal(run.timers.length,0);
});
test('poll failures keep a recoverable status message and navigation stops polling', async()=>{
  const run=setup([{ok:false}]);
  await run.step();
  assert.match(run.nodes['#job-poll-error'].textContent,/session/);
  run.hide();
  await run.step();
  assert.equal(run.timers.length,0);
  assert.equal(run.reloads(),0);
});
