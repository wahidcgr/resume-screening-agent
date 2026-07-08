(function () {
  'use strict';

  const params = new URLSearchParams(window.location.search);
  const runId = params.get('run_id');
  const resultsList = document.getElementById('resultsList');

  if (!runId) {
    renderEmpty('No run selected', 'Start a new screening from the dashboard.');
  } else {
    document.getElementById('downloadJson').href = `/api/download/${runId}/json`;
    document.getElementById('downloadCsv').href = `/api/download/${runId}/csv`;

    fetch(`/api/results/${runId}`)
      .then((r) => {
        if (!r.ok) throw new Error('Results not found for this run.');
        return r.json();
      })
      .then((data) => {
        window.__results = data;
        renderStats(data);
        renderList(data);
      })
      .catch((err) => {
        renderEmpty('Could not load results', err.message);
      });
  }

  function renderEmpty(title, sub) {
    document.getElementById('resultsPage').innerHTML = `
      <div class="empty-state">
        <div class="big">${title}</div>
        <p>${sub} — <a href="/">go to the dashboard</a></p>
      </div>
    `;
  }

  function renderStats(data) {
    const count = data.length;
    const avg = count ? (data.reduce((s, r) => s + r.final_score, 0) / count) : 0;
    const top = data[0];

    document.getElementById('statCount').textContent = count;
    document.getElementById('statAvg').textContent = avg.toFixed(1);
    document.getElementById('statTop').textContent = top ? `${top.name} — ${top.final_score}` : '—';
  }

  function chip(text, cls) {
    return `<span class="chip ${cls || ''}">${escapeHtml(text)}</span>`;
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = String(str == null ? '' : str);
    return div.innerHTML;
  }

  function renderList(data) {
    resultsList.innerHTML = '';

    if (!data.length) {
      renderEmpty('No candidates scored', 'The run completed but produced no results.');
      return;
    }

    data.forEach((c) => {
      const strip = document.createElement('article');
      strip.className = 'strip';

      const scoreCls = scoreClass(c.final_score);
      const strengths = (c.strengths || []).map((s) => chip(s, 'good')).join('') || '<span class="chip">none noted</span>';
      const gaps = (c.gaps || []).map((s) => chip(s, 'gap')).join('') || '<span class="chip">none noted</span>';
      const skills = (c.skills || []).slice(0, 14).map((s) => chip(s)).join('') || '<span class="chip">none extracted</span>';
      const education = (c.education || []).join(' · ') || '—';

      strip.innerHTML = `
        <div class="strip-head">
          <span class="rank">#${String(c.rank).padStart(2, '0')}</span>
          <div class="who">
            <span class="name">${escapeHtml(c.name || 'Unknown')}</span>
            <span class="file">${escapeHtml(c.file)}</span>
          </div>
          <span class="score ${scoreCls}">${c.final_score}</span>
        </div>
        <div class="meter-wrap">
          ${buildMeterSVG(c.final_score, c.tfidf_score, c.llm_score)}
          <div class="meter-readout">
            <span><b>T</b> ${c.tfidf_score}</span>
            <span><b>L</b> ${c.llm_score}</span>
            <span><b>Experience</b> ${c.total_experience_years ?? '—'} yrs</span>
          </div>
        </div>
        <button class="expand-toggle" type="button">
          <span class="chev">▾</span> Details
        </button>
        <div class="strip-body">
          <p class="reasoning">${escapeHtml(c.reasoning || 'No reasoning provided.')}</p>
          <div class="tag-row">
            <span class="tag-label">Strengths</span>
            <div class="chips">${strengths}</div>
          </div>
          <div class="tag-row">
            <span class="tag-label">Gaps</span>
            <div class="chips">${gaps}</div>
          </div>
          <div class="tag-row">
            <span class="tag-label">Skills</span>
            <div class="chips">${skills}</div>
          </div>
          <div class="meta-grid">
            <div class="meta-item"><span class="label">Email</span><span class="value">${escapeHtml(c.email || '—')}</span></div>
            <div class="meta-item"><span class="label">Phone</span><span class="value">${escapeHtml(c.phone || '—')}</span></div>
            <div class="meta-item"><span class="label">Education</span><span class="value">${escapeHtml(education)}</span></div>
          </div>
        </div>
      `;

      const toggleBtn = strip.querySelector('.expand-toggle');
      const body = strip.querySelector('.strip-body');
      toggleBtn.addEventListener('click', () => {
        body.classList.toggle('show');
        toggleBtn.classList.toggle('open');
      });

      resultsList.appendChild(strip);
    });
  }

  // -----------------------------------------------------------------------
  // Search + sort
  // -----------------------------------------------------------------------
  const searchInput = document.getElementById('searchInput');
  const sortSelect = document.getElementById('sortSelect');

  function applyFilters() {
    if (!window.__results) return;
    const q = searchInput.value.trim().toLowerCase();
    let rows = window.__results.filter((c) => {
      if (!q) return true;
      const haystack = [c.name, ...(c.skills || [])].join(' ').toLowerCase();
      return haystack.includes(q);
    });

    const sortKey = sortSelect.value;
    rows = rows.slice().sort((a, b) => {
      if (sortKey === 'name') return (a.name || '').localeCompare(b.name || '');
      if (sortKey === 'tfidf') return b.tfidf_score - a.tfidf_score;
      if (sortKey === 'llm') return b.llm_score - a.llm_score;
      return b.final_score - a.final_score;
    });

    renderList(rows);
  }

  searchInput.addEventListener('input', applyFilters);
  sortSelect.addEventListener('change', applyFilters);
})();
