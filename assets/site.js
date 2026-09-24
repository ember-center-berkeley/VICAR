/* Static project page. No framework, build step, or third-party runtime requests. */
(() => {
  'use strict';
  const content = window.VICAR;
  if (!content) return;
  const $ = (selector) => document.querySelector(selector);
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  document.querySelectorAll('[data-resource]').forEach(link => {
    link.href = content.links[link.dataset.resource] || './';
  });
  $('#abstract-text').textContent = content.abstract;
  if (content.authors.length) {
    const authors = $('#authors');
    authors.hidden = false;
    content.authors.forEach((author, index) => {
      if (index) authors.append(document.createTextNode(' · '));
      const link = element('a', '', author.name);
      link.href = author.url || './';
      authors.append(link);
    });
  }
  if (content.affiliations) {
    $('#affiliations').textContent = content.affiliations;
    $('#affiliations').hidden = false;
  }
  const artPaths = {
    serve: '<path d="M8 52h79M15 52l-4 17m67-17 5 17M47 41v14M10 58h73"/><path d="m67 23 9-11c6-7 17 3 11 10L76 33zM69 29l-9 12"/><circle cx="35" cy="26" r="4"/><path d="M17 34c4-10 11-14 18-14" stroke-dasharray="3 5"/>',
    pickup: '<path d="M14 42h68M22 42v27m52-27v27M45 31V18h16v13zM26 12l-9 10 12 14 16-11"/><circle cx="28" cy="7" r="5"/><path d="m22 36 9 15-7 18M17 22l-6 28-5 18"/>',
    'under-table': '<path d="M34 30h52M43 30v39m35-39v39M55 68V54h14v14zM24 36l14-9m-14 9 6 15 24 8M24 36l-9 19 9 10M15 55l-9 14"/><circle cx="24" cy="26" r="5"/>',
    bimanual: '<path d="M35 35h29v25H35zM23 20l8 18 8 7M76 20l-8 18-8 7M29 20h40M34 20l-5 37-5 32M64 20l5 37 5 32"/><circle cx="49" cy="9" r="7"/>',
    ladder: '<path d="M56 5v65M83 5v65M56 16h27M56 32h27M56 48h27M56 64h27M32 27l12 4 15-16M32 27l1 22 23-1M33 49l-13 18M32 27l-12 15"/><circle cx="32" cy="16" r="6"/>'
  };
  function placeholder(item, number, failed = false) {
    const node = element('div', 'media-placeholder');
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 100 78');
    svg.setAttribute('aria-hidden', 'true');
    svg.classList.add('skill-art');
    svg.innerHTML = artPaths[item.art || 'serve'];
    node.append(element('span', 'media-index', String(number).padStart(2, '0')), svg,
      element('span', 'video-label', failed ? 'Video unavailable' : 'Video coming soon'));
    if (failed) node.setAttribute('role', 'status');
    return node;
  }
  function videoCard(item, number) {
    const card = element('article', 'video-card');
    card.id = item.id;
    const slot = element('div', 'media-slot');
    if (item.src) {
      const video = document.createElement('video');
      video.controls = true;
      video.playsInline = true;
      video.preload = 'none';
      video.setAttribute('aria-label', item.title);
      if (item.poster) video.poster = item.poster;
      if (item.captions) {
        const track = document.createElement('track');
        Object.assign(track, {kind: 'captions', src: item.captions, srclang: 'en', label: 'English'});
        video.append(track);
      }
      video.addEventListener('error', () => slot.replaceChildren(placeholder(item, number, true)), {once: true});
      video.src = item.src;
      slot.append(video);
    } else slot.append(placeholder(item, number));
    const copy = element('div', 'video-copy');
    const meta = element('div', 'video-meta');
    (item.tags || []).forEach(tag => meta.append(element('span', '', tag)));
    copy.append(element('h3', '', item.title), element('p', '', item.description), meta);
    card.append(slot, copy);
    return card;
  }
  const track = $('#serve-track');
  content.serves.forEach((item, index) => track.append(videoCard(item, index + 1)));
  content.skills.forEach((item, index) => $('#other-skills').append(videoCard(item, index + 7)));
  if ([...content.serves, ...content.skills].every(item => item.src)) {
    $('.media-note').hidden = true;
    document.querySelectorAll('.section-tag').forEach(el => el.hidden = true);
  }
  let activeServe = 0;
  const dots = content.serves.map((serve, i) => {
    const dot = element('button');
    dot.setAttribute('aria-label', `Show ${serve.title.toLowerCase()}`);
    dot.addEventListener('click', () => moveTo(i));
    $('#serve-dots').append(dot);
    return dot;
  });
  // Pad the end so every card, including the sixth, can become the first visible card.
  function sizeTrack() {
    const first = track.firstElementChild;
    if (!first) return;
    const gap = parseFloat(getComputedStyle(track).gap);
    const endSpace = Math.max(0, track.clientWidth - first.offsetWidth - gap);
    let spacer = track.querySelector('.carousel-spacer');
    if (!spacer) {
      spacer = element('div', 'carousel-spacer');
      spacer.setAttribute('aria-hidden', 'true');
      track.append(spacer);
    }
    spacer.style.flex = `0 0 ${endSpace}px`;
  }
  function updateCarousel() {
    const step = track.children[1] ? track.children[1].offsetLeft - track.children[0].offsetLeft : 1;
    activeServe = Math.max(0, Math.min(content.serves.length - 1, Math.round(track.scrollLeft / step)));
    dots.forEach((dot, i) => dot.setAttribute('aria-current', String(i === activeServe)));
    $('#serve-prev').disabled = activeServe === 0;
    $('#serve-next').disabled = activeServe === content.serves.length - 1;
  }
  function moveTo(index) {
    index = Math.max(0, Math.min(content.serves.length - 1, index));
    const target = track.children[index];
    track.scrollTo({left: target.offsetLeft - track.firstElementChild.offsetLeft, behavior: reducedMotion.matches ? 'instant' : 'smooth'});
  }
  $('#serve-prev').addEventListener('click', () => moveTo(activeServe - 1));
  $('#serve-next').addEventListener('click', () => moveTo(activeServe + 1));
  track.addEventListener('keydown', event => {
    if (event.target !== track) return;
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault();
      moveTo(activeServe + (event.key === 'ArrowRight' ? 1 : -1));
    }
  });
  track.addEventListener('scroll', updateCarousel, {passive: true});
  new ResizeObserver(() => { sizeTrack(); updateCarousel(); }).observe(track);
  sizeTrack(); updateCarousel();
  // Pause clips once they scroll away; never autoplay six videos at once.
  const mediaObserver = new IntersectionObserver(entries => entries.forEach(entry => {
    if (!entry.isIntersecting) entry.target.pause();
  }), {threshold: .15});
  document.querySelectorAll('video').forEach(video => mediaObserver.observe(video));

  const sceneSelect = $('#demo-scene');
  const viewer = $('#viser-frame');
  let scene = content.viewer.scenes[0];
  let variant = scene.variants[0];
  let loaded = false;
  let loadVersion = 0;
  function viewerURL() {
    if (variant.embedUrl) return new URL(variant.embedUrl, document.baseURI).href;
    const url = new URL(content.viewer.client, document.baseURI);
    url.searchParams.set('playbackPath', new URL(variant.recording, document.baseURI).href);
    return url.href;
  }
  function updateViewerInfo() {
    $('#open-viewer').href = viewerURL();
    $('#demo-description').textContent = scene.description;
    $('.example-badge').hidden = !scene.illustrative;
    viewer.title = `${scene.title}: ${variant.label} — interactive Viser scene`;
  }
  async function loadViewer() {
    const version = ++loadVersion;
    updateViewerInfo();
    $('#load-demo').disabled = true;
    $('#demo-status').textContent = 'Loading the 3D scene…';
    try {
      // Check local files first so missing recordings produce a usable fallback.
      if (!variant.embedUrl) {
        const responses = await Promise.all([
          fetch(new URL(variant.recording, document.baseURI), {method: 'HEAD'}),
          fetch(new URL(content.viewer.client, document.baseURI), {method: 'HEAD'})
        ]);
        if (responses.some(response => !response.ok)) throw new Error('The viewer or recording file is unavailable.');
      }
      if (version !== loadVersion) return;
      viewer.src = viewerURL();
      viewer.hidden = false;
      $('#demo-cover').hidden = true;
      loaded = true;
      $('#demo-status').textContent = `${scene.title} · ${variant.label}. Drag to orbit; use the viewer timeline to play or pause. If your browser cannot render 3D, try Open viewer.`;
    } catch (error) {
      if (version !== loadVersion) return;
      viewer.hidden = true;
      viewer.removeAttribute('src');
      $('#demo-cover').hidden = false;
      $('#demo-status').textContent = 'This scene could not be loaded. Check the recording path or try again.';
    } finally {
      if (version === loadVersion) $('#load-demo').disabled = false;
    }
  }
  function renderVariants() {
    const list = $('#demo-variants');
    list.replaceChildren();
    scene.variants.forEach(item => {
      const button = element('button', '', item.label);
      button.setAttribute('aria-label', item.label);
      button.setAttribute('aria-pressed', String(item.id === variant.id));
      button.addEventListener('click', () => {
        variant = item;
        list.querySelectorAll('button').forEach(el => el.setAttribute('aria-pressed', String(el === button)));
        updateViewerInfo();
        if (loaded) loadViewer();
      });
      list.append(button);
    });
    updateViewerInfo();
  }
  content.viewer.scenes.forEach(item => {
    const option = element('option', '', item.title);
    option.value = item.id;
    sceneSelect.append(option);
  });
  sceneSelect.addEventListener('change', () => {
    scene = content.viewer.scenes.find(item => item.id === sceneSelect.value);
    variant = scene.variants[0];
    renderVariants();
    if (loaded) loadViewer();
  });
  $('#load-demo').addEventListener('click', loadViewer);
  renderVariants();

  if (content.bibtex) {
    $('#citation').hidden = false;
    $('#bibtex').textContent = content.bibtex;
    $('#copy-citation').addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(content.bibtex); $('#copy-status').textContent = 'Citation copied.'; }
      catch { $('#copy-status').textContent = 'Select the citation text and copy it manually.'; }
    });
  }
})();
