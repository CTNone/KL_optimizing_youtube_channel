globalThis.FlowFiles = {
  async write(directory, path, data) {
    const job = (this.pending || Promise.resolve()).catch(()=>{}).then(()=>this.writeOne(directory,path,data));
    this.pending = job;
    return job;
  },
  async writeOne(directory, path, data) {
    if(!directory) throw new Error('Chưa chọn thư mục lưu ảnh trong bảng điều khiển.');
    const match = /^(run_[\d_-]+)\/(\d{4,}_\d{2}(?:_16x9)?\.(?:png|jpg|webp|avif))$/.exec(path || '');
    if(!match || !/^data:image\/(png|jpeg|webp|avif);base64,/.test(data || '') || data.length > 30*1024*1024) throw new Error('Dữ liệu lưu ảnh không hợp lệ.');
    const blob = await (await fetch(data)).blob();
    if(!blob.size) throw new Error('Ảnh rỗng.');
    const subfolder = await directory.getDirectoryHandle(match[1],{create:true});
    let name = match[2], available = false;
    for(let index = 0; index < 10000; index++) {
      name = index ? match[2].replace(/(\.[^.]+)$/,` (${index})$1`) : match[2];
      try { await subfolder.getFileHandle(name); }
      catch(e) { if(e.name !== 'NotFoundError') throw e; available = true; break; }
    }
    if(!available) throw new Error('Có quá nhiều file trùng tên. Hãy chọn thư mục khác.');
    const file = await subfolder.getFileHandle(name,{create:true});
    const stream = await file.createWritable();
    try { await stream.write(blob); await stream.close(); }
    catch(e) { await stream.abort().catch(()=>{}); throw e; }
    if((await file.getFile()).size !== blob.size) throw new Error('Kích thước file lưu không khớp.');
    return directory.name+'/'+match[1]+'/'+name;
  }
};
