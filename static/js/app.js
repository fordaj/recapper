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

  // ---------- Data ----------
  const MEDIA = [
    { id: 'm1', type: 'image', name: 'Family Beach Day', src: '/static/media/images/family.jpg', duration: 4, subtitle: 'Photo' },
    { id: 'm2', type: 'image', name: 'Sunset', src: '/static/media/images/sunset.jpg', duration: 3.5, subtitle: 'Photo' },
    { id: 'm3', type: 'image', name: 'Campfire', src: '/static/media/images/campfire.jpg', duration: 4, subtitle: 'Photo' },
    { id: 'm4', type: 'image', name: 'Lake', src: '/static/media/images/lake.jpg', duration: 3.5, subtitle: 'Photo' },
    { id: 'm5', type: 'image', name: 'Forest Walk', src: '/static/media/images/forest.jpg', duration: 3, subtitle: 'Photo' },
    { id: 'm6', type: 'image', name: 'Picnic', src: '/static/media/images/picnic.jpg', duration: 3.5, subtitle: 'Photo' },
    { id: 'm7', type: 'image', name: 'Boat Ride', src: '/static/media/images/boat.jpg', duration: 4, subtitle: 'Photo' },
    { id: 'm8', type: 'image', name: 'Beach', src: '/static/media/images/beach.jpg', duration: 3.5, subtitle: 'Photo' },
    { id: 'm9', type: 'video', name: 'Kids Playing', src: '', duration: 6, subtitle: 'Video clip', color: '#3b6ea8', thumb: '/static/media/images/beach.jpg' },
    { id: 'm10', type: 'video', name: 'Fireworks', src: '', duration: 5, subtitle: 'Video clip', color: '#7a4a2a', thumb: '/static/media/images/sunset.jpg' },
    { id: 'm11', type: 'audio', name: 'Acoustic Guitar', src: '', duration: 20, subtitle: 'Music track' },
    { id: 'm12', type: 'audio', name: 'Ambient Waves', src: '', duration: 18, subtitle: 'Ambient audio' },
  ];

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
  };

  function defaultClips() {
    state.clips = [
      mkClip({ trackId: 'V1', type: 'title', name: 'Opening Title', start: 0, duration: 3, title: 'Summer 2026', subtitle: 'The Anderson Family Recap', color: '#f0b45c' }),
      mkClip({ trackId: 'V1', type: 'image', name: 'Family Beach Day', start: 3, duration: 4, mediaId: 'm1' }),
      mkClip({ trackId: 'V1', type: 'image', name: 'Sunset', start: 7, duration: 3.5, mediaId: 'm2' }),
      mkClip({ trackId: 'V1', type: 'video', name: 'Kids Playing', start: 10.5, duration: 5, mediaId: 'm9' }),
      mkClip({ trackId: 'V1', type: 'composition', name: 'Lake & Boat', start: 15.5, duration: 4, compLeft: 'm4', compRight: 'm7', title: 'Side by Side' }),
      mkClip({ trackId: 'V1', type: 'image', name: 'Campfire', start: 19.5, duration: 4, mediaId: 'm3' }),
      mkClip({ trackId: 'V1', type: 'title', name: 'Closing Title', start: 23.5, duration: 3, title: 'Until Next Summer', subtitle: 'Made with Recapper', color: '#f0b45c' }),
      mkClip({ trackId: 'A1', type: 'audio', name: 'Acoustic Guitar', start: 0, duration: 26.5, mediaId: 'm11', volume: 80 }),
    ];
  }

  function mkClip(opts) {
    return {
      id: uid(),
      trackId: opts.trackId,
      type: opts.type,
      name: opts.name || 'Clip',
      start: opts.start || 0,
      duration: opts.duration || 3,
      mediaId: opts.mediaId || null,
      title: opts.title || '',
      subtitle: opts.subtitle || '',
      compLeft: opts.compLeft || 'm4',
      compRight: opts.compRight || 'm7',
      volume: opts.volume != null ? opts.volume : 100,
      color: opts.color || '#ff7a45',
    };
  }

  function getMedia(id) { return MEDIA.find(m => m.id === id); }
  function getClip(id) { return state.clips.find(c => c.id === id); }
  function clipsOnTrack(trackId) { return state.clips.filter(c => c.trackId === trackId).sort((a,b) => a.start - b.start); }
  function projectDuration() {
    return Math.max(10, ...state.clips.map(c => c.start + c.duration));
  }
  function totalDuration() { return projectDuration() + 4; }

  // ---------- Media Library ----------
  function renderMedia() {
    const grid = $('#mediaGrid');
    const filter = state.mediaFilter;
    const items = MEDIA.filter(m => filter === 'all' || m.type === filter);
    $('#mediaCount').textContent = `${items.length} item${items.length !== 1 ? 's' : ''}`;
    grid.innerHTML = items.map(m => {
      const badge = `<span class="media-badge badge-${m.type}">${m.type}</span>`;
      const dur = `<span class="media-duration">${fmtShort(m.duration)}</span>`;
      let thumb = '';
      if (m.type === 'image') {
        thumb = `<img src="${m.src}" alt="${esc(m.name)}" loading="lazy">`;
      } else if (m.type === 'video') {
        thumb = m.thumb ? `<img src="${m.thumb}" alt="${esc(m.name)}" loading="lazy"><div class="media-icon" style="position:absolute;inset:0;background:rgba(0,0,0,0.25)"><svg width="28" height="28" viewBox="0 0 24 24" fill="white"><path d="M8 5l11 7-11 7V5z"/></svg></div>`
                        : `<div class="media-icon"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="4" width="20" height="14" rx="2"/><path d="M10 9l5 3-5 3V9z"/></svg></div>`;
      } else {
        thumb = `<div class="media-icon" style="background:linear-gradient(135deg,rgba(78,205,196,0.15),transparent)"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg></div>`;
      }
      return `<div class="media-card" draggable="true" data-media-id="${m.id}">
        <div class="media-thumb">${badge}${thumb}${dur}</div>
        <div class="media-meta"><div class="media-name" title="${esc(m.name)}">${esc(m.name)}</div><div class="media-sub">${esc(m.subtitle)}</div></div>
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
        <div><div>${esc(t.label)}</div><small>${esc(t.sub)}</small></div>
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
      bg = `<div class="clip-bg-strip">${thumbStrip(media.src, width)}</div>`;
      inner = `<div class="clip-thumb">${bg}<span class="clip-badge">IMG</span><div class="clip-content"><div class="clip-name">${esc(c.name)}</div><div class="clip-meta">${c.duration.toFixed(1)}s</div></div></div>`;
    } else if (c.type === 'video') {
      const src = (media && (media.thumb || media.src)) || '';
      bg = src ? `<div class="clip-bg-strip">${thumbStrip(src, width)}</div>` : '';
      inner = `<div class="clip-thumb">${bg}<span class="clip-badge">VID</span><div class="clip-content"><div class="clip-name">${esc(c.name)}</div><div class="clip-meta">${c.duration.toFixed(1)}s</div></div></div>`;
    } else if (c.type === 'title') {
      inner = `<div class="clip-thumb"><span class="clip-badge">T</span><div class="clip-content"><div class="clip-name">${esc(c.title || c.name)}</div><div class="clip-meta">Title slide · ${c.duration.toFixed(1)}s</div></div></div>`;
    } else if (c.type === 'composition') {
      const l = getMedia(c.compLeft); const r = getMedia(c.compRight);
      const lSrc = l ? l.src || l.thumb || '' : '';
      const rSrc = r ? r.src || r.thumb || '' : '';
      bg = `<div class="clip-bg-strip" style="opacity:0.35">${lSrc ? `<img src="${lSrc}" alt="">` : ''}${rSrc ? `<img src="${rSrc}" alt="">` : ''}</div>`;
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
    for (let i = 0; i < count; i++) out += `<img src="${src}" alt="" loading="lazy">`;
    return out;
  }

  function waveformBars(width) {
    const count = Math.max(12, Math.floor(width / 5));
    let out = '';
    // deterministic pseudo waveform from index
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
        if (e.dataTransfer.types.includes('text/plain')) {
          e.preventDefault();
          trackEl.classList.add('drag-over');
        }
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
        // click on track sets playhead
        const rect = trackEl.getBoundingClientRect();
        const x = e.clientX - rect.left + $('#timelineScroll').scrollLeft;
        setPlayhead(Math.max(0, x / state.pxPerSec));
        selectClip(null);
      });
    });

    // ruler click sets playhead
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
          e.stopPropagation();
          e.preventDefault();
          selectClip(el.dataset.clipId);
          startTrim(e, el.dataset.clipId, handle.dataset.edge);
        });
      });
    });
  }

  function snapTime(t) { return Math.round(t * 4) / 4; } // 0.25s snap

  function addClipFromMedia(media, trackId, start) {
    const clip = mkClip({
      trackId,
      type: media.type,
      name: media.name,
      start,
      duration: media.duration,
      mediaId: media.id,
      volume: media.type === 'audio' ? 80 : 100,
    });
    placeClip(clip);
    state.clips.push(clip);
    selectClip(clip.id);
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
    // Avoid exact overlap by nudging right if needed
    const siblings = clipsOnTrack(clip.trackId).filter(c => c.id !== clip.id);
    let guard = 0;
    while (guard++ < 50) {
      const collision = siblings.find(c => clip.start < c.start + c.duration && clip.start + clip.duration > c.start);
      if (!collision) break;
      clip.start = snapTime(collision.start + collision.duration);
    }
  }

  // ---------- Drag reorder ----------
  function startClipDrag(e, clipId) {
    const clip = getClip(clipId);
    if (!clip) return;
    const startX = e.clientX;
    const startY = e.clientY;
    const origStart = clip.start;
    const origTrack = clip.trackId;
    const trackEl = document.querySelector(`.track[data-track-id="${origTrack}"]`);
    const scrollEl = $('#timelineScroll');
    let moved = false;

    function onMove(ev) {
      const dx = ev.clientX - startX;
      const dy = ev.clientY - startY;
      if (!moved && Math.abs(dx) < 3 && Math.abs(dy) < 3) return;
      moved = true;
      const clipEl = document.querySelector(`.clip[data-clip-id="${clipId}"]`);
      if (clipEl) clipEl.classList.add('dragging');

      const newStart = snapTime(Math.max(0, origStart + dx / state.pxPerSec));
      clip.start = newStart;

      // determine track under cursor
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
      // reselect to keep selection
      selectClip(clipId, { silent: true });
    }

    function onUp() {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      if (moved) {
        placeClip(clip);
        renderTimeline();
        renderInspector();
        renderPreview();
      }
    }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }

  // ---------- Trim ----------
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
      renderTimeline();
      selectClip(clipId, { silent: true });
      renderInspector();
      renderPreview();
    }
    function onUp() {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }

  // ---------- Selection ----------
  function selectClip(id, opts = {}) {
    state.selectedClipId = id;
    $$('.clip').forEach(el => el.classList.toggle('selected', el.dataset.clipId === id));
    if (!opts.silent) {
      renderInspector();
      renderPreview();
    }
  }

  // ---------- Inspector ----------
  function renderInspector() {
    const clip = getClip(state.selectedClipId);
    const empty = $('#inspectorEmpty');
    const form = $('#inspectorForm');
    const typeEl = $('#inspectorType');
    if (!clip) {
      empty.style.display = 'flex';
      form.style.display = 'none';
      typeEl.textContent = 'None';
      typeEl.style.color = '';
      return;
    }
    empty.style.display = 'none';
    form.style.display = 'flex';
    typeEl.textContent = clip.type;
    const typeColors = { video: 'var(--video)', image: 'var(--image)', title: 'var(--title)', composition: 'var(--composition)', audio: 'var(--audio)' };
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
    $('#inspectorMeta').innerHTML = `
      <div><strong>Type:</strong> ${esc(clip.type)}</div>
      <div><strong>Track:</strong> ${esc(track ? track.label : clip.trackId)}</div>
      <div><strong>Timeline:</strong> ${fmtTime(clip.start)} – ${fmtTime(clip.start + clip.duration)}</div>
      ${media ? `<div><strong>Source:</strong> ${esc(media.name)}</div>` : ''}
    `;
  }

  function bindInspector() {
    $('#propName').addEventListener('input', e => { const c = getClip(state.selectedClipId); if (!c) return; c.name = e.target.value; renderTimeline(); selectClip(c.id, {silent:true}); });
    $('#propStart').addEventListener('change', e => { const c = getClip(state.selectedClipId); if (!c) return; c.start = Math.max(0, parseFloat(e.target.value) || 0); placeClip(c); renderTimeline(); renderInspector(); renderPreview(); });
    $('#propDuration').addEventListener('change', e => { const c = getClip(state.selectedClipId); if (!c) return; c.duration = Math.max(0.5, parseFloat(e.target.value) || 0.5); renderTimeline(); renderInspector(); renderPreview(); });
    $('#propTitle').addEventListener('input', e => { const c = getClip(state.selectedClipId); if (!c) return; c.title = e.target.value; renderTimeline(); selectClip(c.id, {silent:true}); renderPreview(); });
    $('#propSubtitle').addEventListener('input', e => { const c = getClip(state.selectedClipId); if (!c) return; c.subtitle = e.target.value; renderPreview(); });
    $('#propCompLeft').addEventListener('change', e => { const c = getClip(state.selectedClipId); if (!c) return; c.compLeft = e.target.value; renderTimeline(); renderPreview(); });
    $('#propCompRight').addEventListener('change', e => { const c = getClip(state.selectedClipId); if (!c) return; c.compRight = e.target.value; renderTimeline(); renderPreview(); });
    $('#propVolume').addEventListener('input', e => { const c = getClip(state.selectedClipId); if (!c) return; c.volume = parseInt(e.target.value, 10); $('#propVolumeVal').textContent = c.volume + '%'; renderTimeline(); selectClip(c.id, {silent:true}); });
    $('#propColor').addEventListener('input', e => { const c = getClip(state.selectedClipId); if (!c) return; c.color = e.target.value; renderPreview(); });
  }

  // ---------- Playhead / Playback ----------
  function setPlayhead(t, opts = {}) {
    state.playhead = clamp(t, 0, totalDuration());
    updatePlayhead();
    updatePreviewTime();
    if (!opts.noPreview) renderPreview();
  }

  function updatePlayhead() {
    const ph = $('#playhead');
    ph.style.left = (state.playhead * state.pxPerSec) + 'px';
  }

  function updatePreviewTime() {
    $('#previewTime').textContent = `${fmtTime(state.playhead)} / ${fmtTime(projectDuration())}`;
  }

  let lastTick = null;
  function tick(ts) {
    if (!state.playing) { lastTick = null; return; }
    if (lastTick == null) lastTick = ts;
    const dt = (ts - lastTick) / 1000;
    lastTick = ts;
    let next = state.playhead + dt;
    const end = projectDuration();
    if (next >= end) {
      next = end;
      state.playhead = next;
      updatePlayhead();
      updatePreviewTime();
      renderPreview();
      pause();
      return;
    }
    state.playhead = next;
    updatePlayhead();
    updatePreviewTime();
    renderPreview();
    requestAnimationFrame(tick);
  }

  function play() {
    if (state.playing) return;
    if (state.playhead >= projectDuration() - 0.01) setPlayhead(0, { noPreview: true });
    state.playing = true;
    $('#iconPlay').style.display = 'none';
    $('#iconPause').style.display = 'block';
    lastTick = null;
    requestAnimationFrame(tick);
  }
  function pause() {
    state.playing = false;
    $('#iconPlay').style.display = 'block';
    $('#iconPause').style.display = 'none';
  }
  function togglePlay() { state.playing ? pause() : play(); }

  // ---------- Preview ----------
  function getVisualClipAt(time) {
    // topmost visual track first (V1 only here, but future-proof)
    const visualTracks = state.tracks.filter(t => t.kind === 'visual');
    for (const t of visualTracks) {
      const clips = clipsOnTrack(t.id);
      for (const c of clips) {
        if (time >= c.start && time < c.start + c.duration) return c;
      }
    }
    return null;
  }

  function renderPreview() {
    const selected = getClip(state.selectedClipId);
    // Prefer clip under playhead; fall back to selected
    const atPlayhead = getVisualClipAt(state.playhead);
    const clip = atPlayhead || (selected && selected.type !== 'audio' ? selected : null);

    const empty = $('#previewEmpty');
    const img = $('#previewImage');
    const vid = $('#previewVideo');
    const title = $('#previewTitle');
    const comp = $('#previewComposition');

    [img, vid, title, comp].forEach(el => el.classList.remove('active'));
    img.removeAttribute('src');
    vid.removeAttribute('src'); vid.pause();

    if (!clip) { empty.style.display = 'flex'; return; }
    empty.style.display = 'none';

    if (clip.type === 'image') {
      const media = getMedia(clip.mediaId);
      if (media && media.src) { img.src = media.src; img.alt = media.name; img.classList.add('active'); }
      else { empty.style.display = 'flex'; }
    } else if (clip.type === 'video') {
      const media = getMedia(clip.mediaId);
      if (media && media.src) {
        vid.src = media.src; vid.classList.add('active');
        if (state.playing) vid.play().catch(() => {});
      } else {
        // demo placeholder: show thumbnail as still
        if (media && media.thumb) { img.src = media.thumb; img.alt = media.name; img.classList.add('active'); }
        else { empty.style.display = 'flex'; }
      }
    } else if (clip.type === 'title') {
      $('#previewTitleText').textContent = clip.title || clip.name;
      $('#previewTitleSub').textContent = clip.subtitle || '';
      title.style.background = `linear-gradient(135deg, ${clip.color || '#2b2118'}22 0%, #1a1410 50%, ${clip.color || '#2d2418'}22 100%)`;
      title.classList.add('active');
    } else if (clip.type === 'composition') {
      const l = getMedia(clip.compLeft); const r = getMedia(clip.compRight);
      $('#compLeft').src = l ? (l.src || l.thumb || '') : '';
      $('#compRight').src = r ? (r.src || r.thumb || '') : '';
      $('#compLeftLabel').textContent = l ? l.name : '';
      $('#compRightLabel').textContent = r ? r.name : '';
      comp.classList.add('active');
    } else {
      empty.style.display = 'flex';
    }
  }

  // ---------- Zoom ----------
  function setZoom(pxPerSec) {
    state.pxPerSec = clamp(pxPerSec, state.minPxPerSec, state.maxPxPerSec);
    renderTimeline();
  }
  function updateZoomLabel() {
    const pct = Math.round((state.pxPerSec / 80) * 100);
    $('#zoomLabel').textContent = pct + '%';
  }

  // ---------- Add clips ----------
  function addTitleClip() {
    const end = clipsOnTrack('V1').reduce((m,c) => Math.max(m, c.start + c.duration), 0);
    const clip = mkClip({ trackId: 'V1', type: 'title', name: 'New Title', start: end, duration: 3, title: 'New Title', subtitle: 'Subtitle', color: '#f0b45c' });
    placeClip(clip); state.clips.push(clip); selectClip(clip.id); renderTimeline(); renderInspector(); toast('Title slide added');
  }
  function addCompositionClip() {
    const end = clipsOnTrack('V1').reduce((m,c) => Math.max(m, c.start + c.duration), 0);
    const imgs = MEDIA.filter(m => m.type === 'image');
    const clip = mkClip({ trackId: 'V1', type: 'composition', name: 'Side-by-Side', start: end, duration: 4, compLeft: imgs[0]?.id || 'm4', compRight: imgs[1]?.id || 'm7' });
    placeClip(clip); state.clips.push(clip); selectClip(clip.id); renderTimeline(); renderInspector(); toast('Composition added');
  }

  // ---------- Events ----------
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
    $('#btnExport').addEventListener('click', () => toast('Export is a demo in this prototype'));

    // timeline scroll wheel zoom with ctrl/cmd
    $('#timelineScroll').addEventListener('wheel', (e) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        setZoom(state.pxPerSec + (e.deltaY < 0 ? 10 : -10));
      }
    }, { passive: false });

    // keyboard
    window.addEventListener('keydown', (e) => {
      if (e.target.matches('input, textarea, select')) return;
      if (e.code === 'Space') { e.preventDefault(); togglePlay(); }
      if (e.code === 'Home') { e.preventDefault(); setPlayhead(0); }
      if (e.code === 'End') { e.preventDefault(); setPlayhead(projectDuration()); }
      if (e.code === 'Delete' || e.code === 'Backspace') {
        if (state.selectedClipId) {
          state.clips = state.clips.filter(c => c.id !== state.selectedClipId);
          selectClip(null);
          renderTimeline();
        }
      }
      if (e.key === '=' || e.key === '+') { setZoom(state.pxPerSec + 10); }
      if (e.key === '-') { setZoom(state.pxPerSec - 10); }
    });

    bindInspector();
  }

  // ---------- Init ----------
  function init() {
    defaultClips();
    bindUI();
    renderMedia();
    renderTimeline();
    renderInspector();
    setPlayhead(0);
    // select first clip for a nice initial state
    if (state.clips.length) selectClip(state.clips[0].id);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
