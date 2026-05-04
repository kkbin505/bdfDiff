/**
 * BdfDiff - Single-Page Application
 *
 * Hash-based routing:
 *   #home        -> Home page (repo info + recent commits)
 *   #upload      -> Upload two BDF files and diff
 *   #git-diff    -> Compare a BDF file between two git commits
 *   #diff-result -> Diff result viewer (populated by state.diffResult)
 *
 * All data is fetched from the Flask JSON API (/api/*).
 * The 3D grid renderer is imported from 3d_grid.js (ES module).
 */

import { renderBdfGridDiff } from './3d_grid.js';

// ---------------------------------------------------------------------------
// Application state
// ---------------------------------------------------------------------------
const state = {
  repoInfo: null,   // cached /api/repo_info response
  commits: [],      // cached commit list
  diffResult: null, // last diff result to show in #diff-result
};

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

/** Escape a value for safe insertion into innerHTML. */
function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Replace the main content area. */
function setContent(html) {
  document.getElementById('app-content').innerHTML = html;
}

/** Show a centered spinner. */
function showSpinner() {
  setContent(`
    <div class="text-center py-5">
      <div class="spinner-border text-secondary" role="status">
        <span class="visually-hidden">Loading...</span>
      </div>
    </div>`);
}

/** Show a full-width error alert. */
function showError(msg) {
  setContent(`<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> ${esc(msg)}</div>`);
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function apiGet(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status} - ${url}`);
  return res.json();
}

async function apiPost(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const j = await res.json(); msg = j.error || msg; } catch (_) {}
    throw new Error(msg);
  }
  return res.json();
}

async function apiUpload(url, formData) {
  const res = await fetch(url, { method: 'POST', body: formData });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const j = await res.json(); msg = j.error || msg; } catch (_) {}
    throw new Error(msg);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

function navigate() {
  const hash = (window.location.hash || '#home').split('?')[0];

  // Update active nav link
  document.querySelectorAll('.navbar .nav-link[data-page]').forEach(a => {
    const page = '#' + a.dataset.page;
    a.classList.toggle('active', page === hash);
  });

  switch (hash) {
    case '#upload':      renderUploadPage();     break;
    case '#git-diff':    renderGitDiffPage();    break;
    case '#diff-result': renderDiffResultPage(); break;
    default:             renderHomePage();       break;
  }
}

// ---------------------------------------------------------------------------
// HOME PAGE
// ---------------------------------------------------------------------------

async function renderHomePage() {
  showSpinner();
  try {
    const data = await apiGet('/api/repo_info');
    state.repoInfo = data.repo_info;
    state.commits  = data.commits;
    setContent(buildHomePage(data));
    bindHomePage();
  } catch (e) {
    showError(e.message);
  }
}

function buildHomePage({ repo_info: info, commits }) {
  return `
    <div class="row g-4">
      ${buildRepoCard(info)}
      ${buildActionsCard(info)}
      ${buildCommitsCard(commits)}
    </div>`;
}

function buildRepoCard(info) {
  const body = info.is_git_repo
    ? `<dl class="mb-0">
        <dt>Name</dt>
        <dd>${esc(info.repo_name)}</dd>
        <dt>Branch</dt>
        <dd><span class="badge bg-secondary">${esc(info.current_branch)}</span></dd>
        <dt>Tracked BDF files</dt>
        <dd>${
          info.bdf_files?.length
            ? `<ul class="list-unstyled mb-0">${info.bdf_files.map(f =>
                `<li><i class="bi bi-file-earmark-text text-info"></i> ${esc(f)}</li>`
              ).join('')}</ul>`
            : '<em class="text-muted">No BDF files tracked yet.</em>'
        }</dd>
      </dl>`
    : `<p class="text-muted mb-0">
        <i class="bi bi-exclamation-circle"></i>
        The working directory is not a Git repository.<br/>
        Git-based diff requires running BdfDiff inside a Git-managed folder.
      </p>`;

  return `
    <div class="col-lg-4">
      <div class="card shadow-sm h-100">
        <div class="card-header bg-dark text-white">
          <i class="bi bi-git"></i> Repository
        </div>
        <div class="card-body">${body}</div>
      </div>
    </div>`;
}

function buildActionsCard(info) {
  return `
    <div class="col-lg-4">
      <div class="card shadow-sm h-100">
        <div class="card-header bg-dark text-white">
          <i class="bi bi-lightning"></i> Quick Actions
        </div>
        <div class="card-body d-flex flex-column gap-3">
          <a href="#upload" class="btn btn-primary btn-lg">
            <i class="bi bi-upload"></i> Upload &amp; Diff two BDF files
          </a>

          <button class="btn btn-outline-secondary" type="button"
                  data-bs-toggle="collapse" data-bs-target="#pasteForm">
            <i class="bi bi-clipboard"></i> Paste BDF text and diff
          </button>
          <div class="collapse" id="pasteForm">
            <form id="paste-form" class="mt-2">
              <div class="row g-2">
                <div class="col-6">
                  <label class="form-label fw-semibold">Old BDF</label>
                  <textarea id="paste-old" class="form-control font-monospace"
                            rows="8" placeholder="Paste old BDF content..."></textarea>
                </div>
                <div class="col-6">
                  <label class="form-label fw-semibold">New BDF</label>
                  <textarea id="paste-new" class="form-control font-monospace"
                            rows="8" placeholder="Paste new BDF content..."></textarea>
                </div>
              </div>
              <button type="submit" class="btn btn-success mt-2 w-100" id="paste-btn">
                <i class="bi bi-arrow-left-right"></i> Compute Diff
              </button>
            </form>
          </div>

          ${info.is_git_repo
            ? `<a href="#git-diff" class="btn btn-outline-primary btn-lg">
                <i class="bi bi-git"></i> Compare Git commits
              </a>`
            : ''}
        </div>
      </div>
    </div>`;
}

function buildCommitsCard(commits) {
  const items = commits?.length
    ? commits.map(c => `
        <div class="list-group-item list-group-item-action py-2">
          <div class="d-flex justify-content-between align-items-start">
            <code class="text-primary">${esc(c.short_sha)}</code>
            <small class="text-muted">${esc(c.date)}</small>
          </div>
          <div class="text-truncate">${esc(c.message)}</div>
          <small class="text-muted">${esc(c.author)}</small>
        </div>`).join('')
    : '<div class="card-body text-muted">No commits found.</div>';

  return `
    <div class="col-lg-4">
      <div class="card shadow-sm h-100">
        <div class="card-header bg-dark text-white">
          <i class="bi bi-clock-history"></i> Recent commits
        </div>
        ${commits?.length
          ? `<div class="list-group list-group-flush overflow-auto" style="max-height:420px">${items}</div>`
          : items}
      </div>
    </div>`;
}

function bindHomePage() {
  document.getElementById('paste-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('paste-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Computing...';

    try {
      const data = await apiPost('/api/diff/text', {
        old_text: document.getElementById('paste-old').value,
        new_text: document.getElementById('paste-new').value,
      });
      data.mode = 'text';
      state.diffResult = data;
      window.location.hash = '#diff-result';
    } catch (err) {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-arrow-left-right"></i> Compute Diff';
      const errDiv = document.createElement('div');
      errDiv.className = 'alert alert-danger mt-2';
      errDiv.textContent = err.message;
      document.getElementById('paste-form').prepend(errDiv);
    }
  });
}

// ---------------------------------------------------------------------------
// UPLOAD PAGE
// ---------------------------------------------------------------------------

function renderUploadPage() {
  setContent(`
    <div class="row justify-content-center">
      <div class="col-lg-8">
        <div class="card shadow-sm">
          <div class="card-header bg-dark text-white">
            <i class="bi bi-upload"></i> Upload two BDF files to compare
          </div>
          <div class="card-body">
            <div id="upload-error"></div>
            <form id="upload-form">
              <div class="row g-3 mb-3">
                <div class="col-md-6">
                  <label class="form-label fw-semibold">
                    <i class="bi bi-file-earmark-minus text-danger"></i> Old / Base BDF
                  </label>
                  <input type="file" name="file_old" class="form-control"
                         accept=".bdf,.dat,.nas,.bulk" required />
                </div>
                <div class="col-md-6">
                  <label class="form-label fw-semibold">
                    <i class="bi bi-file-earmark-plus text-success"></i> New / Target BDF
                  </label>
                  <input type="file" name="file_new" class="form-control"
                         accept=".bdf,.dat,.nas,.bulk" required />
                </div>
              </div>
              <button type="submit" class="btn btn-primary w-100" id="upload-btn">
                <i class="bi bi-arrow-left-right"></i> Compute Diff
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>`);

  document.getElementById('upload-form').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('upload-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Computing...';
    document.getElementById('upload-error').innerHTML = '';

    try {
      const data = await apiUpload('/api/diff/upload', new FormData(e.target));
      data.mode = 'upload';
      state.diffResult = data;
      window.location.hash = '#diff-result';
    } catch (err) {
      document.getElementById('upload-error').innerHTML =
        `<div class="alert alert-danger">${esc(err.message)}</div>`;
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-arrow-left-right"></i> Compute Diff';
    }
  });
}

// ---------------------------------------------------------------------------
// GIT DIFF PAGE
// ---------------------------------------------------------------------------

async function renderGitDiffPage() {
  showSpinner();
  try {
    if (!state.repoInfo) {
      const data = await apiGet('/api/repo_info');
      state.repoInfo = data.repo_info;
      state.commits  = data.commits;
    }
    setContent(buildGitDiffPage(state.repoInfo, state.commits));
    bindGitDiffPage();
  } catch (e) {
    showError(e.message);
  }
}

function buildGitDiffPage(info, commits) {
  if (!info.is_git_repo) {
    return `
      <div class="row justify-content-center">
        <div class="col-lg-10">
          <div class="card shadow-sm">
            <div class="card-header bg-dark text-white">
              <i class="bi bi-git"></i> Compare BDF file between two Git commits
            </div>
            <div class="card-body">
              <div class="alert alert-warning mb-0">
                <i class="bi bi-exclamation-triangle"></i>
                The current working directory is not inside a Git repository.
                Please run BdfDiff from a Git-managed project folder.
              </div>
            </div>
          </div>
        </div>
      </div>`;
  }

  const fileOptions = (info.bdf_files || []).map(f =>
    `<option value="${esc(f)}">${esc(f)}</option>`).join('');

  const commitOptions = (commits || []).map(c =>
    `<option value="${esc(c.sha)}">${esc(c.short_sha)} - ${esc(c.message.substring(0, 60))} (${esc(c.date.substring(0, 10))})</option>`
  ).join('');

  const commitRows = (commits || []).map(c => `
    <tr>
      <td><code>${esc(c.short_sha)}</code></td>
      <td class="text-nowrap text-muted">${esc(c.date.substring(0, 10))}</td>
      <td class="text-muted text-nowrap">${esc(c.author)}</td>
      <td>${esc(c.message.substring(0, 80))}</td>
      <td>${(c.files_changed || []).slice(0, 3)
             .map(f => `<span class="badge bg-secondary">${esc(f)}</span>`).join('')}
          ${(c.files_changed || []).length > 3 ? '<span class="text-muted">...</span>' : ''}
      </td>
    </tr>`).join('');

  return `
    <div class="row justify-content-center">
      <div class="col-lg-10">
        <div class="card shadow-sm">
          <div class="card-header bg-dark text-white">
            <i class="bi bi-git"></i> Compare BDF file between two Git commits
          </div>
          <div class="card-body">
            <div id="git-error"></div>
            <form id="git-diff-form">
              <div class="row g-3 mb-3">
                <div class="col-12">
                  <label class="form-label fw-semibold">BDF file path (relative to repo root)</label>
                  <select name="filepath" class="form-select" required>
                    <option value="">-- Select file --</option>
                    ${fileOptions}
                  </select>
                </div>
                <div class="col-md-6">
                  <label class="form-label fw-semibold">
                    <i class="bi bi-circle text-danger"></i> Old commit (base)
                  </label>
                  <select name="old_sha" class="form-select" required>
                    <option value="">-- Select commit --</option>
                    ${commitOptions}
                  </select>
                </div>
                <div class="col-md-6">
                  <label class="form-label fw-semibold">
                    <i class="bi bi-circle-fill text-success"></i> New commit (target)
                  </label>
                  <select name="new_sha" class="form-select" required>
                    <option value="">-- Select commit --</option>
                    ${commitOptions}
                  </select>
                </div>
              </div>
              <button type="submit" class="btn btn-primary w-100" id="git-btn">
                <i class="bi bi-arrow-left-right"></i> Compute Diff
              </button>
            </form>

            ${commits?.length ? `
              <div class="mt-4">
                <h6 class="fw-semibold"><i class="bi bi-clock-history"></i> Commit History</h6>
                <div class="table-responsive" style="max-height:320px;overflow-y:auto">
                  <table class="table table-sm table-hover table-bordered align-middle">
                    <thead class="table-dark sticky-top">
                      <tr>
                        <th>SHA</th><th>Date</th><th>Author</th>
                        <th>Message</th><th>Files changed</th>
                      </tr>
                    </thead>
                    <tbody>${commitRows}</tbody>
                  </table>
                </div>
              </div>` : ''}
          </div>
        </div>
      </div>
    </div>`;
}

function bindGitDiffPage() {
  document.getElementById('git-diff-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('git-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Computing...';
    document.getElementById('git-error').innerHTML = '';

    const fd = new FormData(e.target);
    try {
      const data = await apiPost('/api/diff/commits', {
        filepath: fd.get('filepath'),
        old_sha:  fd.get('old_sha'),
        new_sha:  fd.get('new_sha'),
      });
      data.mode = 'git';
      state.diffResult = data;
      window.location.hash = '#diff-result';
    } catch (err) {
      document.getElementById('git-error').innerHTML =
        `<div class="alert alert-danger">${esc(err.message)}</div>`;
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-arrow-left-right"></i> Compute Diff';
    }
  });
}

// ---------------------------------------------------------------------------
// DIFF RESULT PAGE
// ---------------------------------------------------------------------------

function renderDiffResultPage() {
  if (!state.diffResult) {
    setContent(`
      <div class="alert alert-warning">
        No diff data available.
        <a href="#home" class="alert-link">Go to home page</a> to start a new diff.
      </div>`);
    return;
  }
  setContent(buildDiffResultPage(state.diffResult));
  bindDiffResultPage(state.diffResult);
}

function buildDiffResultPage(data) {
  const { summary } = data;

  // Summary bar
  const summaryBar = `
    <div class="row g-3 mb-4">
      <div class="col-12">
        <div class="card shadow-sm">
          <div class="card-body py-2">
            <div class="d-flex flex-wrap align-items-center gap-3">
              <span class="fw-bold">
                <i class="bi bi-arrow-left-right"></i>
                <code>${esc(data.old_label)}</code>
                <i class="bi bi-arrow-right mx-1"></i>
                <code>${esc(data.new_label)}</code>
              </span>
              <span class="badge bg-success fs-6">+${summary.added} added</span>
              <span class="badge bg-danger fs-6">-${summary.removed} removed</span>
              <span class="badge bg-warning text-dark fs-6">~${summary.modified} modified</span>
              <span class="badge bg-secondary fs-6">${summary.unchanged} unchanged</span>
              <span class="ms-auto text-muted small">
                Total changes: ${summary.total_changes} cards
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>`;

  // Keyword sidebar
  const kwButtons = (data.all_keywords || []).map(kw => {
    const st = (data.keyword_stats || {})[kw] || {};
    const badges = [
      st.added    ? `<span class="badge bg-success">+${st.added}</span>`              : '',
      st.removed  ? `<span class="badge bg-danger">-${st.removed}</span>`             : '',
      st.modified ? `<span class="badge bg-warning text-dark">~${st.modified}</span>` : '',
    ].join('');
    return `
      <button class="list-group-item list-group-item-action
                     d-flex justify-content-between align-items-center"
              onclick="window._bdfFilterKeyword('${esc(kw)}')"
              id="filter-${esc(kw)}">
        <span>${esc(kw)}</span><span>${badges}</span>
      </button>`;
  }).join('');

  const sidebar = `
    <div class="col-lg-2 col-md-3">
      <div class="card shadow-sm sticky-top" style="top:70px">
        <div class="card-header bg-dark text-white py-2">
          <i class="bi bi-funnel"></i> Card types
        </div>
        <div class="list-group list-group-flush" style="max-height:75vh;overflow-y:auto">
          <button class="list-group-item list-group-item-action active"
                  onclick="window._bdfFilterKeyword('ALL')"
                  id="filter-ALL">
            All keywords
          </button>
          ${kwButtons}
        </div>
      </div>
    </div>`;

  // Card diff tab
  const changed   = (data.card_diffs || []).filter(cd => cd.status !== 'unchanged');
  const unchanged = (data.card_diffs || []).filter(cd => cd.status === 'unchanged');

  const cardItems = changed.map((cd, i) => {
    const hdrClass   = cd.status === 'added'   ? 'bg-success-subtle'
                     : cd.status === 'removed' ? 'bg-danger-subtle'
                     :                           'bg-warning-subtle';
    const badgeClass = cd.status === 'added'   ? 'bg-success'
                     : cd.status === 'removed' ? 'bg-danger'
                     :                           'bg-warning text-dark';
    let detail = '';
    if (cd.status === 'modified' && cd.field_diff) {
      detail = `<div class="p-2"><pre class="mb-0 diff-block">${esc(cd.field_diff.join('\n'))}</pre></div>`;
    } else if (cd.status === 'added' && cd.new_card) {
      detail = `<pre class="mb-0 p-2 diff-added">${esc((cd.new_card.raw_lines || []).join('\n'))}</pre>`;
    } else if (cd.status === 'removed' && cd.old_card) {
      detail = `<pre class="mb-0 p-2 diff-removed">${esc((cd.old_card.raw_lines || []).join('\n'))}</pre>`;
    }
    return `
      <div class="card mb-2 diff-card diff-${esc(cd.status)}"
           data-keyword="${esc(cd.keyword)}">
        <div class="card-header d-flex justify-content-between align-items-center
                    py-1 ${hdrClass}">
          <span>
            <span class="badge ${badgeClass}">${esc(cd.status)}</span>
            <strong class="ms-2">${esc(cd.keyword)}</strong>
            <code class="ms-1 text-muted">${esc(cd.key)}</code>
          </span>
          <button class="btn btn-sm btn-outline-secondary py-0"
                  onclick="window._bdfToggleCard(${i})">
            <i class="bi bi-chevron-down" id="chevron-${i}"></i>
          </button>
        </div>
        <div class="card-body p-0" id="detail-${i}" style="display:none">
          ${detail}
        </div>
      </div>`;
  }).join('');

  const unchangedItems = unchanged.map(cd => `
    <div class="card mb-1 diff-card diff-unchanged border-0 bg-light"
         data-keyword="${esc(cd.keyword)}">
      <div class="card-body py-1 px-2 text-muted font-monospace small">
        ${esc(cd.key)}
      </div>
    </div>`).join('');

  const cardTab = changed.length
    ? `<div id="card-diff-list">${cardItems}</div>
       <details class="mt-3">
         <summary class="text-muted">Show ${unchanged.length} unchanged cards</summary>
         ${unchangedItems}
       </details>`
    : `<div class="alert alert-info">
         <i class="bi bi-check-circle"></i> The two files are identical.
       </div>`;

  // Side-by-side tab
  const sideRows = (data.side_by_side || []).map(([lNo, lLine, rNo, rLine, change]) => {
    const lCls = change === 'delete'  ? 'diff-cell-removed'
               : change === 'replace' ? 'diff-cell-modified' : '';
    const rCls = change === 'insert'  ? 'diff-cell-added'
               : change === 'replace' ? 'diff-cell-modified' : '';
    return `
      <tr class="diff-row-${esc(change)}">
        <td class="text-muted text-end pe-1">${lNo ?? ''}</td>
        <td class="${lCls}"><span>${esc(lLine ?? '')}</span></td>
        <td class="text-muted text-end pe-1">${rNo ?? ''}</td>
        <td class="${rCls}"><span>${esc(rLine ?? '')}</span></td>
      </tr>`;
  }).join('');

  const sideTab = `
    <div class="table-responsive">
      <table class="table table-sm table-bordered font-monospace small diff-table">
        <thead class="table-dark">
          <tr>
            <th style="width:3em">#</th>
            <th>${esc(data.old_label)}</th>
            <th style="width:3em">#</th>
            <th>${esc(data.new_label)}</th>
          </tr>
        </thead>
        <tbody>${sideRows}</tbody>
      </table>
    </div>`;

  // Unified diff tab
  const unifiedTab = `<pre class="diff-block" id="unified-block">${esc((data.text_diff || []).join(''))}</pre>`;

  // 3D grid tab
  const gridTab = `
    <div class="card shadow-sm">
      <div class="card-header bg-dark text-white py-2">
        <i class="bi bi-cube"></i> 3D Grid Visualization
      </div>
      <div class="card-body" style="background:#1e1e1e;">
        <div id="bdf-3d-grid" style="width:100%;height:500px;"></div>
      </div>
    </div>`;

  const mainPanel = `
    <div class="col-lg-10 col-md-9">
      <ul class="nav nav-tabs mb-3">
        <li class="nav-item">
          <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#tab-cards">
            <i class="bi bi-table"></i> Card Diff
          </button>
        </li>
        <li class="nav-item">
          <button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-sidebyside">
            <i class="bi bi-layout-split"></i> Side-by-Side
          </button>
        </li>
        <li class="nav-item">
          <button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-unified">
            <i class="bi bi-file-text"></i> Unified Diff
          </button>
        </li>
        <li class="nav-item">
          <button class="nav-link" id="tab-grid-btn"
                  data-bs-toggle="tab" data-bs-target="#tab-grid">
            <i class="bi bi-cube"></i> 3D Grid Visualization
          </button>
        </li>
      </ul>
      <div class="tab-content">
        <div class="tab-pane fade show active" id="tab-cards">${cardTab}</div>
        <div class="tab-pane fade" id="tab-sidebyside">${sideTab}</div>
        <div class="tab-pane fade" id="tab-unified">${unifiedTab}</div>
        <div class="tab-pane fade" id="tab-grid">${gridTab}</div>
      </div>
    </div>`;

  return `${summaryBar}<div class="row g-3">${sidebar}${mainPanel}</div>`;
}

function bindDiffResultPage(data) {
  // Syntax-highlight unified diff block
  const block = document.getElementById('unified-block');
  if (block) {
    const lines = block.textContent.split('\n');
    block.innerHTML = lines.map(line => {
      if (line.startsWith('+++') || line.startsWith('---')) return `<span class="line-hdr">${esc(line)}</span>`;
      if (line.startsWith('+'))  return `<span class="line-add">${esc(line)}</span>`;
      if (line.startsWith('-'))  return `<span class="line-del">${esc(line)}</span>`;
      if (line.startsWith('@@')) return `<span class="line-hdr">${esc(line)}</span>`;
      return esc(line);
    }).join('\n');
  }

  // Lazy-render 3D grid on first tab activation
  let gridRendered = false;
  document.getElementById('tab-grid-btn')?.addEventListener('shown.bs.tab', () => {
    if (gridRendered) return;
    gridRendered = true;
    const meshDiff = data.mesh_diff ?? {
      nodes:     { added: [], deleted: [], modified: {} },
      elements:  { added: [], deleted: [], modified: {} },
      materials: { added: [], deleted: [], modified: {} },
      summary:   { total_changes: 0 },
      render:    { nodes: { old: {}, new: {} }, elements: { old: {}, new: {} } },
    };
    renderBdfGridDiff('bdf-3d-grid', meshDiff);
  });

  // Expose onclick helpers as globals (used by inline onclick attributes in built HTML)
  window._bdfFilterKeyword = filterKeyword;
  window._bdfToggleCard    = toggleCardDetail;
}

/** Filter the card-diff list to a single keyword (or 'ALL'). */
function filterKeyword(kw) {
  document.querySelectorAll('[id^="filter-"]').forEach(b => b.classList.remove('active'));
  document.getElementById('filter-' + kw)?.classList.add('active');
  document.querySelectorAll('.diff-card').forEach(card => {
    card.style.display = (kw === 'ALL' || card.dataset.keyword === kw) ? '' : 'none';
  });
}

/** Toggle the expanded detail panel of a card-diff card. */
function toggleCardDetail(id) {
  const detail  = document.getElementById(`detail-${id}`);
  const chevron = document.getElementById(`chevron-${id}`);
  if (!detail) return;
  const opening = detail.style.display === 'none';
  detail.style.display = opening ? 'block' : 'none';
  chevron?.classList.replace(
    opening ? 'bi-chevron-down' : 'bi-chevron-up',
    opening ? 'bi-chevron-up'  : 'bi-chevron-down',
  );
}

// ---------------------------------------------------------------------------
// Initialise
// ---------------------------------------------------------------------------
window.addEventListener('hashchange', navigate);
document.addEventListener('DOMContentLoaded', navigate);
