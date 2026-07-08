/**
 * meter.js
 * Builds the "dual-probe meter" — the signature visual of the results page.
 * It renders the blended final_score as a filled bar on a graduated 0-100
 * ruler, with two small marker flags showing exactly where the two raw
 * signals (TF-IDF similarity and LLM judgment) individually landed.
 * This is a literal readout of how scorer.py computed final_score, not a
 * decorative chart.
 */

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

function buildMeterSVG(finalScore, tfidfScore, llmScore) {
  const w = 100; // viewBox units == percent, so x-position == score value
  const barY = 13;
  const barH = 7;
  const f = clamp(finalScore, 0, 100);
  const t = clamp(tfidfScore, 0, 100);
  const l = clamp(llmScore, 0, 100);
  const gid = 'grad-' + Math.random().toString(36).slice(2, 9);

  const ticks = [0, 25, 50, 75, 100].map((v) => {
    return `
      <line x1="${v}" y1="${barY - 3}" x2="${v}" y2="${barY + barH + 3}" stroke="var(--line)" stroke-width="0.4"/>
      <text x="${v}" y="${barY + barH + 11}" font-size="4.6" fill="var(--ink-faint)"
            font-family="var(--font-mono)"
            text-anchor="${v === 0 ? 'start' : v === 100 ? 'end' : 'middle'}">${v}</text>
    `;
  }).join('');

  function marker(x, color, label) {
    return `
      <g transform="translate(${x}, ${barY - 5})">
        <polygon points="0,0 -2.2,-4 2.2,-4" fill="${color}"/>
        <title>${label}: ${x.toFixed(1)}</title>
      </g>
    `;
  }

  return `
    <svg viewBox="0 0 ${w} ${barY + barH + 16}" preserveAspectRatio="none" width="100%" height="52" role="img"
         aria-label="Fit meter: final score ${f.toFixed(1)}, TF-IDF ${t.toFixed(1)}, LLM ${l.toFixed(1)}">
      <defs>
        <linearGradient id="${gid}" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="var(--teal)"/>
          <stop offset="100%" stop-color="var(--amber)"/>
        </linearGradient>
      </defs>
      <rect x="0" y="${barY}" width="${w}" height="${barH}" rx="${barH / 2}" fill="var(--panel-2)" stroke="var(--line)" stroke-width="0.3"/>
      <rect x="0" y="${barY}" width="${f}" height="${barH}" rx="${barH / 2}" fill="url(#${gid})"/>
      ${ticks}
      ${marker(t, 'var(--teal)', 'TF-IDF')}
      ${marker(l, 'var(--amber)', 'LLM')}
    </svg>
  `;
}

function scoreClass(score) {
  if (score >= 65) return 'high';
  if (score >= 40) return 'mid';
  return 'low';
}
