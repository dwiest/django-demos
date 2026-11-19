const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
test('connection test stays on the form and does not clear or save the typed key',async()=>{
  let handler, sent;
  const form={action:'/ai/settings/',key:'test-unsaved-secret',addEventListener:(type,fn)=>handler=fn};
  const output={textContent:''};
  class Data {
    constructor(f){this.values={api_key:f.key,csrfmiddlewaretoken:'csrf'};}
    set(k,v){this.values[k]=v;}
  }
  const button={value:'test',disabled:false};
  vm.runInNewContext(fs.readFileSync('dwiest/django/demos/static/dwiest-django-demos/whisper/ai_settings.js','utf8'),{
    document:{querySelector:key=>key==='#ai-settings-form'?form:output},FormData:Data,
    fetch:async(url,args)=>{sent=args.body.values;return{json:async()=>({message:'Connection succeeded'})};},
    window:{location:{href:'/ai/settings/'}}
  });
  await handler({submitter:button,preventDefault(){}});
  assert.equal(sent.action,'test');
  assert.equal(sent.api_key,'test-unsaved-secret');
  assert.equal(form.key,'test-unsaved-secret');
  assert.equal(button.disabled,false);
  assert.equal(output.textContent,'Connection succeeded');
});
