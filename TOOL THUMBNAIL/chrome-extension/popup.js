const status = document.getElementById('status');
const button = document.getElementById('connect');
let tabId;
(async () => {
  try {
    status.textContent = 'Tool sẽ tìm duy nhất một tab Google Flow trong Chrome. Không cần đang đứng ở tab Flow.';
    button.textContent = 'Kết nối tab Flow duy nhất';
    button.disabled = false;
  } catch(error) { status.textContent = error.message; }
})();
button.onclick = async () => {
  button.disabled = true;
  try {
    const result = await chrome.runtime.sendMessage({type:'connect',tabId});
    if(result?.error) throw new Error(result.error);
    window.close();
  } catch(error) { status.textContent = error.message; button.disabled = false; }
};
// Windows shortcut opens this same extension page in Chrome app mode.
// Keep the retry UI visible if Flow is absent or multiple projects are open.
if(new URLSearchParams(location.search).get('desktop')==='1')void button.onclick();
