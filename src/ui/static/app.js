let allPlanItems = [];
let currentFilter = 'all';
let currentEditIndex = null;
let progressPollInterval = null;

// Helpers
function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function setStatus(text) {
  document.getElementById('systemStatus').textContent = text;
}

// Scanning
async function triggerScan() {
  const sourcePath = document.getElementById('sourcePath').value.trim();
  if (!sourcePath) {
    alert('Please enter a valid Source Music Directory path.');
    return;
  }

  const btnScan = document.getElementById('btnScan');
  btnScan.disabled = true;
  btnScan.textContent = '⏳ Scanning...';
  setStatus('Scanning audio files...');

  try {
    const res = await fetch('/api/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_dir: sourcePath })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Failed to scan directory');
    }

    // Populate Metrics
    document.getElementById('metricsBanner').style.display = 'grid';
    document.getElementById('statTotalTracks').textContent = data.total_tracks;
    document.getElementById('statTotalSize').textContent = formatBytes(data.total_size_bytes);
    document.getElementById('statArtCount').textContent = `${data.artwork_folders_found} artwork folders detected`;

    const formatsStr = Object.entries(data.formats)
      .map(([ext, count]) => `${ext.toUpperCase()}: ${count}`)
      .join(' | ');
    document.getElementById('statFormats').textContent = formatsStr || 'No audio files found';

    document.getElementById('statHighConf').textContent = data.confidence.high || 0;
    document.getElementById('statInferred').textContent = (data.confidence.medium || 0) + (data.confidence.low || 0);

    // Enable Plan button
    document.getElementById('btnPlan').disabled = false;
    setStatus(`Scan complete: ${data.total_tracks} tracks found`);

    // Auto-suggest default destination if empty
    const destInput = document.getElementById('destPath');
    if (!destInput.value.trim()) {
      destInput.value = sourcePath.replace(/[\\\/]+$/, '') + '_Organized';
    }

  } catch (err) {
    alert(`Error: ${err.message}`);
    setStatus('Error during scan');
  } finally {
    btnScan.disabled = false;
    btnScan.textContent = '🔍 Scan & Analyze';
  }
}

// Planning
async function triggerPlan() {
  const destPath = document.getElementById('destPath').value.trim();
  if (!destPath) {
    alert('Please enter a destination directory path.');
    return;
  }

  const btnPlan = document.getElementById('btnPlan');
  btnPlan.disabled = true;
  btnPlan.textContent = '⏳ Building Plan...';
  setStatus('Generating reorganization plan...');

  try {
    const res = await fetch('/api/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        destination_dir: destPath,
        conflict_strategy: 'suffix',
        write_tags: document.getElementById('optWriteTags').checked,
        copy_art: document.getElementById('optCopyArt').checked,
        uconnect_mode: true,
        artwork_action: document.getElementById('artworkAction').value,
      })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Failed to generate plan');
    }

    allPlanItems = data.items;
    updateCounts();
    renderTable();

    document.getElementById('tableSection').style.display = 'flex';
    document.getElementById('btnExecute').disabled = false;
    setStatus(`Plan ready: ${data.total_items} tracks mapped`);

  } catch (err) {
    alert(`Error: ${err.message}`);
    setStatus('Error generating plan');
  } finally {
    btnPlan.disabled = false;
    btnPlan.textContent = '📋 Preview Plan';
  }
}

function updateCounts() {
  document.getElementById('countAll').textContent = allPlanItems.length;
  document.getElementById('countReady').textContent = allPlanItems.filter(p => p.status === 'ready').length;
  document.getElementById('countWarning').textContent = allPlanItems.filter(p => p.status === 'warning').length;
  document.getElementById('countConflict').textContent = allPlanItems.filter(p => p.status === 'conflict').length;
}

function setFilter(filter, el) {
  currentFilter = filter;
  document.querySelectorAll('.filter-pill').forEach(btn => btn.classList.remove('active'));
  el.classList.add('active');
  renderTable();
}

function filterTable() {
  renderTable();
}

