// A persistent port keeps the OS-selected directory in the native process.
globalThis.NativeFiles = {
  connect() {
    if(this.port)return;
    const port=chrome.runtime.connectNative('com.flowtxt.files');
    this.port=port;this.pending=new Map();
    port.onMessage.addListener(message=>{
      const job=this.pending.get(message.id);if(!job)return;
      this.pending.delete(message.id);
      message.error ? job.reject(new Error(message.error)) : job.resolve(message);
    });
    port.onDisconnect.addListener(()=>{
      const reason=chrome.runtime.lastError?.message || 'Bộ lưu Windows đã ngắt kết nối. Chọn lại thư mục.';
      for(const job of this.pending.values())job.reject(new Error(reason));
      this.pending.clear();this.port=null;this.directory=null;
    });
  },
  request(message) {
    this.connect();
    const id=crypto.randomUUID();
    return new Promise((resolve,reject)=>{
      this.pending.set(id,{resolve,reject});
      try {this.port.postMessage({...message,id});}
      catch(error){this.pending.delete(id);reject(error);}
    });
  },
  async choose() {
    const result=await this.request({type:'choose'});
    if(!result.cancelled)this.directory=result.path;
    return result;
  },
  async write(path,data) {
    if(!this.directory)throw new Error('Chọn thư mục Windows trước khi lưu.');
    return this.request({type:'write',path,data});
  },
  async importImage(path,source) {
    if(!this.directory)throw new Error('Chọn thư mục Windows trước khi lưu.');
    return this.request({type:'import',path,source});
  },
  async readImage(source,withData=false) {
    const image=await this.request({type:'inspect',source});
    return this.imageData(image,withData);
  },
  async cropImage(source,persist=false) {
    const image=await this.request({type:'crop',source,persist});
    return this.imageData(image,!persist);
  },
  async imageData(image,withData) {
    if(withData) {
      const parts=[];
      for(let offset=0;offset<image.size;) {
        const part=await this.request({type:'chunk',token:image.token,offset});
        parts.push(Uint8Array.from(atob(part.base64),c=>c.charCodeAt(0)));offset+=part.length;
      }
      const blob=new Blob(parts,{type:'image/'+(image.ext==='jpg'?'jpeg':image.ext)});
      image.data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('Không đọc được dữ liệu file trên máy.'));reader.readAsDataURL(blob);});
    }
    return image;
  }
};
