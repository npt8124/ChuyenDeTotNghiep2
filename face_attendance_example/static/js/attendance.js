const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const classSelect = document.getElementById("classSelect");
const sessionSelect = document.getElementById("sessionSelect");
const resultsEl = document.getElementById("results");

let stream = null;
let timer = null;
let busy = false;

async function loadAttendanceOptions() {
    const students = await fetch(API.students).then(r => r.json());
    const classes = [...new Set(students.map(s => s.class_name))].sort();

    const options =
        `<option value="">-- Chọn lớp --</option>` +
        classes.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");

    classSelect.innerHTML = options;
    document.getElementById("newClassSelect").innerHTML = options;

    const today = new Date().toISOString().slice(0, 10);
    document.getElementById("sessionDate").value = today;

    await loadSessions();
}

async function loadSessions() {
    const sessions = await fetch(API.sessions).then(r => r.json());
    const className = classSelect.value;

    const filtered = className
        ? sessions.filter(s => s.class_name === className && s.status === "active")
        : sessions.filter(s => s.status === "active");

    sessionSelect.innerHTML =
        `<option value="">-- Chọn buổi học --</option>` +
        filtered.map(s =>
            `<option value="${s.id}">
                ${escapeHtml(s.class_name)} - ${s.session_date} ${s.start_time}
            </option>`
        ).join("");
}

classSelect.addEventListener("change", loadSessions);

document.getElementById("sessionForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    const data = {
        class_name: document.getElementById("newClassSelect").value,
        session_date: document.getElementById("sessionDate").value,
        start_time: document.getElementById("startTime").value,
        end_time: document.getElementById("endTime").value || null
    };

    const res = await fetch(API.sessions, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(data)
    });

    const json = await res.json();
    const el = document.getElementById("sessionCreateMessage");
    el.textContent = json.error || "Đã tạo buổi học.";
    el.className = res.ok ? "message success" : "message error";

    if (res.ok) {
        classSelect.value = data.class_name;
        await loadSessions();
        if (json.id) sessionSelect.value = json.id;
    }
});

document.getElementById("startBtn").onclick = async () => {
    if (!sessionSelect.value) {
        showMessage("Hãy chọn buổi học trước.", false);
        return;
    }

    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: {width: {ideal: 640}, height: {ideal: 480}},
            audio: false
        });
        video.srcObject = stream;
        timer = setInterval(sendFrame, 700);
        showMessage("Camera đang hoạt động.", true);
    } catch (err) {
        showMessage("Không mở được camera: " + err.message, false);
    }
};

document.getElementById("stopBtn").onclick = stopCamera;

async function sendFrame() {
    if (busy || !stream || !sessionSelect.value || video.readyState < 2) return;

    busy = true;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);

    const image = canvas.toDataURL("image/jpeg", 0.75);

    try {
        const res = await fetch(API.recognize, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                session_id: Number(sessionSelect.value),
                image
            })
        });

        const json = await res.json();

        if (!res.ok) {
            showMessage(json.error || "Recognition error", false);
            return;
        }

        renderResults(json.results || []);
    } catch (err) {
        showMessage("Lỗi kết nối: " + err.message, false);
    } finally {
        busy = false;
    }
}

function renderResults(results) {
    if (!results.length) {
        resultsEl.innerHTML = `<p class="muted">Chưa phát hiện khuôn mặt.</p>`;
        return;
    }

    resultsEl.innerHTML = results.map(r => `
        <div class="result ${r.recognized ? "known" : "unknown"}">
            <strong>${escapeHtml(r.full_name)}</strong>
            <span>Similarity: ${Number(r.similarity).toFixed(4)}</span>
            <span>${r.status}</span>
            ${r.recognized ? `<small>${r.already_present ? "Đã điểm danh trước đó" : "✓ Vừa điểm danh"} - ${r.check_in_time}</small>` : ""}
        </div>
    `).join("");
}

function showMessage(text, ok) {
    const el = document.getElementById("sessionMessage");
    el.textContent = text;
    el.className = ok ? "message success" : "message error";
}

function stopCamera() {
    if (timer) clearInterval(timer);
    timer = null;

    if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
    }

    video.srcObject = null;
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
        "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;"
    }[c]));
}

loadAttendanceOptions();
window.addEventListener("beforeunload", stopCamera);
