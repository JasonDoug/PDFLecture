// App State
const state = {
    jobId: null,
    status: 'idle', // idle, uploading, processing, ready, error
    currentSectionIndex: 0,
    sections: [], // { section_id, title, audioUrl, timestampsUrl, scriptText, timestamps }
    audioContext: {
        isPlaying: false,
        duration: 0,
        currentTime: 0
    }
};

// DOM Elements
const views = {
    upload: document.getElementById('upload-view'),
    processing: document.getElementById('processing-view'),
    player: document.getElementById('player-view')
};

const dom = {
    dropZone: document.getElementById('drop-zone'),
    fileInput: document.getElementById('file-input'),
    uploadLoading: document.getElementById('upload-loading'),
    progressBar: document.getElementById('progress-bar'),
    progressMessage: document.getElementById('progress-message'),
    progressPercent: document.getElementById('progress-percent'),
    steps: {
        upload: document.getElementById('step-upload'),
        analyze: document.getElementById('step-analyze'),
        script: document.getElementById('step-script'),
        audio: document.getElementById('step-audio')
    },
    audio: document.getElementById('audio-element'),
    playBtn: document.getElementById('btn-play'),
    seekSlider: document.getElementById('seek-slider'),
    currentTime: document.getElementById('current-time'),
    totalTime: document.getElementById('total-time'),
    tocList: document.getElementById('toc-list'),
    transcriptContent: document.getElementById('transcript-content'),
    sectionTitle: document.getElementById('current-section-title')
};

// Initialization
function init() {
    setupEventListeners();
    checkUrlParams();
}

function setupEventListeners() {
    // Upload Interaction
    dom.dropZone.addEventListener('click', () => dom.fileInput.click());
    dom.dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dom.dropZone.classList.add('drag-over');
    });
    dom.dropZone.addEventListener('dragleave', () => dom.dropZone.classList.remove('drag-over'));
    dom.dropZone.addEventListener('drop', handleDrop);
    dom.fileInput.addEventListener('change', handleFileSelect);

    // Audio Controls
    dom.playBtn.addEventListener('click', togglePlay);
    dom.audio.addEventListener('timeupdate', updateTime);
    dom.audio.addEventListener('ended', handleAudioEnded);
    dom.audio.addEventListener('loadedmetadata', () => {
        dom.totalTime.textContent = formatTime(dom.audio.duration);
    });

    dom.seekSlider.addEventListener('input', (e) => {
        const time = (e.target.value / 100) * dom.audio.duration;
        dom.audio.currentTime = time;
    });

    document.getElementById('btn-prev').addEventListener('click', playPreviousSection);
    document.getElementById('btn-next').addEventListener('click', playNextSection);
    document.getElementById('speed-select').addEventListener('change', (e) => {
        dom.audio.playbackRate = parseFloat(e.target.value);
    });
}

function checkUrlParams() {
    const params = new URLSearchParams(window.location.search);
    const jobId = params.get('jobId');
    if (jobId) {
        state.jobId = jobId;
        startPolling();
    }
}

// Upload Handling
async function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) uploadFile(file);
}

function handleDrop(e) {
    e.preventDefault();
    dom.dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && file.type === 'application/pdf') {
        uploadFile(file);
    } else {
        alert('Please upload a PDF file.');
    }
}

async function uploadFile(file) {
    switchView('processing');
    updateProgress(0, 'Uploading PDF...');

    document.getElementById('proc-filename').textContent = file.name;
    document.getElementById('proc-size').textContent = (file.size / (1024 * 1024)).toFixed(2) + ' MB';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(CONFIG.API_ENDPOINTS.UPLOAD, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('Upload failed');

        const data = await response.json();
        state.jobId = data.jobId;

        // Update URL without reload
        const newUrl = window.location.protocol + "//" + window.location.host + window.location.pathname + '?jobId=' + state.jobId;
        window.history.pushState({ path: newUrl }, '', newUrl);

        markStepComplete('upload');
        startPolling();

    } catch (error) {
        console.error(error);
        alert('Error uploading file: ' + error.message);
        switchView('upload');
    }
}

// Polling Logic
function startPolling() {
    if (state.interval) clearInterval(state.interval);

    switchView('processing');

    state.interval = setInterval(async () => {
        try {
            const response = await fetch(`${CONFIG.API_ENDPOINTS.STATUS}?jobId=${state.jobId}`);
            const data = await response.json();

            updateStatusUI(data);

            if (data.status === 'completed') {
                clearInterval(state.interval);
                initializePlayer(data);
            } else if (data.status === 'failed') {
                clearInterval(state.interval);
                alert('Processing failed: ' + (data.progress?.message || 'Unknown error'));
            }

        } catch (error) {
            console.error('Polling error:', error);
        }
    }, CONFIG.POLL_INTERVAL);
}

