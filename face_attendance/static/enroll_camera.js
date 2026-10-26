const video = document.getElementById('enroll-video');
const canvas = document.getElementById('enroll-canvas');
const preview = document.getElementById('enroll-preview');
const msg = document.getElementById('enroll-message');
const start = document.getElementById('enroll-start');
const capture = document.getElementById('enroll-capture');
const retake = document.getElementById('enroll-retake');
const save = document.getElementById('enroll-save');
const stop = document.getElementById('enroll-stop');
let stream = null;
let photo = null;
function message(text, kind='secondary') {
  msg.className = `alert alert-${kind} mt-3 mb-0`;
  msg.textContent = text;
}
function stopCamera() {
  if (stream) stream.getTracks().forEach(track => track.stop());
  stream = null;
  video.srcObject = null;
  start.disabled = false;
  capture.disabled = true;
  stop.disabled = true;
}
start.addEventListener('click', async () => {
  try {
    stream = await navigator.mediaDevices.getUserMedia({video:{width:1280,height:720,facingMode:'user'},audio:false});
    video.srcObject = stream;
    await video.play();
    start.disabled = true;
    stop.disabled = false;
    capture.disabled = false;
    photo = null;
    preview.style.display = 'none';
    video.style.display = 'block';
    save.disabled = true;
    retake.disabled = true;
    message('Camera đã sẵn sàng. Đặt một khuôn mặt vào khung hình rồi bấm Chụp ảnh.', 'info');
  } catch (err) { message('Không mở được camera: ' + err.message, 'danger'); }
});
capture.addEventListener('click', () => {
  if (!stream || !video.videoWidth) return message('Camera chưa sẵn sàng.', 'warning');
  const width = Math.min(video.videoWidth, 960);
  canvas.width = width;
  canvas.height = Math.round(width * video.videoHeight / video.videoWidth);
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
  photo = canvas.toDataURL('image/jpeg', 0.9);
  preview.src = photo;
  preview.style.display = 'block';
  video.style.display = 'none';
  capture.disabled = true;
  retake.disabled = false;
  save.disabled = false;
  message('Đã chụp. Kiểm tra ảnh và bấm Lưu khuôn mặt hoặc Chụp lại.', 'info');
});
retake.addEventListener('click', () => {
  photo = null;
  preview.style.display = 'none';
  video.style.display = 'block';
  capture.disabled = !stream;
  retake.disabled = true;
  save.disabled = true;
  message('Hãy chụp lại ảnh mới.', 'info');
});
save.addEventListener('click', async () => {
  if (!photo) return;
  save.disabled = true;
  message('Đang phát hiện khuôn mặt và tạo embedding, vui lòng chờ...', 'info');
  try {
    const response = await fetch(enrollEndpoint, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({image:photo})
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Đăng ký thất bại.');
    message(result.message, 'success');
    stopCamera();
    setTimeout(() => location.reload(), 900);
  } catch (err) {
    message(err.message, 'danger');
    save.disabled = false;
  }
});
stop.addEventListener('click', () => {
  stopCamera();
  message('Đã tắt camera.');
});
window.addEventListener('pagehide', stopCamera);
