(function () {
  'use strict';

  const state = {
    jdMode: 'sample',
    jdFile: null,
    resumeFiles: [],
  };

  // ---------------------------------------------------------------------
  // Status pill
  // ---------------------------------------------------------------------
  fetch('/api/status')
    .then((r) => r.json())
    .then((data) => {
      const pill = document.getElementById('statusPill');
      const text = document.getElementById('statusText');
      const modelTag = document.getElementById('modelTag');
      if (data.llm_configured) {
        pill.classList.add('live');
        text.textContent = 'Groq engine connected — ' + data.model;
      } else {
        pill.classList.add('fallback');
        text.textContent = 'No GROQ_API_KEY — heuristic fallback mode';
      }
      modelTag.textContent = data.model;
    })
    .catch(() => {
      document.getElementById('statusText').textContent = 'Status unavailable';
    });

  // ---------------------------------------------------------------------
  // Sample JD preview
  // ---------------------------------------------------------------------
  fetch('/api/sample-jd')
    .then((r) => r.json())
    .then((data) => {
      document.getElementById('samplePreview').textContent = data.text || 'No sample JD found.';
    })
    .catch(() => {
      document.getElementById('samplePreview').textContent = 'Could not load sample job description.';
    });

  // ---------------------------------------------------------------------
  // Tabs
  // ---------------------------------------------------------------------
  const tabBtns = document.querySelectorAll('.tab-btn');
  tabBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      tabBtns.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.tab;
      state.jdMode = tab;
      document.querySelectorAll('.tab-panel').forEach((p) => {
        p.classList.toggle('active', p.dataset.panel === tab);
      });
    });
  });

  // ---------------------------------------------------------------------
  // JD upload dropzone
  // ---------------------------------------------------------------------
  const jdDropzone = document.getElementById('jdDropzone');
  const jdFileInput = document.getElementById('jdFileInput');
  const jdFileList = document.getElementById('jdFileList');

  function renderJdFile() {
    jdFileList.innerHTML = '';
    if (!state.jdFile) return;
    const li = document.createElement('li');
    li.innerHTML = `<span class="name">${state.jdFile.name}</span>`;
    const btn = document.createElement('button');
    btn.textContent = '✕';
    btn.addEventListener('click', () => {
      state.jdFile = null;
      jdFileInput.value = '';
      renderJdFile();
    });
    li.appendChild(btn);
    jdFileList.appendChild(li);
  }

  jdDropzone.addEventListener('click', () => jdFileInput.click());
  jdFileInput.addEventListener('change', () => {
    if (jdFileInput.files.length) {
      state.jdFile = jdFileInput.files[0];
      renderJdFile();
    }
  });
  ['dragover', 'dragleave', 'drop'].forEach((evt) => {
    jdDropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      jdDropzone.classList.toggle('dragover', evt === 'dragover');
    });
  });
  jdDropzone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files.length) {
      state.jdFile = e.dataTransfer.files[0];
      renderJdFile();
    }
  });

  // ---------------------------------------------------------------------
  // Resume upload dropzone (multi-file)
  // ---------------------------------------------------------------------
  const resumeDropzone = document.getElementById('resumeDropzone');
  const resumeFileInput = document.getElementById('resumeFileInput');
  const resumeFileList = document.getElementById('resumeFileList');
  const resumeSampleNote = document.getElementById('resumeSampleNote');

  function renderResumeFiles() {
    resumeFileList.innerHTML = '';
    resumeSampleNote.style.display = state.resumeFiles.length ? 'none' : 'block';
    state.resumeFiles.forEach((file, idx) => {
      const li = document.createElement('li');
      li.innerHTML = `<span class="name">${file.name}</span>`;
      const btn = document.createElement('button');
      btn.textContent = '✕';
      btn.addEventListener('click', () => {
        state.resumeFiles.splice(idx, 1);
        renderResumeFiles();
      });
      li.appendChild(btn);
      resumeFileList.appendChild(li);
    });
  }

  function addResumeFiles(fileList) {
    Array.from(fileList).forEach((f) => state.resumeFiles.push(f));
    renderResumeFiles();
  }

  resumeDropzone.addEventListener('click', () => resumeFileInput.click());
  resumeFileInput.addEventListener('change', () => {
    addResumeFiles(resumeFileInput.files);
    resumeFileInput.value = '';
  });
  ['dragover', 'dragleave', 'drop'].forEach((evt) => {
    resumeDropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      resumeDropzone.classList.toggle('dragover', evt === 'dragover');
    });
  });
  resumeDropzone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files.length) addResumeFiles(e.dataTransfer.files);
  });

  // ---------------------------------------------------------------------
  // Terminal helpers
  // ---------------------------------------------------------------------
  const terminal = document.getElementById('terminal');
  const progressFill = document.getElementById('progressFill');
  const progressLabel = document.getElementById('progressLabel');
  const progressPct = document.getElementById('progressPct');

  function logLine(text, cls) {
    const span = document.createElement('span');
    span.className = 'line' + (cls ? ' ' + cls : '');
    span.textContent = text;
    terminal.appendChild(span);
    terminal.scrollTop = terminal.scrollHeight;
  }

  function clearTerminal() {
    terminal.innerHTML = '';
  }

  function setProgress(done, total) {
    const pct = total ? Math.round((done / total) * 100) : 0;
    progressFill.style.width = pct + '%';
    progressLabel.textContent = `${done} / ${total} processed`;
    progressPct.textContent = pct + '%';
  }

  function showError(message) {
    const banner = document.getElementById('errorBanner');
    banner.textContent = message;
    banner.classList.add('show');
  }

  function hideError() {
    document.getElementById('errorBanner').classList.remove('show');
  }

  // ---------------------------------------------------------------------
  // Run flow: prepare -> SSE stream -> redirect to results
  // ---------------------------------------------------------------------
  const runBtn = document.getElementById('runBtn');

  runBtn.addEventListener('click', () => {
    hideError();
    clearTerminal();
    setProgress(0, 0);
    runBtn.disabled = true;
    runBtn.textContent = 'Preparing…';

    const form = new FormData();
    form.append('jd_mode', state.jdMode);

    if (state.jdMode === 'paste') {
      form.append('jd_text', document.getElementById('jdTextarea').value);
    } else if (state.jdMode === 'upload') {
      if (!state.jdFile) {
        runBtn.disabled = false;
        runBtn.textContent = 'Run screening →';
        showError('Please choose a job description file to upload, or switch to the Sample / Paste tab.');
        return;
      }
      form.append('jd_file', state.jdFile);
    }

    state.resumeFiles.forEach((f) => form.append('resumes', f));

    fetch('/api/prepare', { method: 'POST', body: form })
      .then((r) => r.json().then((data) => ({ ok: r.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) throw new Error(data.error || 'Failed to prepare run.');
        startStream(data.run_id);
      })
      .catch((err) => {
        runBtn.disabled = false;
        runBtn.textContent = 'Run screening →';
        showError(err.message);
        logLine('[error] ' + err.message, 'err');
      });
  });

  function startStream(runId) {
    runBtn.textContent = 'Screening…';
    logLine('Run prepared (id: ' + runId + '). Connecting…', null);

    const useLlm = document.getElementById('useLlmCheckbox').checked;
    const source = new EventSource(`/api/run/${runId}/stream?use_llm=${useLlm}`);

    source.onmessage = (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch (e) {
        return;
      }

      switch (msg.type) {
        case 'start':
          logLine(`Starting screening of ${msg.total} resume(s)…`, null);
          setProgress(0, msg.total);
          break;

        case 'progress':
          logLine(`[${msg.index}/${msg.total}] Processing ${msg.file} …`, null);
          break;

        case 'candidate':
          logLine(`  → ${msg.candidate.name || msg.candidate.file}: final ${msg.candidate.final_score} (T ${msg.candidate.tfidf_score} · L ${msg.candidate.llm_score})`, 'ok');
          setProgress(msg.index, msg.total);
          break;

        case 'skipped':
          logLine(`  [skip] ${msg.file}: ${msg.reason}`, 'warn');
          setProgress(msg.index, msg.total);
          break;

        case 'error':
          logLine('[error] ' + msg.message, 'err');
          showError(msg.message);
          source.close();
          runBtn.disabled = false;
          runBtn.textContent = 'Run screening →';
          break;

        case 'done':
          logLine(`Done. Ranked ${msg.results.length} candidate(s). Redirecting to results…`, 'ok');
          setProgress(msg.results.length, msg.results.length);
          source.close();
          setTimeout(() => {
            window.location.href = `/results?run_id=${runId}`;
          }, 500);
          break;
      }
    };

    source.onerror = () => {
      source.close();
      runBtn.disabled = false;
      runBtn.textContent = 'Run screening →';
      showError('Connection to the server was lost. Please try again.');
      logLine('[error] Connection lost.', 'err');
    };
  }
})();
