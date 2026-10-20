'use strict';
(() => {
  const $ = id => document.getElementById(id);
  let token = null, catalog = {}, selected = new URLSearchParams(location.search).get('job');
  let submitting = false, polling = false, timer = null, pending = null;
  let selectionVersion = 0, lastList = '', lastDetail = '';
  function node(tag, text, cls) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = String(text ?? 'Unavailable');
    if (cls) element.className = cls;
    return element;
  }
  function error(message) {
    $('execution-error').textContent = message;
    $('execution-error').hidden = !message;
  }
  async function api(path, method = 'GET', body) {
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(path, {method, signal: controller.signal, cache: 'no-store',
        headers: {'X-Inquest-Token': token || '', ...(body ? {'Content-Type': 'application/json'} : {})},
        ...(body ? {body: JSON.stringify(body)} : {})});
      let data;
      try { data = await response.json(); } catch { throw new Error(`Local server returned HTTP ${response.status}`); }
      if (!response.ok) {
        if (response.status === 403) token = null;
        throw new Error(data.error || `Local request failed (${response.status})`);
      }
      return data;
    } catch (failure) {
      if (failure.name === 'AbortError') throw new Error('Local request timed out. Refresh jobs before retrying.');
      if (failure instanceof TypeError) throw new Error('Local server unavailable. Restart it, then refresh jobs.');
      throw failure;
    } finally { clearTimeout(timeout); }
  }
  function selectCases() {
    $('case').replaceChildren();
    for (const entry of catalog[$('suite').value] || []) {
      const option = node('option', `${entry.case_id} · ${entry.difficulty}`);
      option.value = entry.case_id; $('case').append(option);
    }
  }
  async function connect() {
    const data = await api('/api/local/config');
    token = data.token; catalog = data.suites;
    const previous = $('suite').value;
    $('suite').replaceChildren();
    for (const suite of Object.keys(catalog)) {
      const option = node('option', suite); option.value = suite; $('suite').append(option);
    }
    if (catalog[previous]) $('suite').value = previous;
    selectCases();
    ['suite', 'case', 'budget', 'start'].forEach(id => { $(id).disabled = false; });
  }
  function choose(id) {
    selectionVersion++;
    selected = id;
    history.replaceState(null, '', `/investigate?job=${encodeURIComponent(id)}`);
    refresh();
  }
  function renderJobs(jobs) {
    if (!jobs.some(job => job.id === selected)) selected = jobs[0]?.id || null;
    const signature = JSON.stringify([jobs, selected]);
    if (signature === lastList) return;
    lastList = signature;
    $('job-list').replaceChildren();
    for (const job of jobs) {
      const button = node('button', undefined, 'episode-button'); button.type = 'button';
      button.setAttribute('aria-pressed', String(job.id === selected));
      button.append(node('strong', job.case_id), node('small', `${job.suite} · budget ${job.budget}`),
        node('small', job.state), node('small', job.created_at));
      button.addEventListener('click', () => choose(job.id));
      $('job-list').append(button);
    }
    if (!jobs.length) $('job-list').append(node('p', 'No local investigations yet.', 'muted'));
  }
  function renderJob(job) {
    const signature = JSON.stringify(job);
    if (signature === lastDetail) return;
    lastDetail = signature;
    const detail = $('job-detail'); detail.replaceChildren();
    const heading = node('div', undefined, 'episode-heading');
    heading.append(node('h2', job.case_id), node('span', job.state, 'pill')); detail.append(heading);
    const steps = job.result?.score.steps ?? job.steps;
    detail.append(node('p', `${job.suite} · ${steps} of ${job.budget} tool calls used`, 'muted'));
    const progress = node('progress', undefined, 'job-progress'); progress.max = job.budget; progress.value = steps;
    progress.setAttribute('aria-label', 'Tool calls used'); detail.append(progress);
    const actions = node('div', undefined, 'job-actions');
    if (['queued', 'running', 'cancelling'].includes(job.state)) {
      const button = node('button', job.state === 'cancelling' ? 'Cancellation requested…' : 'Cancel investigation');
      button.type = 'button'; button.disabled = job.state === 'cancelling';
      button.addEventListener('click', () => action(job.id, 'cancel', button)); actions.append(button);
    }
    if (['interrupted', 'cancelled'].includes(job.state)) {
      const button = node('button', 'Resume investigation'); button.type = 'button';
      button.addEventListener('click', () => action(job.id, 'resume', button)); actions.append(button);
      detail.append(node('p', 'Resume keeps previous attempts. Changed runner configuration, source or data can make strict resume incompatible.', 'notice'));
    }
    if (job.can_open) {
      const link = node('a', 'Open saved result', 'button'); link.href = `/runs?job=${encodeURIComponent(job.id)}`;
      actions.append(link);
    }
    detail.append(actions);
    if (job.error) detail.append(node('p', job.error, 'notice error'));
    if (job.result) {
      detail.append(node('h3', 'Recorded outcome'));
      detail.append(node('p', `${job.result.status} · ${job.result.score.success ? 'Accepted' : 'Not accepted'}`, 'live-report'));
      if (job.result.report) detail.append(node('p', job.result.report.summary || 'Report saved.', 'live-report'));
      else detail.append(node('p', 'No final report saved.', 'muted'));
    }
    detail.append(node('h3', 'Investigation timeline'));
    const timeline = node('ol', undefined, 'timeline');
    for (const event of job.events) {
      const item = node('li');
      if (event.kind === 'observation') {
        item.append(node('strong', `${event.observation.id} / ${event.observation.tool}`),
          node('pre', event.observation.text));
      } else if (event.kind === 'report') item.append(node('strong', 'Final report recorded'));
      else item.append(node('strong', event.kind), node('pre', event.code || 'Execution event'));
      timeline.append(item);
    }
    detail.append(timeline);
    if (!job.events.length) detail.append(node('p', 'No tool observations in this attempt yet.', 'muted'));
  }
  async function action(id, name, button) {
    button.disabled = true; error('');
    try { await api(`/api/local/jobs/${id}/${name}`, 'POST'); }
    catch (failure) { error(failure.message); }
    finally { button.disabled = false; refresh(); }
  }
  async function refresh() {
    if (polling) return;
    polling = true; clearTimeout(timer);
    try {
      if (!token) await connect();
      const before = selectionVersion;
      const data = await api('/api/local/jobs');
      if (before !== selectionVersion) return;
      renderJobs(data.jobs);
      const wanted = selected;
      if (wanted) {
        const job = await api(`/api/local/jobs/${wanted}`);
        if (wanted === selected) renderJob(job);
      }
      $('connection-status').textContent = 'Connected · jobs and observations saved locally';
    } catch (failure) {
      $('connection-status').textContent = failure.message;
    } finally {
      polling = false;
      timer = setTimeout(refresh, token ? 700 : 3000);
    }
  }
  $('suite').addEventListener('change', selectCases);
  $('refresh-jobs').addEventListener('click', refresh);
  $('investigation-form').addEventListener('submit', async event => {
    event.preventDefault(); if (submitting) return;
    submitting = true; $('start').disabled = true; error('');
    const settings = {suite: $('suite').value, case_id: $('case').value, budget: Number($('budget').value)};
    if (!pending || JSON.stringify(pending.settings) !== JSON.stringify(settings)) {
      pending = {settings, key: crypto.randomUUID().replaceAll('-', '')};
    }
    try {
      const job = await api('/api/local/jobs', 'POST', {...settings, request_key: pending.key});
      pending = null; choose(job.id);
    } catch (failure) { error(failure.message); }
    finally { submitting = false; $('start').disabled = false; }
  });
  refresh();
})();