function renderTable() {
  const tbody = document.getElementById('trackTableBody');
  tbody.innerHTML = '';

  const search = document.getElementById('tableSearch').value.toLowerCase().trim();

  const filtered = allPlanItems.filter((item, idx) => {
    // Filter pill check
    if (currentFilter !== 'all' && item.status !== currentFilter) {
      return false;
    }
    // Search check
    if (search) {
      const text = `${item.artist} ${item.album} ${item.title} ${item.source_filename} ${item.target_filename}`.toLowerCase();
      return text.includes(search);
    }
    return true;
  });

  const displayItems = filtered.slice(0, 150); // performance limit

  displayItems.forEach((item, displayIdx) => {
    const originalIndex = allPlanItems.indexOf(item);
    const tr = document.createElement('tr');

    const confClass = item.confidence === 'high' ? 'conf-high' : (item.confidence === 'medium' ? 'conf-medium' : 'conf-low');

    tr.innerHTML = `
      <td>
        <button class="play-btn" title="Play Track Preview" onclick="playTrack('${encodeURIComponent(item.source_path)}', '${escapeHtml(item.title)}', '${escapeHtml(item.artist)}')">
          ▶
        </button>
      </td>
      <td>
        <div class="path-diff">
          <span class="orig-path" title="${escapeHtml(item.source_path)}">${escapeHtml(item.source_path)}</span>
          <span class="new-path" title="${escapeHtml(item.target_path)}">↳ ${escapeHtml(item.target_artist)} / ${escapeHtml(item.target_album)} / ${escapeHtml(item.target_filename)}</span>
        </div>
      </td>
      <td><strong>${escapeHtml(item.artist || 'Unknown')}</strong></td>
      <td>${escapeHtml(item.album || 'Unknown')}</td>
      <td>${escapeHtml(item.title || item.source_filename)}</td>
      <td style="text-align: center;">${item.track_number || '-'}</td>
      <td style="text-align: center;"><span style="font-family: monospace; font-size: 0.8rem;">${escapeHtml(item.format)}</span></td>
      <td><span class="badge-confidence ${confClass}">${item.confidence}</span></td>
      <td style="text-align: right;">
        <div class="table-actions" style="justify-content: flex-end;">
          <button class="action-icon-btn" title="Identify with Acoustic Fingerprint (Shazam-style)" onclick="fingerprintTrackDirect(${originalIndex})">🎧</button>
          <button class="action-icon-btn" title="Edit Metadata" onclick="openEditModal(${originalIndex})">✎</button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Audio Player
function playTrack(encodedPath, title, artist) {
  const player = document.getElementById('nativeAudio');
  const bar = document.getElementById('audioPlayerBar');
  
  document.getElementById('nowPlayingTitle').textContent = decodeURIComponent(title);
  document.getElementById('nowPlayingArtist').textContent = decodeURIComponent(artist);
  
  player.src = `/api/audio-stream?path=${encodedPath}`;
  bar.style.display = 'flex';
  player.play().catch(e => console.log('Audio autoplay prevented:', e));
}

function closePlayer() {
  const player = document.getElementById('nativeAudio');
  player.pause();
  document.getElementById('audioPlayerBar').style.display = 'none';
}

// Edit Modal
function openEditModal(index) {
  currentEditIndex = index;
  const item = allPlanItems[index];

  document.getElementById('editArtist').value = item.artist || '';
  document.getElementById('editAlbum').value = item.album || '';
  document.getElementById('editTitle').value = item.title || '';
  document.getElementById('editTrackNum').value = item.track_number || '';
  document.getElementById('editYear').value = item.year || '';

  document.getElementById('editModal').style.display = 'flex';
}

function closeEditModal() {
  document.getElementById('editModal').style.display = 'none';
  currentEditIndex = null;
}

async function saveTrackEdit() {
  if (currentEditIndex === null) return;

  const payload = {
    index: currentEditIndex,
    artist: document.getElementById('editArtist').value,
    album: document.getElementById('editAlbum').value,
    title: document.getElementById('editTitle').value,
    track_number: parseInt(document.getElementById('editTrackNum').value) || null,
    year: parseInt(document.getElementById('editYear').value) || null,
  };

  try {
    const res = await fetch('/api/update-track', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.plan_item) {
      allPlanItems[currentEditIndex] = data.plan_item;
      updateCounts();
      renderTable();
    }
    closeEditModal();
  } catch (err) {
    alert(`Failed to save: ${err.message}`);
  }
}

async function searchMusicBrainzForCurrent() {
  const artist = document.getElementById('editArtist').value.trim();
  const album = document.getElementById('editAlbum').value.trim();

  if (!artist && !album) {
    alert('Please enter at least an Artist or Album name to search MusicBrainz.');
    return;
  }

  try {
    const res = await fetch('/api/search-musicbrainz', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ artist, album })
    });
    const data = await res.json();
    if (data.results && data.results.length > 0) {
      const match = data.results[0];
      if (confirm(`MusicBrainz Match Found:\nArtist: ${match.artist}\nAlbum: ${match.title}\nDate: ${match.date || 'N/A'}\n\nApply this metadata?`)) {
        if (match.artist) document.getElementById('editArtist').value = match.artist;
        if (match.title) document.getElementById('editAlbum').value = match.title;
        if (match.date) {
          const y = parseInt(match.date.slice(0, 4));
          if (!isNaN(y)) document.getElementById('editYear').value = y;
        }
      }
    } else {
      alert('No exact MusicBrainz matches found for this query.');
    }
  } catch (err) {
    alert(`MusicBrainz query error: ${err.message}`);
  }
}

// Execute Copy
async function triggerExecute() {
  if (!confirm(`Are you ready to copy ${allPlanItems.length} tracks into the organized structure?\n\nNote: Original files are completely untouched.`)) {
    return;
  }

  const btnExec = document.getElementById('btnExecute');
  btnExec.disabled = true;

  const progressCard = document.getElementById('progressCard');
  progressCard.style.display = 'block';
  document.getElementById('btnOpenDest').style.display = 'none';

  try {
    const res = await fetch('/api/execute', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Execution start failed');

    setStatus('Copy in progress...');
    startProgressPolling();

  } catch (err) {
    alert(`Execution failed: ${err.message}`);
    btnExec.disabled = false;
  }
}

function startProgressPolling() {
  if (progressPollInterval) clearInterval(progressPollInterval);

  progressPollInterval = setInterval(async () => {
    try {
      const res = await fetch('/api/progress');
      const prog = await res.json();

      const pct = prog.total_files > 0 ? Math.round((prog.current_index / prog.total_files) * 100) : 0;
      document.getElementById('progressBar').style.width = `${pct}%`;
      document.getElementById('progressPercent').textContent = `${pct}%`;
      document.getElementById('progressFileCount').textContent = `${prog.current_index} / ${prog.total_files} Files`;
      document.getElementById('progressSpeed').textContent = `${prog.speed_mb_s} MB/s`;
      document.getElementById('progressCurrentFile').textContent = prog.current_file || 'Processing...';

      if (prog.status === 'finished') {
        clearInterval(progressPollInterval);
        setStatus('✓ Organization complete! All files safely copied.');
        document.getElementById('progressTitle').textContent = '🎉 Organization Complete!';
        document.getElementById('btnOpenDest').style.display = 'inline-flex';
        document.getElementById('btnCancel').style.display = 'none';
        document.getElementById('btnExecute').disabled = false;
      } else if (prog.status === 'cancelled') {
        clearInterval(progressPollInterval);
        setStatus('Copy cancelled by user.');
        document.getElementById('progressTitle').textContent = 'Copy Cancelled';
        document.getElementById('btnExecute').disabled = false;
      }
    } catch (err) {
      console.error('Progress poll error:', err);
    }
  }, 400);
}

async function triggerCancel() {
  if (confirm('Cancel file copying? Already copied files in destination will remain, but copying will halt.')) {
    await fetch('/api/cancel', { method: 'POST' });
  }
}

async function openDestFolder() {
  const destPath = document.getElementById('destPath').value.trim();
  if (destPath) {
    await fetch(`/api/open-folder?path=${encodeURIComponent(destPath)}`);
  }
}

// Settings & Pre-population from Local Config
async function loadAndApplyInitialSettings() {
  try {
    const res = await fetch('/api/settings');
    if (!res.ok) return;
    const data = await res.json();

    // Prepopulate main screen controls from config
    if (data.source_dir && document.getElementById('sourcePath')) {
      document.getElementById('sourcePath').value = data.source_dir;
    }
    if (data.destination_dir && document.getElementById('destPath')) {
      document.getElementById('destPath').value = data.destination_dir;
    }
    if (data.artwork_action && document.getElementById('artworkAction')) {
      document.getElementById('artworkAction').value = data.artwork_action;
    }
    if (data.write_tags !== undefined && document.getElementById('optWriteTags')) {
      document.getElementById('optWriteTags').checked = data.write_tags;
    }
    if (data.copy_art !== undefined && document.getElementById('optCopyArt')) {
      document.getElementById('optCopyArt').checked = data.copy_art;
    }

    // Prepopulate model select options
    const select = document.getElementById('geminiModelSelect');
    if (select && data.available_models && data.available_models.length > 0) {
      select.innerHTML = '';
      data.available_models.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.id;
        opt.textContent = m.name;
        if (m.id === (data.gemini_model || 'gemini-pro-latest')) {
          opt.selected = true;
        }
        select.appendChild(opt);
      });
    } else if (select && data.gemini_model) {
      select.value = data.gemini_model;
    }

    // Prepopulate API Key inputs
    const geminiInput = document.getElementById('geminiApiKeyInput');
    if (geminiInput) {
      if (data.gemini_api_key) {
        geminiInput.value = data.gemini_api_key;
      }
      if (data.gemini_key_preview) {
        geminiInput.placeholder = `Active (${data.gemini_key_preview})`;
      }
    }

    const acoustidInput = document.getElementById('acoustidApiKeyInput');
    if (acoustidInput) {
      if (data.acoustid_api_key) {
        acoustidInput.value = data.acoustid_api_key;
      }
      if (data.acoustid_key_preview) {
        acoustidInput.placeholder = `Active (${data.acoustid_key_preview})`;
      }
    }

    // Fingerprint engine status
    const fpStatus = document.getElementById('fingerprintEngineStatus');
    if (fpStatus) {
      if (data.has_fpcalc) {
        fpStatus.textContent = '✓ Chromaprint (fpcalc 1.6.1) engine installed and ready';
        fpStatus.style.color = '#34d399';
      } else {
        fpStatus.textContent = '⚠ fpcalc engine not found. Fingerprinting will be unavailable.';
        fpStatus.style.color = '#f87171';
      }
    }
  } catch (err) {
    console.error('Failed to load initial settings from local config:', err);
  }
}

function attachAutoSaveListeners() {
  const artSel = document.getElementById('artworkAction');
  if (artSel) {
    artSel.addEventListener('change', () => {
      fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ artwork_action: artSel.value })
      }).catch(e => console.error('Failed to auto-save artwork_action:', e));
    });
  }

  const writeTags = document.getElementById('optWriteTags');
  if (writeTags) {
    writeTags.addEventListener('change', () => {
      fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ write_tags: writeTags.checked })
      }).catch(e => console.error('Failed to auto-save write_tags:', e));
    });
  }

  const copyArt = document.getElementById('optCopyArt');
  if (copyArt) {
    copyArt.addEventListener('change', () => {
      fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ copy_art: copyArt.checked })
      }).catch(e => console.error('Failed to auto-save copy_art:', e));
    });
  }
}

// Auto-run on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', async () => {
    await loadAndApplyInitialSettings();
    attachAutoSaveListeners();
  });
} else {
  loadAndApplyInitialSettings().then(attachAutoSaveListeners);
}

// Settings Modal
async function openSettingsModal() {
  await loadAndApplyInitialSettings();
  document.getElementById('settingsModal').style.display = 'flex';
}

function closeSettingsModal() {
  document.getElementById('settingsModal').style.display = 'none';
}

async function saveSettings() {
  const geminiKey = document.getElementById('geminiApiKeyInput').value.trim();
  const acoustidKey = document.getElementById('acoustidApiKeyInput').value.trim();
  const model = document.getElementById('geminiModelSelect').value;

  const payload = {
    gemini_model: model || 'gemini-pro-latest',
    gemini_api_key: geminiKey || '',
    acoustid_api_key: acoustidKey || '',
    artwork_action: document.getElementById('artworkAction') ? document.getElementById('artworkAction').value : 'strip',
    write_tags: document.getElementById('optWriteTags') ? document.getElementById('optWriteTags').checked : true,
    copy_art: document.getElementById('optCopyArt') ? document.getElementById('optCopyArt').checked : false,
  };

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Server returned an error');
    alert('Settings saved to local config successfully!');
    closeSettingsModal();
    // Refresh pre-population
    await loadAndApplyInitialSettings();
  } catch (err) {
    alert(`Failed to save settings: ${err.message}`);
  }
}

// AI Album Resolver
async function triggerAiResolve() {
  const btn = document.getElementById('btnAiResolve');
  btn.disabled = true;
  btn.textContent = '🤖 Analyzing with AI...';
  setStatus('Resolving unknown album metadata using Gemini AI...');

  try {
    const res = await fetch('/api/ai-resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();

    if (!res.ok) {
      if (data.detail && data.detail.includes('API Key is not configured')) {
        alert('Please configure your Gemini API Key in "AI & Fingerprint Settings" to use AI recognition.');
        openSettingsModal();
        return;
      }
      throw new Error(data.detail || 'AI resolution failed');
    }

    if (data.total_updated > 0) {
      alert(`🎉 Gemini AI successfully resolved ${data.total_updated} tracks across ${data.resolutions.length} album(s)!`);
      if (data.plan) {
        allPlanItems = data.plan;
        updateCounts();
        renderTable();
      }
      setStatus(`AI Resolution complete: ${data.total_updated} tracks updated`);
    } else {
      alert(data.message || 'No unknown tracks required AI resolution.');
      setStatus('Ready');
    }
  } catch (err) {
    alert(`AI Resolution Error: ${err.message}`);
    setStatus('AI Resolution error');
  } finally {
    btn.disabled = false;
    btn.textContent = '🤖 AI Resolve Unknowns';
  }
}

// Acoustic Fingerprint Matching
async function fingerprintTrackDirect(index) {
  setStatus(`Generating acoustic fingerprint for track #${index + 1}...`);
  try {
    const res = await fetch('/api/fingerprint-track', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ index: index })
    });
    const data = await res.json();

    if (data.status === 'matched') {
      const s = data.suggested;
      if (confirm(`🎧 Acoustic Fingerprint Match Found!\nScore: ${Math.round(s.score * 100)}%\nArtist: ${s.artist}\nTitle: ${s.title}\nAlbum: ${s.album || 'Unknown'}\n\nApply this match to track?`)) {
        await fetch('/api/update-track', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            index: index,
            artist: s.artist,
            title: s.title,
            album: s.album || undefined
          })
        });
        // Refresh plan
        await triggerPlan();
        setStatus(`Applied fingerprint match for "${s.title}"`);
      }
    } else if (data.details && data.details.error) {
      alert(`Acoustic Fingerprint Result:\n${data.details.error}`);
      if (data.details.has_fingerprint) {
        openSettingsModal();
      }
    } else {
      alert(`Fingerprint generated, but no match was found in the AcoustID database.`);
    }
  } catch (err) {
    alert(`Fingerprint matching error: ${err.message}`);
  } finally {
    setStatus('Ready');
  }
}

async function fingerprintCurrentTrack() {
  if (currentEditIndex === null) return;
  await fingerprintTrackDirect(currentEditIndex);
  closeEditModal();
}
