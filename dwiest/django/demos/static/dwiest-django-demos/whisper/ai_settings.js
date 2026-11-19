(() => {
  const form=document.querySelector('#ai-settings-form');
  if(!form) return;
  const output=document.querySelector('#ai-test-result');
  form.addEventListener('submit',async event=>{
    const button=event.submitter;
    if(!button || button.value!=='test') return;
    event.preventDefault();
    const data=new FormData(form);
    data.set('action','test');
    button.disabled=true;
    output.textContent='Testing credentials and model visibility…';
    try {
      const response=await fetch(form.action || window.location.href,{method:'POST',credentials:'same-origin',redirect:'error',
        headers:{Accept:'application/json'},body:data});
      const result=await response.json();
      output.textContent=result.message || 'Connection test failed.';
    } catch (_) { output.textContent='The connection test could not complete. Check your session and retry.'; }
    finally { button.disabled=false; }
  });
})();
