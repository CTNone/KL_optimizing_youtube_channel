(() => {
  const interactive='button,[role="button"],[role="combobox"],[role="menuitemradio"],[role="radio"],a[href],input,textarea,[role="menuitem"],[role="option"]';
  function owner(element) {
    if(globalThis.FlowModels?.isOption(element))return element;
    const semantic=element.closest?.(interactive);
    if(semantic)return semantic;
    if(element.tagName==='IMG') {
      // Flow renders image hover overlays as siblings of <img>. Clicking
      // their shared image wrapper opens the same asset, unless a toolbar
      // control or an unrelated overlay is under the pointer.
      let parent=element.parentElement;
      let candidate=element;
      const bounds=element.getBoundingClientRect();
      for(let i=0;i<6 && parent;i++,parent=parent.parentElement) {
        if(['BODY','HTML'].includes(parent.tagName))break;
        if(parent.querySelectorAll?.('img').length!==1)break;
        const box=parent.getBoundingClientRect?.();
        if(box && (box.right-box.left>(bounds.right-bounds.left)*1.5+80 || box.bottom-box.top>(bounds.bottom-bounds.top)*1.5+120))break;
        if(parent.contains(element))candidate=parent;
      }
      return candidate;
    }
    return element;
  }
  function point(element,{document,visible,width,height}) {
    const target=owner(element);
    if(!element?.isConnected || !target?.isConnected || !visible(element) || target.disabled || target.getAttribute('aria-disabled')==='true')throw Object.assign(new Error('Điều khiển đã thay đổi hoặc đang bị khóa. Chưa bấm.'),{code:'click_not_sent'});
    const r=element.getBoundingClientRect();
    // Retain the first unobstructed point. A tooltip may cover the center
    // while the rest of the same control is safe to click.
    for(const [fx,fy] of [[.5,.5],[.25,.5],[.75,.5],[.5,.25],[.5,.75],[.25,.25],[.75,.75]]) {
      const x=r.left+(r.right-r.left)*fx,y=r.top+(r.bottom-r.top)*fy;
      if(x<0 || y<0 || x>=width || y>=height)continue;
      const hit=document.elementFromPoint(x,y);
      if(!hit || (hit!==target && !target.contains(hit)))continue;
      const nested=hit.closest?.(interactive);
      if(nested && (nested.disabled || nested.getAttribute('aria-disabled')==='true'))continue;
      if(nested && nested!==target && !target.contains(nested) && !nested.contains?.(target))continue;
      if(nested && nested!==target && target.contains(nested)) {
        const children=target.querySelectorAll?.('button,[role="button"]') || [];
        const delegated=['option','menuitem','menuitemradio','radio','combobox'].includes(target.getAttribute('role')) && children.length===1 && children[0]===nested;
        if(!delegated)continue;
      }
      return {x,y};
    }
    throw Object.assign(new Error('Không tìm được điểm bấm trống trên điều khiển hiện tại. Một lớp giao diện khác đang che; chưa bấm.'),{code:'click_not_sent'});
  }
  globalThis.FlowClicks={owner,point};
})();
