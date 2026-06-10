const $ = (id) => document.getElementById(id);

let currentInfo = null;

function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }

function showError(msg) {
  $("error").textContent = msg;
  show($("error"));
}

$("url-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  hide($("error"));
  hide($("info"));
  hide($("progress-section"));
  try {
    const resp = await fetch("/api/info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: $("url").value }),
    });
    if (!resp.ok) throw new Error((await resp.json()).detail || "Failed to fetch info");
    currentInfo = await resp.json();
    renderInfo(currentInfo);
  } catch (err) {
    showError(err.message);
  }
});

function renderInfo(info) {
  $("title").textContent = info.title;
  if (info.thumbnail) { $("thumb").src = info.thumbnail; show($("thumb")); }
  $("meta").textContent = info.is_playlist
    ? `Playlist · ${info.entries_count} videos`
    : (info.duration ? `${Math.floor(info.duration / 60)}m ${info.duration % 60}s` : "");

  const res = $("resolution");
  res.innerHTML = "";
  const heights = info.available_heights.length ? info.available_heights : [1080, 720, 480];
  for (const h of heights) {
    const opt = document.createElement("option");
    opt.value = h; opt.textContent = `${h}p`;
    res.appendChild(opt);
  }
  show($("info"));
}

document.querySelectorAll('input[name="kind"]').forEach((r) =>
  r.addEventListener("change", () => {
    const isVideo = document.querySelector('input[name="kind"]:checked').value === "video";
    $("video-opts").classList.toggle("hidden", !isVideo);
    $("audio-opts").classList.toggle("hidden", isVideo);
  })
);

$("subtitles").addEventListener("change", (e) =>
  $("sub-lang-wrap").classList.toggle("hidden", !e.target.checked)
);

$("download-btn").addEventListener("click", async () => {
  hide($("error"));
  const kind = document.querySelector('input[name="kind"]:checked').value;
  const payload = {
    url: $("url").value,
    kind,
    resolution: kind === "video" ? parseInt($("resolution").value, 10) : null,
    bitrate: kind === "audio" ? parseInt($("bitrate").value, 10) : null,
    audio_format: $("audio_format").value,
    subtitles: $("subtitles").checked,
    sub_lang: $("sub_lang").value || "en",
  };
  try {
    const resp = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) throw new Error("Failed to start download");
    const { job_id } = await resp.json();
    trackProgress(job_id);
  } catch (err) {
    showError(err.message);
  }
});

function trackProgress(jobId) {
  show($("progress-section"));
  $("bar-fill").style.width = "0%";
  $("status-text").textContent = "Starting…";
  const es = new EventSource(`/api/progress/${jobId}`);
  es.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.status === "downloading") {
      $("bar-fill").style.width = `${data.progress}%`;
      $("status-text").textContent = `Downloading… ${data.progress}%`;
    } else if (data.status === "done") {
      $("bar-fill").style.width = "100%";
      $("status-text").textContent = "Done! Downloading file…";
      es.close();
      window.location.href = `/api/file/${jobId}`;
    } else if (data.status === "error") {
      es.close();
      showError(data.error || "Download failed");
      hide($("progress-section"));
    }
  };
  es.onerror = () => { es.close(); };
}
