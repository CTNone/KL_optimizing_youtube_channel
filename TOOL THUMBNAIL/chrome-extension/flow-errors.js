(() => {
  function classify(text) {
    const value = String(text || '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').toLowerCase().replace(/\s+/g,' ').trim();
    if (/(?:not enough|insufficient|out of|ran out of|no remaining)\s+(?:ai\s+)?credits?|credits?\s+(?:exhausted|depleted)|(?:khong du|het|da dung het|da su dung het)\s+(?:so\s+)?(?:tin dung|credits?)/.test(value)) return 'credit';
    if (/(?:violat\w*|against|does not comply|blocked by).{0,60}(?:polic\w*|guidelines)|(?:content|prompt|generation).{0,50}(?:blocked|not allowed|not permitted)|(?:vi pham|khong tuan thu).{0,60}(?:chinh sach|nguyen tac)|(?:noi dung|cau lenh|yeu cau).{0,50}(?:bi chan|khong duoc phep)|(?:couldn.t|cannot|can.t) generate.{0,60}(?:safety|policy)/.test(value)) return 'policy';
    if (/(?:too many requests|rate limit exceeded|qua nhieu yeu cau)/.test(value)) return 'rate_limit';
    if (/(?:model|mo hinh).{0,80}(?:usage limit|quota|limit reached|han muc|gioi han su dung)|(?:reached|exceeded).{0,40}(?:limit|quota).{0,60}(?:nano banana|imagen)|(?:dat|vuot|het).{0,30}(?:han muc|gioi han).{0,40}(?:mo hinh|nano banana|imagen)/.test(value)) return 'model_limit';
    if (/(?:generation failed|couldn.t generate|unable to generate|something went wrong|tao anh that bai|khong the tao anh|da xay ra loi)/.test(value)) return 'generation';
    return null;
  }
  function watch({visible, prompt = '', ignoreExisting = false}) {
    let error = null;
    const ignored = new WeakMap();
    for(const node of document.body.querySelectorAll('[role="alert"],[role="dialog"],[role="status"],[aria-live="assertive"],[data-sonner-toast],p,span,div')) {
      const text=(node.innerText || node.textContent || '').trim();
      // A notice from the previous generation must not fail the first attempt.
      // Account-credit blocks remain actionable even after F5.
      if(visible(node) && classify(text)!=='credit' && (ignoreExisting || classify(text)))ignored.set(node,text);
    }
    const inspect = (element, liveOnly = false) => {
      if(error || !element?.querySelectorAll) return;
      const selectors = '[role="alert"], [role="dialog"], [role="status"], [aria-live="assertive"], [data-sonner-toast]';
      const candidates = liveOnly ? [...element.querySelectorAll(selectors)] : [element,...element.querySelectorAll('p,span,div,'+selectors)].slice(0,200);
      for(const node of candidates) {
        if(ignored.has(node) && ignored.get(node)===(node.innerText || node.textContent || '').trim())continue;
        if(!visible(node) || node.closest?.('textarea,input,[contenteditable="true"],[data-flow-txt-overlay]')) continue;
        const text = (node.innerText || node.textContent || '').trim();
        if(!text || text.length > 800 || (prompt && (text === prompt || text.includes(prompt)))) continue;
        const kind = classify(text);
        if(kind) { error = {kind,text:text.slice(0,500)}; break; }
      }
    };
    inspect(document.body,true);
    const observer = new MutationObserver(records => {
      for(const record of records) {
        if(record.type === 'characterData') inspect(record.target.parentElement);
        else for(const node of record.addedNodes) {const element=node.nodeType === 3 ? node.parentElement : node;inspect(element);}
      }
    });
    observer.observe(document.body,{subtree:true,childList:true,characterData:true});
    return {check() {
      inspect(document.body,true);
      if(error) {
        const labels = {credit:'Flow báo không đủ credit tài khoản.',policy:'Flow từ chối nội dung theo chính sách.',rate_limit:'Flow báo quá nhiều yêu cầu.',model_limit:'Flow báo mô hình đạt hạn mức sử dụng.',generation:'Flow báo tạo ảnh không thành công.'};
        const failure = new Error(labels[error.kind] + ' Thông báo: ' + error.text);
        failure.code = 'blocked_' + error.kind;
        failure.flowMessage = error.text;
        throw failure;
      }
    },disconnect(){observer.disconnect();}};
  }
  globalThis.FlowErrors = {classify,watch};
})();
