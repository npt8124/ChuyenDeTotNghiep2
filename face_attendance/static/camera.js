const video=document.getElementById('video');
const canvas=document.getElementById('canvas');
const statusBox=document.getElementById('status');
const detail=document.getElementById('detail');
const startBtn=document.getElementById('start');
const stopBtn=document.getElementById('stop');
let stream=null, active=false;
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function show(message,kind='secondary',info=''){
 statusBox.className='alert alert-'+kind;
 statusBox.textContent=message;
 detail.textContent=info;
}
async function loop(){
 while(active){
  if(video.readyState<2){await sleep(400);continue;}
  canvas.width=640;canvas.height=Math.round(video.videoHeight*640/video.videoWidth)||480;
  canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
  const image=canvas.toDataURL('image/jpeg',0.75);
  try{
   const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image})});
   const data=await response.json();
   if(!response.ok){show(data.error||'Lỗi xử lý','danger');}
   else if(data.label==='matched'){
    const msg=data.attendance==='recorded'?'Đã điểm danh': 'Đã điểm danh trước đó';
    show(msg,'success',`${data.name} (${data.code}) — cosine distance: ${data.distance}`);
   }else{show(data.message||'Unknown','warning',data.distance!==undefined?`Distance: ${data.distance}`:'');}
  }catch(err){show('Không kết nối được máy chủ: '+err.message,'danger');}
  await sleep(2000);
 }
}
startBtn.addEventListener('click',async()=>{
 try{
  stream=await navigator.mediaDevices.getUserMedia({video:{width:640,height:480},audio:false});
  video.srcObject=stream;active=true;startBtn.disabled=true;stopBtn.disabled=false;
  show('Đang nhận diện...','info');loop();
 }catch(err){show('Không mở được camera: '+err.message,'danger');}
});
stopBtn.addEventListener('click',()=>{
 active=false;if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}
 startBtn.disabled=false;stopBtn.disabled=true;show('Đã dừng camera.');
});
window.addEventListener('pagehide',()=>{active=false;if(stream)stream.getTracks().forEach(t=>t.stop());});