function updateStatusUI(data) {
    const stageMap = {
        'uploaded': 10,
        'analyzing': 20,
        'analyzed': 30,
        'generating_script': 40,
        'script_generated': 60,
        'generating_audio': 70,
        'completed': 100
    };

    const pct = data.progress?.percentage || stageMap[data.status] || 0;
    updateProgress(pct, data.progress?.message || 'Processing...');

    if (pct >= 10) markStepComplete('upload');
    if (pct >= 30) markStepComplete('analyze');
    if (pct >= 60) markStepComplete('script');
    if (pct >= 100) markStepComplete('audio');
}

function updateProgress(percent, message) {
    dom.progressBar.style.width = `${percent}%`;
    dom.progressPercent.textContent = `${percent}%`;
    dom.progressMessage.textContent = message;
}

function markStepComplete(stepId) {
    dom.steps[stepId].classList.add('completed');
}

// Player Logic
async function initializePlayer(jobData) {
    state.sections = jobData.audio.sections;
    state.status = 'ready';

    // Setup ToC
    renderToC();

    // Load first section
    await loadSection(0);

    switchView('player');
}

function renderToC() {
    dom.tocList.innerHTML = '';
    state.sections.forEach((section, index) => {
        const li = document.createElement('li');
        li.className = 'toc-item';
        if (index === 0) li.classList.add('active');

        li.innerHTML = `
            <div class="toc-title">Section ${section.section_id}</div>
            <div class="toc-sub">${formatTime(section.duration)}</div>
        `;
        li.onclick = () => loadSection(index);
        dom.tocList.appendChild(li);
    });
}

async function loadSection(index) {
    if (index < 0 || index >= state.sections.length) return;

    state.currentSectionIndex = index;
    const section = state.sections[index];

    // Update active ToC
    document.querySelectorAll('.toc-item').forEach((el, i) => {
        el.classList.toggle('active', i === index);
    });

    // Load Audio
    dom.audio.src = section.audioUrl;
    dom.sectionTitle.textContent = `Section ${section.section_id}`;

    // Load Timestamps/Script
    try {
        const resp = await fetch(section.timestampsUrl);
        const timestamps = await resp.json();
        section.timestamps = timestamps;
        renderTranscript(timestamps);
    } catch (e) {
        console.error("Error loading transcript", e);
        dom.transcriptContent.textContent = "Transcript unavailable.";
    }

    // Reset player UI
    dom.seekSlider.value = 0;
    dom.currentTime.textContent = "0:00";
    if (state.audioContext.isPlaying) dom.audio.play();
}

function renderTranscript(timestamps) {
    dom.transcriptContent.innerHTML = '';
    timestamps.forEach((ts, i) => {
        const span = document.createElement('span');
        span.textContent = ts.word + " ";
        span.className = 'word';
        span.id = `word-${i}`;
        span.onclick = () => {
            dom.audio.currentTime = ts.start;
            dom.audio.play();
        };
        dom.transcriptContent.appendChild(span);
    });
}

function updateTime() {
    const time = dom.audio.currentTime;
    dom.currentTime.textContent = formatTime(time);

    if (dom.audio.duration) {
        dom.seekSlider.value = (time / dom.audio.duration) * 100;
    }

    // Highlight words
    const section = state.sections[state.currentSectionIndex];
    if (section && section.timestamps) {
        // Simple search (could be optimized)
        section.timestamps.forEach((ts, i) => {
            const el = document.getElementById(`word-${i}`);
            if (el) {
                if (time >= ts.start && time < ts.end) {
                    el.classList.add('active');
                    // Auto scroll
                    if (i % 10 === 0) { // Throttle scrolling
                        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                } else {
                    el.classList.remove('active');
                    if (time > ts.end) el.classList.add('spoken');
                    else el.classList.remove('spoken');
                }
            }
        });
    }
}

function togglePlay() {
    if (dom.audio.paused) {
        dom.audio.play();
        dom.playBtn.textContent = '⏸';
        state.audioContext.isPlaying = true;
    } else {
        dom.audio.pause();
        dom.playBtn.textContent = '▶';
        state.audioContext.isPlaying = false;
    }
}

function handleAudioEnded() {
    if (state.currentSectionIndex < state.sections.length - 1) {
        playNextSection();
    } else {
        dom.playBtn.textContent = '▶';
        state.audioContext.isPlaying = false;
    }
}

function playNextSection() {
    loadSection(state.currentSectionIndex + 1);
}

function playPreviousSection() {
    loadSection(state.currentSectionIndex - 1);
}

// Utilities
function switchView(viewName) {
    Object.values(views).forEach(el => el.classList.remove('active'));
    views[viewName].classList.add('active');
}

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Start
init();
