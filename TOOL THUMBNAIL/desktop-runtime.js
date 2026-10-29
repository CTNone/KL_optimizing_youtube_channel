(() => {
  const listeners=[];
  globalThis.chrome ||= {};
  chrome.runtime={id:'desktop-studio',onMessage:{addListener:fn=>listeners.push(fn)},sendMessage:message=>globalThis.__studioBridge(message)};
  chrome.storage={local:{set:values=>globalThis.__studioBridge({type:'persist',values})}};
  globalThis.__studioRequest=message=>new Promise(resolve=>{
    for(const listener of listeners)listener(message,{id:'desktop-studio'},resolve);
  });
  globalThis.__desktopReference=reference=>globalThis.__studioBridge({type:'desktopAttach',reference});
})();
