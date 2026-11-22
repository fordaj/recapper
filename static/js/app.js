(() => {
  'use strict';

  // ---------- Utilities ----------
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));
  const uid = () => 'c_' + Math.random().toString(36).slice(2, 10);
  const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
  const fmtTime = (s) => {
    s = Math.max(0, s);
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    const tenth = Math.floor((s * 10) % 10);
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}.${tenth}`;
  };
  const fmtShort = (s) => {
    s = Math.max(0, s);
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return m > 0 ? `${m}:${String(sec).padStart(2, '0')}` : `0:${String(sec).padStart(2, '0')}`;
  };

  function toast(msg) {
    const el = $('#toast');
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.remove('show'), 2200);
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
      ...opts,
    });
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
    if (!res.ok) {
      const msg = data?.error?.message || data?.message || `Request failed (${res.status})`;
      throw new Error(msg);
    }
    return data;
  }

  // ---------- State ----------
  let MEDIA = [];
  const state = {
    pxPerSec: 80,
    minPxPerSec: 40,
    maxPxPerSec: 180,
    playhead: 0,
    playing: false,
    selectedClipId: null,
    mediaFilter: 'all',
    tracks: [
      { id: 'V1', kind: 'visual', label: 'Video 1', sub: 'Main visuals' },
      { id: 'A1', kind: 'audio', label: 'Audio 1', sub: 'Music & sound' },
    ],
    clips: [],
    projectName: 'Untitled Recap',
    projectPath: null,
    dirty: false,
  };

  function setDirty(dirty = true) {
    state.dirty = dirty;
    const el = $('#saveStatus');
    if (el) el.textContent = dirty ? 'Unsaved' : (state.projectPath ? 'Saved' : '');
  }

  function normalizeMedia(m) {
    const type = m.type || 'image';
    const src = m.src || (m.id ? `/api/media/file/${m.id}` : '');
    const thumb = m.thumbnail || (type === 'image' ? src : (m.thumb || (type === 'video' ? `/api/media/thumb/${m.id}` : '')));
    return {
      id: m.id,
      type,
      name: m.name || 'Untitled',
      src,
      thumb,
      duration: Number(m.duration || (type === 'image' ? 4 : type === 'audio' ? 20 : 5)),
      subtitle: m.subtitle || (type === 'image' ? 'Photo' : type === 'video' ? 'Video clip' : 'Audio'),
      hasAudio: !!m.has_audio,
    };
  }

  function getMedia(id) { return MEDIA.find(m => m.id === id); }
  function getClip(id) { return state.clips.find(c => c.id === id); }
  function clipsOnTrack(trackId) { return state.clips.filter(c => c.trackId === trackId).sort((a,b) => a.start - b.start); }
  function projectDuration() { return Math.max(10, ...state.clips.map(c => c.start + c.duration)); }
  function totalDuration() { return projectDuration() + 4; }

  function mkClip(opts) {
    return {
      id: opts.id || uid(),
      trackId: opts.trackId,
      type: opts.type,
      name: opts.name || 'Clip',
      start: Number(opts.start || 0),
      duration: Number(opts.duration || 3),
      mediaId: opts.mediaId || opts.media_id || null,
      title: opts.title || opts.params?.title || '',
      subtitle: opts.subtitle || opts.params?.subtitle || '',
      compLeft: opts.compLeft || opts.params?.compLeft || 'm1',
      compRight: opts.compRight || opts.params?.compRight || 'm2',
      volume: opts.volume != null ? Number(opts.volume) : (opts.params?.volume != null ? Number(opts.params.volume) : 100),
      color: opts.color || opts.params?.color || '#f0b45c',
    };
  }

  function projectToState(project, path = null) {
    state.projectName = project.name || 'Untitled Recap';
    state.projectPath = path || null;
    $('#projectName').textContent = state.projectName;
    document.title = `Recapper - ${state.projectName}`;
    window.__mediaRaw = (project.media || []).slice();
    MEDIA = window.__mediaRaw.map(normalizeMedia);
    state.tracks = (project.tracks || []).map(t => ({ id: t.id, kind: t.kind, label: t.label || t.id, sub: t.kind === 'audio' ? 'Music & sound' : 'Main visuals' }));
    if (!state.tracks.length) {
      state.tracks = [
        { id: 'V1', kind: 'visual', label: 'Video 1', sub: 'Main visuals' },
        { id: 'A1', kind: 'audio', label: 'Audio 1', sub: 'Music & sound' },
      ];
    }
    state.clips = (project.clips || []).map(c => mkClip({ ...c, ...c.params }));
    state.render = project.render || state.render;
    setDirty(false);
  }

  function stateToProject() {
    return {
      version: '1.0',
      name: state.projectName,
      media: MEDIA.map(m => ({ id: m.id, type: m.type, name: m.name, path: m.src.startsWith('/api/media/file/') ? (getMedia(m.id)?._path || m.name) : m.src, duration: m.duration, thumbnail: m.thumb })),
      tracks: state.tracks.map((t, i) => ({ id: t.id, kind: t.kind, label: t.label, order: i })),
      clips: state.clips.map(c => ({
        id: c.id, trackId: c.trackId, type: c.type, name: c.name, start: c.start, duration: c.duration, mediaId: c.mediaId,
        params: { title: c.title, subtitle: c.subtitle, compLeft: c.compLeft, compRight: c.compRight, volume: c.volume, color: c.color }
      })),
      render: state.render || { width:1920, height:1080, fps:30, crf:18, output_name:'recap.mp4' },
    };
  }

  // Better stateToProject: keep original media paths if known
  function buildProjectPayload() {
    const mediaPayload = (window.__mediaRaw || []).map(m => ({
      id: m.id, type: m.type, name: m.name, path: m.path, duration: m.duration,
      width: m.width, height: m.height, has_audio: m.has_audio, codec: m.codec, thumbnail: m.thumbnail, probe: m.probe || {}
    }));
    return {
      version: '1.0',
      name: state.projectName,
      media: mediaPayload,
      tracks: state.tracks.map((t, i) => ({ id: t.id, kind: t.kind, label: t.label, order: i })),
      clips: state.clips.map(c => ({
        id: c.id, trackId: c.trackId, type: c.type, name: c.name, start: Number(c.start), duration: Number(c.duration), mediaId: c.mediaId || null,
        params: { title: c.title, subtitle: c.subtitle, compLeft: c.compLeft, compRight: c.compRight, volume: Number(c.volume), color: c.color }
      })),
      render: state.render || { width:1920, height:1080, fps:30, crf:18, output_name:'recap.mp4' },
    };
  }

  // ---------- Media Library ----------
  function renderMedia() {
    const grid = $('#mediaGrid');
    const filter = state.mediaFilter;
    const items = MEDIA.filter(m => filter === 'all' || m.type === filter);
    $('#mediaCount').textContent = `${items.length} item${items.length !== 1 ? 's' : ''}`;
    grid.innerHTML = items.map(m => {
      const badge = `<span class="media-badge badge-${m.type}">${m.type}</span>`;
      const dur = `<span class="media-duration">${fmtShort(m.duration || 0)}</span>`;
      let thumb = '';
      if (m.type === 'image') {
        thumb = `<img src="${esc(m.thumb || m.src)}" alt="${esc(m.name)}" loading="lazy">`;
      } else if (m.type === 'video') {
        const poster = m.thumb ? `<img src="${esc(m.thumb)}" alt="${esc(m.name)}" loading="lazy">` : '';
        thumb = `${poster}<div class="media-icon" style="position:absolute;inset:0;background:rgba(0,0,0,0.25)"><svg width="28" height="28" viewBox="0 0 24 24" fill="white"><path d="M8 5l11 7-11 7V5z"/></svg></div>`;
      } else {
        thumb = `<div class="media-icon" style="background:linear-gradient(135deg,rgba(78,205,196,0.15),transparent)"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg></div>`;
      }
      return `<div class="media-card" draggable="true" data-media-id="${m.id}">
        <div class="media-thumb">${badge}${thumb}${dur}</div>
        <div class="media-meta"><div class="media-name" title="${esc(m.name)}">${esc(m.name)}</div><div class="media-sub">${esc(m.subtitle || '')}</div></div>
      </div>`;
    }).join('');

    grid.querySelectorAll('.media-card').forEach(card => {
      card.addEventListener('dragstart', (e) => {
        card.classList.add('dragging');
        e.dataTransfer.setData('text/plain', card.dataset.mediaId);
        e.dataTransfer.effectAllowed = 'copy';
      });
      card.addEventListener('dragend', () => card.classList.remove('dragging'));
      card.addEventListener('dblclick', () => addMediaToTimeline(card.dataset.mediaId));
    });
  }

  function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  // ---------- Timeline ----------
  function renderTimeline() {
    renderTrackLabels();
    renderRuler();
    renderTracks();
    updatePlayhead();
    updateZoomLabel();
  }

  function renderTrackLabels() {
    $('#trackLabels').innerHTML = state.tracks.map(t => {
      const color = t.kind === 'audio' ? 'var(--audio)' : 'var(--accent)';
      return `<div class="track-label ${t.kind === 'audio' ? 'track-audio' : ''}" data-track="${t.id}">
        <span class="track-dot" style="background:${color}"></span>
        <div><div>${esc(t.label)}</div><small>${esc(t.sub || '')}</small></div>
      </div>`;
    }).join('');
  }

  function renderRuler() {
    const ruler = $('#timeRuler');
    const dur = totalDuration();
    const width = Math.max(dur * state.pxPerSec, 600);
    ruler.style.width = width + 'px';
    let html = '';
    const step = state.pxPerSec < 55 ? 5 : 1;
    for (let s = 0; s <= Math.ceil(dur); s += step) {
      const left = s * state.pxPerSec;
      html += `<div class="ruler-tick" style="left:${left}px"><span>${fmtShort(s)}</span></div>`;
      if (step === 1) {
        for (let q = 1; q < 4; q++) {
          const ms = s + q * 0.25;
          if (ms > dur) break;
          html += `<div class="ruler-tick minor" style="left:${ms * state.pxPerSec}px;height:8px;top:auto;bottom:0"></div>`;
        }
      }
    }
    ruler.innerHTML = html;
  }

  function renderTracks() {
    const tracksEl = $('#tracks');
    const dur = totalDuration();
    const width = Math.max(dur * state.pxPerSec, 600);
    tracksEl.style.width = width + 'px';
    $('#timeRuler').style.width = width + 'px';
    tracksEl.innerHTML = state.tracks.map(t => {
      const clips = clipsOnTrack(t.id);
      const clipHtml = clips.map(c => renderClip(c)).join('');
      return `<div class="track ${t.kind === 'audio' ? 'track-audio' : ''}" data-track-id="${t.id}" style="width:${width}px">${clipHtml}</div>`;
    }).join('');
    bindTrackEvents();
    bindClipEvents();
  }

  function renderClip(c) {
    const left = c.start * state.pxPerSec;
    const width = Math.max(24, c.duration * state.pxPerSec);
    const sel = c.id === state.selectedClipId ? ' selected' : '';
    const media = c.mediaId ? getMedia(c.mediaId) : null;
    let inner = '';
    let bg = '';
    if (c.type === 'image' && media) {
      bg = `<div class="clip-bg-strip">${thumbStrip(media.thumb || media.src, width)}</div>`;
      inner = `<div class="clip-thumb">${bg}<span class="clip-badge">IMG</span><div class="clip-content"><div class="clip-name">${esc(c.name)}</div><div class="clip-meta">${c.duration.toFixed(1)}s</div></div></div>`;
    } else if (c.type === 'video') {
      const src = media ? (media.thumb || media.src) : '';
      bg = src ? `<div class="clip-bg-strip">${thumbStrip(src, width)}</div>` : '';
      inner = `<div class="clip-thumb">${bg}<span class="clip-badge">VID</span><div class="clip-content"><div class="clip-name">${esc(c.name)}</div><div class="clip-meta">${c.duration.toFixed(1)}s</div></div></div>`;
    } else if (c.type === 'title') {
      inner = `<div class="clip-thumb"><span class="clip-badge">T</span><div class="clip-content"><div class="clip-name">${esc(c.title || c.name)}</div><div class="clip-meta">Title slide · ${c.duration.toFixed(1)}s</div></div></div>`;
    } else if (c.type === 'composition') {
      const l = getMedia(c.compLeft); const r = getMedia(c.compRight);
      const lSrc = l ? (l.thumb || l.src || '') : '';
      const rSrc = r ? (r.thumb || r.src || '') : '';
      bg = `<div class="clip-bg-strip" style="opacity:0.35">${lSrc ? `<img src="${esc(lSrc)}" alt="">` : ''}${rSrc ? `<img src="${esc(rSrc)}" alt="">` : ''}</div>`;
      inner = `<div class="clip-thumb">${bg}<span class="clip-badge">SBS</span><div class="clip-content"><div class="clip-name">${esc(c.name)}</div><div class="clip-meta">Side-by-side · ${c.duration.toFixed(1)}s</div></div></div>`;
    } else if (c.type === 'audio') {
      inner = `<div class="clip-thumb"><div class="clip-waveform">${waveformBars(width)}</div><span class="clip-badge" style="margin-left:auto">AUD</span><div class="clip-content" style="flex:0 1 auto"><div class="clip-name">${esc(c.name)}</div><div class="clip-meta">${c.volume}% · ${c.duration.toFixed(1)}s</div></div></div>`;
    }
    return `<div class="clip clip-type-${c.type}${sel}" data-clip-id="${c.id}" style="left:${left}px;width:${width}px">
      <div class="trim-handle left" data-edge="left"></div>
      ${inner}
      <div class="trim-handle right" data-edge="right"></div>
    </div>`;
  }

  function thumbStrip(src, width) {
    const count = Math.max(1, Math.ceil(width / 72));
    let out = '';
    for (let i = 0; i < count; i++) out += `<img src="${esc(src)}" alt="" loading="lazy">`;
    return out;
  }

  function waveformBars(width) {
    const count = Math.max(12, Math.floor(width / 5));
    let out = '';
    for (let i = 0; i < count; i++) {
      const h = 20 + Math.abs(Math.sin(i * 0.55) * 55) + Math.abs(Math.cos(i * 0.23) * 20);
      out += `<span style="height:${Math.min(90, h)}%"></span>`;
    }
    return out;
  }

  // ---------- Track / Clip Events ----------
  function bindTrackEvents() {
    $$('.track').forEach(trackEl => {
      trackEl.addEventListener('dragover', (e) => {
        if (e.dataTransfer.types.includes('text/plain')) { e.preventDefault(); trackEl.classList.add('drag-over'); }
      });
      trackEl.addEventListener('dragleave', () => trackEl.classList.remove('drag-over'));
      trackEl.addEventListener('drop', (e) => {
        e.preventDefault();
        trackEl.classList.remove('drag-over');
        const mediaId = e.dataTransfer.getData('text/plain');
        const media = getMedia(mediaId);
        if (!media) return;
        const trackId = trackEl.dataset.trackId;
        const track = state.tracks.find(t => t.id === trackId);
        if (!track) return;
        if (media.type === 'audio' && track.kind !== 'audio') { toast('Audio clips go on an audio track'); return; }
        if (media.type !== 'audio' && track.kind === 'audio') { toast('Visual clips go on a visual track'); return; }
        const rect = trackEl.getBoundingClientRect();
        const x = e.clientX - rect.left + $('#timelineScroll').scrollLeft;
        const start = snapTime(Math.max(0, x / state.pxPerSec));
        addClipFromMedia(media, trackId, start);
      });
      trackEl.addEventListener('mousedown', (e) => {
        if (e.target.closest('.clip')) return;
        const rect = trackEl.getBoundingClientRect();
        const x = e.clientX - rect.left + $('#timelineScroll').scrollLeft;
        setPlayhead(Math.max(0, x / state.pxPerSec));
        selectClip(null);
      });
    });
    $('#timeRuler').addEventListener('mousedown', (e) => {
      const rect = $('#timeRuler').getBoundingClientRect();
      const x = e.clientX - rect.left + $('#timelineScroll').scrollLeft;
      setPlayhead(Math.max(0, x / state.pxPerSec));
    });
  }

  function bindClipEvents() {
    $$('.clip').forEach(el => {
      el.addEventListener('mousedown', (e) => {
        if (e.target.closest('.trim-handle')) return;
        e.stopPropagation();
        const clipId = el.dataset.clipId;
        selectClip(clipId);
        startClipDrag(e, clipId);
      });
      el.querySelectorAll('.trim-handle').forEach(handle => {
        handle.addEventListener('mousedown', (e) => {
          e.stopPropagation(); e.preventDefault();
          selectClip(el.dataset.clipId);
          startTrim(e, el.dataset.clipId, handle.dataset.edge);
        });
      });
    });
  }

  function snapTime(t) { return Math.round(t * 4) / 4; }

  function addClipFromMedia(media, trackId, start) {
    const clip = mkClip({
      trackId, type: media.type, name: media.name, start, duration: media.duration || 4, mediaId: media.id,
      volume: media.type === 'audio' ? 80 : 100,
    });
    placeClip(clip);
    state.clips.push(clip);
    selectClip(clip.id);
    setDirty(true);
    renderTimeline();
    renderInspector();
    toast(`Added ${media.name} to timeline`);
  }

  function addMediaToTimeline(mediaId) {
    const media = getMedia(mediaId);
    if (!media) return;
    const trackId = media.type === 'audio' ? 'A1' : 'V1';
    const end = state.clips.filter(c => c.trackId === trackId).reduce((m, c) => Math.max(m, c.start + c.duration), 0);
    addClipFromMedia(media, trackId, end);
  }

  function placeClip(clip) {
    const siblings = clipsOnTrack(clip.trackId).filter(c => c.id !== clip.id);
    let guard = 0;
    while (guard++ < 50) {
      const collision = siblings.find(c => clip.start < c.start + c.duration && clip.start + clip.duration > c.start);
      if (!collision) break;
      clip.start = snapTime(collision.start + collision.duration);
    }
  }

  function startClipDrag(e, clipId) {
    const clip = getClip(clipId);
    if (!clip) return;
    const startX = e.clientX;
    const origStart = clip.start;
    let moved = false;
    function onMove(ev) {
      const dx = ev.clientX - startX;
      const dy = ev.clientY - startX; // not used
      if (!moved && Math.abs(dx) < 3) return;
      moved = true;
      const clipEl = document.querySelector(`.clip[data-clip-id="${clipId}"]`);
      if (clipEl) clipEl.classList.add('dragging');
      clip.start = snapTime(Math.max(0, origStart + dx / state.pxPerSec));
      const trackEls = $$('.track');
      for (const t of trackEls) {
        const r = t.getBoundingClientRect();
        if (ev.clientY >= r.top && ev.clientY <= r.bottom) {
          const targetTrack = state.tracks.find(tr => tr.id === t.dataset.trackId);
          if (targetTrack) {
            const canMove = (clip.type === 'audio') === (targetTrack.kind === 'audio');
            if (canMove) clip.trackId = targetTrack.id;
          }
          break;
        }
      }
      renderTimeline();
      selectClip(clipId, { silent: true });
    }
    function onUp() {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      if (moved) { placeClip(clip); setDirty(true); renderTimeline(); renderInspector(); renderPreview(); }
    }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }

  function startTrim(e, clipId, edge) {
    const clip = getClip(clipId);
    if (!clip) return;
    const startX = e.clientX;
    const origStart = clip.start;
    const origDur = clip.duration;
    function onMove(ev) {
      const dx = (ev.clientX - startX) / state.pxPerSec;
      if (edge === 'right') {
        clip.duration = Math.max(0.5, snapTime(origDur + dx));
      } else {
        const newStart = snapTime(origStart + dx);
        const maxStart = origStart + origDur - 0.5;
        const clamped = clamp(newStart, 0, maxStart);
        clip.duration = snapTime(origStart + origDur - clamped);
        clip.start = clamped;
      }
      renderTimeline(); selectClip(clipId, { silent: true }); renderInspector(); renderPreview();
    }
    function onUp() { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); setDirty(true); }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }

  // ---------- Selection / Inspector ----------
  function selectClip(id, opts = {}) {
    state.selectedClipId = id;
    $$('.clip').forEach(el => el.classList.toggle('selected', el.dataset.clipId === id));
    if (!opts.silent) { renderInspector(); renderPreview(); }
  }

  function renderInspector() {
    const clip = getClip(state.selectedClipId);
    const empty = $('#inspectorEmpty');
    const form = $('#inspectorForm');
    const typeEl = $('#inspectorType');
    if (!clip) { empty.style.display='flex'; form.style.display='none'; typeEl.textContent='None'; typeEl.style.color=''; return; }
    empty.style.display='none'; form.style.display='flex'; typeEl.textContent=clip.type;
    const typeColors = { video:'var(--video)', image:'var(--image)', title:'var(--title)', composition:'var(--composition)', audio:'var(--audio)' };
    typeEl.style.color = typeColors[clip.type] || '';
    $('#propName').value = clip.name;
    $('#propStart').value = clip.start.toFixed(2);
    $('#propDuration').value = clip.duration.toFixed(2);
    const showTitle = clip.type === 'title';
    const showComp = clip.type === 'composition';
    const showVolume = clip.type === 'audio' || clip.type === 'video';
    const showColor = clip.type === 'title';
    $('#fieldTitle').style.display = showTitle ? '' : 'none';
    $('#fieldSubtitle').style.display = showTitle ? '' : 'none';
    $('#fieldComposition').style.display = showComp ? '' : 'none';
    $('#fieldVolume').style.display = showVolume ? '' : 'none';
    $('#fieldColor').style.display = showColor ? '' : 'none';
    $('#propTitle').value = clip.title || '';
    $('#propSubtitle').value = clip.subtitle || '';
    $('#propVolume').value = clip.volume;
    $('#propVolumeVal').textContent = clip.volume + '%';
    $('#propColor').value = clip.color || '#f0b45c';
    if (showComp) {
      const imgOptions = MEDIA.filter(m => m.type === 'image').map(m => `<option value="${m.id}">${esc(m.name)}</option>`).join('');
      $('#propCompLeft').innerHTML = imgOptions;
      $('#propCompRight').innerHTML = imgOptions;
      $('#propCompLeft').value = clip.compLeft;
      $('#propCompRight').value = clip.compRight;
    }
    const track = state.tracks.find(t => t.id === clip.trackId);
    const media = clip.mediaId ? getMedia(clip.mediaId) : null;
    $('#inspectorMeta').innerHTML = `<div><strong>Type:</strong> ${esc(clip.type)}</div><div><strong>Track:</strong> ${esc(track ? track.label : clip.trackId)}</div><div><strong>Timeline:</strong> ${fmtTime(clip.start)} – ${fmtTime(clip.start + clip.duration)}</div>${media ? `<div><strong>Source:</strong> ${esc(media.name)}</div>` : ''}`;
  }

  function bindInspector() {
    $('#propName').addEventListener('input', e => { const c=getClip(state.selectedClipId); if(!c) return; c.name=e.target.value; setDirty(true); renderTimeline(); selectClip(c.id,{silent:true}); });
    $('#propStart').addEventListener('change', e => { const c=getClip(state.selectedClipId); if(!c) return; c.start=Math.max(0,parseFloat(e.target.value)||0); placeClip(c); setDirty(true); renderTimeline(); renderInspector(); renderPreview(); });
    $('#propDuration').addEventListener('change', e => { const c=getClip(state.selectedClipId); if(!c) return; c.duration=Math.max(0.5,parseFloat(e.target.value)||0.5); setDirty(true); renderTimeline(); renderInspector(); renderPreview(); });
    $('#propTitle').addEventListener('input', e => { const c=getClip(state.selectedClipId); if(!c) return; c.title=e.target.value; setDirty(true); renderTimeline(); selectClip(c.id,{silent:true}); renderPreview(); });
    $('#propSubtitle').addEventListener('input', e => { const c=getClip(state.selectedClipId); if(!c) return; c.subtitle=e.target.value; setDirty(true); renderPreview(); });
    $('#propCompLeft').addEventListener('change', e => { const c=getClip(state.selectedClipId); if(!c) return; c.compLeft=e.target.value; setDirty(true); renderTimeline(); renderPreview(); });
    $('#propCompRight').addEventListener('change', e => { const c=getClip(state.selectedClipId); if(!c) return; c.compRight=e.target.value; setDirty(true); renderTimeline(); renderPreview(); });
    $('#propVolume').addEventListener('input', e => { const c=getClip(state.selectedClipId); if(!c) return; c.volume=parseInt(e.target.value,10); $('#propVolumeVal').textContent=c.volume+'%'; setDirty(true); renderTimeline(); selectClip(c.id,{silent:true}); });
    $('#propColor').addEventListener('input', e => { const c=getClip(state.selectedClipId); if(!c) return; c.color=e.target.value; setDirty(true); renderPreview(); });
  }

  // ---------- Playhead / Playback ----------
  function setPlayhead(t, opts={}) { state.playhead = clamp(t, 0, totalDuration()); updatePlayhead(); updatePreviewTime(); if (!opts.noPreview) renderPreview(); }
  function updatePlayhead() { $('#playhead').style.left = (state.playhead * state.pxPerSec) + 'px'; }
  function updatePreviewTime() { $('#previewTime').textContent = `${fmtTime(state.playhead)} / ${fmtTime(projectDuration())}`; }
  let lastTick = null;
  function tick(ts) {
    if (!state.playing) { lastTick = null; return; }
    if (lastTick == null) lastTick = ts;
    const dt = (ts - lastTick) / 1000; lastTick = ts;
    let next = state.playhead + dt;
    const end = projectDuration();
    if (next >= end) { state.playhead=end; updatePlayhead(); updatePreviewTime(); renderPreview(); pause(); return; }
    state.playhead = next; updatePlayhead(); updatePreviewTime(); renderPreview();
    requestAnimationFrame(tick);
  }
  function play() { if (state.playing) return; if (state.playhead >= projectDuration()-0.01) setPlayhead(0,{noPreview:true}); state.playing=true; $('#iconPlay').style.display='none'; $('#iconPause').style.display='block'; lastTick=null; requestAnimationFrame(tick); }
  function pause() { state.playing=false; $('#iconPlay').style.display='block'; $('#iconPause').style.display='none'; }
  function togglePlay() { state.playing ? pause() : play(); }

  // ---------- Preview ----------
  function getVisualClipAt(time) {
    const visualTracks = state.tracks.filter(t => t.kind === 'visual');
    for (const t of visualTracks) {
      for (const c of clipsOnTrack(t.id)) { if (time >= c.start && time < c.start + c.duration) return c; }
    }
    return null;
  }

  function renderPreview() {
    const selected = getClip(state.selectedClipId);
    const atPlayhead = getVisualClipAt(state.playhead);
    const clip = atPlayhead || (selected && selected.type !== 'audio' ? selected : null);
    const empty = $('#previewEmpty'), img = $('#previewImage'), vid = $('#previewVideo'), title = $('#previewTitle'), comp = $('#previewComposition');
    [img, vid, title, comp].forEach(el => el.classList.remove('active'));
    img.removeAttribute('src'); vid.removeAttribute('src'); vid.pause();
    if (!clip) { empty.style.display='flex'; return; }
    empty.style.display='none';
    if (clip.type === 'image') {
      const media = getMedia(clip.mediaId);
      if (media && (media.src || media.thumb)) { img.src = media.src || media.thumb; img.alt = media.name; img.classList.add('active'); }
      else { empty.style.display='flex'; }
    } else if (clip.type === 'video') {
      const media = getMedia(clip.mediaId);
      if (media && media.src) {
        vid.src = media.src; vid.classList.add('active');
        if (state.playing) vid.play().catch(() => {});
      } else if (media && media.thumb) { img.src = media.thumb; img.alt = media.name; img.classList.add('active'); }
      else { empty.style.display='flex'; }
    } else if (clip.type === 'title') {
      $('#previewTitleText').textContent = clip.title || clip.name;
      $('#previewTitleSub').textContent = clip.subtitle || '';
      title.style.background = `linear-gradient(135deg, ${clip.color || '#2b2118'}22 0%, #1a1410 50%, ${clip.color || '#2d2418'}22 100%)`;
      title.classList.add('active');
    } else if (clip.type === 'composition') {
      const l = getMedia(clip.compLeft), r = getMedia(clip.compRight);
      $('#compLeft').src = l ? (l.src || l.thumb || '') : '';
      $('#compRight').src = r ? (r.src || r.thumb || '') : '';
      $('#compLeftLabel').textContent = l ? l.name : '';
      $('#compRightLabel').textContent = r ? r.name : '';
      comp.classList.add('active');
    } else { empty.style.display='flex'; }
  }

  // ---------- Zoom / Add ----------
  function setZoom(pxPerSec) { state.pxPerSec = clamp(pxPerSec, state.minPxPerSec, state.maxPxPerSec); renderTimeline(); }
  function updateZoomLabel() { $('#zoomLabel').textContent = Math.round((state.pxPerSec / 80) * 100) + '%'; }
  function addTitleClip() { const end = clipsOnTrack('V1').reduce((m,c)=>Math.max(m,c.start+c.duration),0); const clip=mkClip({trackId:'V1',type:'title',name:'New Title',start:end,duration:3,title:'New Title',subtitle:'Subtitle',color:'#f0b45c'}); placeClip(clip); state.clips.push(clip); setDirty(true); selectClip(clip.id); renderTimeline(); renderInspector(); toast('Title slide added'); }
  function addCompositionClip() { const end = clipsOnTrack('V1').reduce((m,c)=>Math.max(m,c.start+c.duration),0); const imgs=MEDIA.filter(m=>m.type==='image'); const clip=mkClip({trackId:'V1',type:'composition',name:'Side-by-Side',start:end,duration:4,compLeft:imgs[0]?.id,compRight:imgs[1]?.id||imgs[0]?.id}); placeClip(clip); state.clips.push(clip); setDirty(true); selectClip(clip.id); renderTimeline(); renderInspector(); toast('Composition added'); }

  // ---------- Backend wiring ----------
  async function loadFromServer() {
    const [projRes, mediaRes] = await Promise.all([api('/api/project'), api('/api/media')]);
    window.__mediaRaw = mediaRes.media || [];
    MEDIA = window.__mediaRaw.map(normalizeMedia);
    if (projRes.project) {
      projectToState(projRes.project, projRes.path);
    }
    // If project has no media but server has media, keep them; project is source of truth for clips
    renderMedia(); renderTimeline(); renderInspector(); setPlayhead(0);
    if (state.clips.length) selectClip(state.clips[0].id);
  }

  async function saveProject() {
    try {
      const payload = { project: buildProjectPayload() };
      if (state.projectPath) payload.path = state.projectPath;
      const res = await api('/api/project/save', { method: 'POST', body: JSON.stringify(payload) });
      state.projectPath = res.path;
      state.projectName = res.project.name;
      $('#projectName').textContent = state.projectName;
      setDirty(false);
      toast('Project saved');
    } catch (e) { console.error(e); toast('Save failed: ' + e.message); }
  }

  async function openProject() {
    const path = prompt('Enter path to .recapper.json project file:', state.projectPath || '');
    if (!path) return;
    try {
      const res = await api('/api/project/load', { method: 'POST', body: JSON.stringify({ path }) });
      window.__mediaRaw = (res.project.media || []);
      MEDIA = window.__mediaRaw.map(normalizeMedia);
      projectToState(res.project, res.path);
      renderMedia(); renderTimeline(); renderInspector(); setPlayhead(0);
      if (state.clips.length) selectClip(state.clips[0].id);
      toast('Project loaded');
    } catch (e) { console.error(e); toast('Open failed: ' + e.message); }
  }

  async function newProject() {
    if (state.dirty && !confirm('Discard unsaved changes?')) return;
    const name = prompt('Project name:', 'Untitled Recap');
    if (name === null) return;
    try {
      const res = await api('/api/project/new', { method: 'POST', body: JSON.stringify({ name: name || 'Untitled Recap' }) });
      window.__mediaRaw = [];
      MEDIA = [];
      projectToState(res.project, res.path);
      renderMedia(); renderTimeline(); renderInspector(); setPlayhead(0);
      toast('New project created');
    } catch (e) { console.error(e); toast('Failed: ' + e.message); }
  }

  async function importMediaFiles(files) {
    const arr = Array.from(files || []);
    if (!arr.length) return;
    let ok = 0;
    for (const file of arr) {
      try {
        const res = await fetch(`/api/media/upload?name=${encodeURIComponent(file.name)}`, {
          method: 'POST',
          headers: { 'X-Filename': file.name, 'Content-Type': 'application/octet-stream' },
          body: file,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data?.error?.message || 'Upload failed');
        const m = data.media;
        window.__mediaRaw = window.__mediaRaw || [];
        // replace or add
        const idx = window.__mediaRaw.findIndex(x => x.id === m.id);
        if (idx >= 0) window.__mediaRaw[idx] = m; else window.__mediaRaw.push(m);
        ok++;
      } catch (e) { console.error(e); toast(`Import failed: ${file.name}`); }
    }
    MEDIA = (window.__mediaRaw || []).map(normalizeMedia);
    renderMedia();
    setDirty(true);
    if (ok) toast(`Imported ${ok} file${ok!==1?'s':''}`);
  }

  // ---------- Export ----------
  let exportPoll = null;
  async function openExportModal() {
    $('#exportModal').style.display = 'flex';
    $('#exportName').value = state.render?.output_name || 'recap.mp4';
    $('#exportWidth').value = state.render?.width || 1920;
    $('#exportHeight').value = state.render?.height || 1080;
    $('#exportFps').value = state.render?.fps || 30;
    $('#exportCrf').value = state.render?.crf ?? 18;
    $('#exportLog').textContent = '';
    $('#exportProgressBar').style.width = '0%';
    $('#exportProgressText').textContent = 'Idle';
    try {
      const sys = await api('/api/system/check');
      $('#exportSystemStatus').textContent = sys.ok ? `ffmpeg: ${sys.ffmpeg?.version || 'ok'}\nffprobe: ${sys.ffprobe?.version || 'ok'}` : (sys.error || 'ffmpeg/ffprobe not available');
      $('#btnStartExport').disabled = !sys.ok;
    } catch (e) {
      $('#exportSystemStatus').textContent = 'Failed to check ffmpeg: ' + e.message;
      $('#btnStartExport').disabled = true;
    }
  }
  function closeExportModal() { $('#exportModal').style.display = 'none'; if (exportPoll) { clearInterval(exportPoll); exportPoll=null; } }

  async function startExport() {
    try {
      state.render = {
        ...(state.render || {}),
        output_name: $('#exportName').value || 'recap.mp4',
        width: parseInt($('#exportWidth').value,10) || 1920,
        height: parseInt($('#exportHeight').value,10) || 1080,
        fps: parseInt($('#exportFps').value,10) || 30,
        crf: parseInt($('#exportCrf').value,10) || 18,
      };
      setDirty(true);
      const payload = { project: buildProjectPayload(), output_name: state.render.output_name };
      const res = await api('/api/render/export', { method: 'POST', body: JSON.stringify(payload) });
      const jobId = res.job.id;
      $('#exportProgressText').textContent = 'Queued...';
      $('#exportLog').textContent = '';
      if (exportPoll) clearInterval(exportPoll);
      exportPoll = setInterval(async () => {
        try {
          const jr = await api(`/api/jobs/${jobId}`);
          const job = jr.job;
          const pct = Math.max(0, Math.min(100, Number(job.progress || 0)));
          $('#exportProgressBar').style.width = pct + '%';
          $('#exportProgressText').textContent = `${job.status} - ${job.stage || ''} ${job.message || ''}`.trim();
          $('#exportLog').textContent = (job.logs || []).slice(-80).join('\n');
          if (job.status === 'completed') {
            clearInterval(exportPoll); exportPoll = null;
            toast('Export completed');
            if (job.result?.output_path) {
              $('#exportProgressText').textContent = `Completed: ${job.result.output_path}`;
            }
          } else if (job.status === 'failed') {
            clearInterval(exportPoll); exportPoll = null;
            toast('Export failed');
          }
        } catch (e) { console.error(e); }
      }, 1000);
    } catch (e) { console.error(e); toast('Export failed: ' + e.message); }
  }

  // ---------- UI binding ----------
  function bindUI() {
    $$('.media-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        $$('.media-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        state.mediaFilter = tab.dataset.filter;
        renderMedia();
      });
    });

    $('#btnPlay').addEventListener('click', togglePlay);
    $('#btnSkipBack').addEventListener('click', () => { setPlayhead(0); });
    $('#btnSkipForward').addEventListener('click', () => { setPlayhead(projectDuration()); });
    $('#btnZoomIn').addEventListener('click', () => setZoom(state.pxPerSec + 15));
    $('#btnZoomOut').addEventListener('click', () => setZoom(state.pxPerSec - 15));
    $('#btnAddTitle').addEventListener('click', addTitleClip);
    $('#btnAddComp').addEventListener('click', addCompositionClip);

    $('#btnImportMedia').addEventListener('click', () => $('#mediaFileInput').click());
    $('#mediaFileInput').addEventListener('change', (e) => { importMediaFiles(e.target.files); e.target.value = ''; });
    const mediaPanel = document.querySelector('.media-panel');
    mediaPanel.addEventListener('dragover', (e) => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); mediaPanel.classList.add('drag-over'); } });
    mediaPanel.addEventListener('dragleave', () => mediaPanel.classList.remove('drag-over'));
    mediaPanel.addEventListener('drop', (e) => {
      if (e.dataTransfer.files && e.dataTransfer.files.length) { e.preventDefault(); mediaPanel.classList.remove('drag-over'); importMediaFiles(e.dataTransfer.files); }
    });
    $('#btnSaveProject').addEventListener('click', saveProject);
    $('#btnOpenProject').addEventListener('click', openProject);
    $('#btnNewProject').addEventListener('click', newProject);

    $('#btnExport').addEventListener('click', openExportModal);
    $('#btnCloseExport').addEventListener('click', closeExportModal);
    $('#btnCloseExport2').addEventListener('click', closeExportModal);
    $('#btnStartExport').addEventListener('click', startExport);
    $('#exportModal').addEventListener('click', (e) => { if (e.target.id === 'exportModal') closeExportModal(); });

    $('#timelineScroll').addEventListener('wheel', (e) => {
      if (e.ctrlKey || e.metaKey) { e.preventDefault(); setZoom(state.pxPerSec + (e.deltaY < 0 ? 10 : -10)); }
    }, { passive: false });

    window.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') { e.preventDefault(); saveProject(); return; }
      if (e.target.matches('input, textarea, select')) return;
      if (e.code === 'Space') { e.preventDefault(); togglePlay(); }
      if (e.code === 'Home') { e.preventDefault(); setPlayhead(0); }
      if (e.code === 'End') { e.preventDefault(); setPlayhead(projectDuration()); }
      if (e.code === 'Delete' || e.code === 'Backspace') {
        if (state.selectedClipId) { state.clips = state.clips.filter(c => c.id !== state.selectedClipId); selectClip(null); setDirty(true); renderTimeline(); }
      }
      if (e.key === '=' || e.key === '+') { setZoom(state.pxPerSec + 10); }
      if (e.key === '-') { setZoom(state.pxPerSec - 10); }
    });

    bindInspector();
  }

  // ---------- Init ----------
  async function init() {
    state.render = state.render || { width:1920, height:1080, fps:30, crf:18, output_name:'recap.mp4' };
    bindUI();
    try {
      await loadFromServer();
      // If server has no clips/media, seed with a friendly default project in memory only
      if (!state.clips.length && !MEDIA.length) {
        // try to register existing static demo images as convenience
        const demoPaths = [];
        toast('Empty project - import media to get started');
      }
    } catch (e) {
      console.error(e);
      // fallback to empty state
      MEDIA = []; state.clips = []; renderMedia(); renderTimeline(); renderInspector(); setPlayhead(0);
      toast('Failed to load project: ' + e.message);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
