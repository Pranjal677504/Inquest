'use strict';

// This page has no network or storage API. Imported text is always rendered as text.
(() => {
  const $ = id => document.getElementById(id);
  const MAX_FILE = 20 * 1024 * 1024, MAX_TOTAL = 128 * 1024 * 1024;
  const statuses = new Set(['reported', 'backend_error', 'protocol_error',
    'tool_budget_exhausted', 'context_limit', 'model_turn_limit']);
  let current = null, sourceFiles = [], selected = null, generation = 0, comparisonGeneration = 0;
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const integer = value => Number.isSafeInteger(value) && value >= 0;
  const safeId = value => typeof value === 'string' && /^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}$/.test(value);
  const display = value => value === null || value === undefined ? 'Unavailable' : String(value);
  const yes = value => value === true ? 'Yes' : value === false ? 'No' : 'Unavailable';
  const json = value => JSON.stringify(value, null, 2);
  function node(tag, text, cls) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = display(text);
    if (cls) element.className = cls;
    return element;
  }
  function require(condition, message) { if (!condition) throw new Error(message); }
  function parse(text, label) {
    try { return JSON.parse(text); }
    catch { throw new Error(`${label}: invalid JSON. Select the original saved file.`); }
  }
  function facts(parent, entries) {
    const list = node('dl', undefined, 'facts');
    entries.forEach(([key, value]) => list.append(node('dt', key), node('dd', value)));
    parent.append(list);
  }
  function raw(parent, label, value) {
    const details = node('details');
    details.append(node('summary', label), node('pre', typeof value === 'string' ? value : json(value)));
    parent.append(details);
  }
  function notice(parent, text) { parent.append(node('p', text, 'notice')); }
  function outcome(result) {
    if (!result) return 'Unfinished';
    if (result.status !== 'reported') return `Execution error · ${result.status}`;
    return result.score.success ? 'Accepted' : 'Reported, not accepted';
  }
  function validateManifest(manifest) {
    require(object(manifest) && manifest.format_version === 1 && object(manifest.config) &&
      typeof manifest.fingerprint === 'string' && /^[a-f0-9]{64}$/.test(manifest.fingerprint) &&
      Array.isArray(manifest.jobs) && manifest.jobs.length > 0 && manifest.jobs.length <= 1000,
    'Unsupported run.json. Expected a version 1 Inquest run with 1–1000 planned episodes.');
    const ids = new Set(), pairs = new Set();
    for (const job of manifest.jobs) {
      require(object(job) && safeId(job.job_id) && safeId(job.case_id) &&
        integer(job.max_steps) && job.max_steps <= 10000 && typeof job.difficulty === 'string' &&
        !ids.has(job.job_id) && !pairs.has(`${job.case_id}/${job.max_steps}`),
      'Invalid or duplicate episode in run.json.');
      ids.add(job.job_id); pairs.add(`${job.case_id}/${job.max_steps}`);
    }
    return manifest;
  }
  function validateResult(result, job, manifest) {
    require(object(result) && result.fingerprint === manifest.fingerprint &&
      ['job_id', 'case_id', 'max_steps', 'difficulty'].every(k => result[k] === job[k]) &&
      integer(result.attempt) && result.attempt >= 1 && result.attempt <= 999999 &&
      statuses.has(result.status) && object(result.score) &&
      typeof result.latency_seconds === 'number' && Number.isFinite(result.latency_seconds) && result.latency_seconds >= 0 &&
      ['success', 'evidence_relevant_success', 'report_valid', 'submitted'].every(k => typeof result.score[k] === 'boolean') &&
      result.score.scenario === job.case_id && integer(result.score.steps) && result.score.steps <= job.max_steps &&
      (result.report === null || object(result.report)),
    `Result does not match the run manifest: ${job.job_id}.`);
  }
  async function readRun(files) {
    require(files.length <= 5000, 'Select one run folder (at most 5000 files).');
    const usable = files.filter(f => /^(run|result)\.json$|^attempt-\d{3,6}\.jsonl$/.test(f.name));
    require(usable.reduce((n, f) => n + f.size, 0) <= MAX_TOTAL,
      'Run files exceed the 128 MiB import limit. Select a smaller run.');
    require(usable.every(f => f.size <= MAX_FILE), 'A run file exceeds the 20 MiB limit.');
    const manifests = usable.filter(f => f.name === 'run.json');
    require(manifests.length > 0, 'Select run.json with your episode files, or choose the complete run folder.');
    // Flat-file additions can contain the same manifest twice; folder import must be one run.
    const manifestFile = manifests[manifests.length - 1];
    const manifest = validateManifest(parse(await manifestFile.text(), 'run.json'));
    for (const other of manifests.slice(0, -1)) {
      require(validateManifest(parse(await other.text(), 'run.json')).fingerprint === manifest.fingerprint,
        'Multiple runs selected. Choose one run folder at a time; clear the review before opening a different run.');
    }
    const relativeRoot = manifestFile.webkitRelativePath ?
      manifestFile.webkitRelativePath.slice(0, -'run.json'.length) : null;
    const jobs = new Map(manifest.jobs.map(job => [job.job_id, {job, result: null, journals: new Map(), warnings: []}]));
    // Sequential reads bound peak parsing memory. Request histories are not needed by this viewer.
    for (const file of usable) {
      if (file.name === 'run.json') continue;
      let pathJob = null;
      if (relativeRoot !== null) {
        const path = file.webkitRelativePath;
        if (!path.startsWith(relativeRoot)) continue;
        const match = /^episodes\/([^/]+)\/(result\.json|attempt-\d{3,6}\.jsonl)$/.exec(path.slice(relativeRoot.length));
        if (!match) continue;
        pathJob = match[1];
        require(jobs.has(pathJob), `Unknown episode folder: ${pathJob}.`);
      }
      const contents = await file.text();
      if (file.name === 'result.json') {
        const result = parse(contents, 'result.json');
        require(object(result) && jobs.has(result.job_id), 'Result belongs to an unknown episode.');
        require(pathJob === null || result.job_id === pathJob, 'Result is in the wrong episode folder.');
        const entry = jobs.get(result.job_id);
        validateResult(result, entry.job, manifest);
        entry.result = result;
      } else {
        const lines = contents.split(/\r?\n/).filter(line => line.trim());
        require(lines.length <= 10000, 'Journal exceeds the 10000-event import limit.');
        require(lines.length > 0, `Empty journal: ${file.name}.`);
        const start = parse(lines[0], file.name);
        require(object(start) && start.kind === 'episode_started' && start.fingerprint === manifest.fingerprint &&
          jobs.has(start.job_id) && integer(start.attempt) && start.attempt > 0 &&
          file.name === `attempt-${String(start.attempt).padStart(3, '0')}.jsonl` &&
          (pathJob === null || pathJob === start.job_id), 'Journal identity does not match this run.');
        const entry = jobs.get(start.job_id);
        require(['case_id', 'difficulty', 'max_steps'].every(k => start[k] === entry.job[k]),
          'Journal episode metadata does not match run.json.');
        const events = [], warnings = [];
        let previous = 0;
        for (let i = 0; i < lines.length; i++) {
          let event;
          try { event = JSON.parse(lines[i]); }
          catch { warnings.push(`Unreadable journal line ${i + 1}; timeline is incomplete.`); continue; }
          if (!object(event) || !integer(event.seq) || event.seq !== previous + 1) {
            warnings.push(`Journal sequence gap or invalid event at line ${i + 1}; timeline is incomplete.`);
          }
          if (!object(event)) continue;
          if (integer(event.seq)) previous = event.seq;
          // Drop repeated request histories and provider metadata from the review model.
          if (['observation', 'protocol_error', 'backend_error', 'report', 'episode_finished'].includes(event.kind) ||
              (event.kind === 'transport_result' && event.outcome !== 'received')) events.push(event);
        }
        entry.journals.set(start.attempt, {events, warnings});
      }
    }
    return {manifest, entries: [...jobs.values()], name: relativeRoot ? relativeRoot.split('/').filter(Boolean).pop() : 'Imported investigation'};
  }
  function renderRun() {
    const {manifest, entries, name} = current;
    $('run-review').hidden = false;
    $('run-title').textContent = name;
    $('run-policy').textContent = `Policy ${display(manifest.config.episode_options?.policy)}`;
    $('run-meta').replaceChildren();
    const backend = manifest.config.backend || {}, suite = manifest.config.suite || {};
    $('run-meta').append(node('div', `${display(suite.suite_id)} / ${display(suite.set_name)} · ${display(backend.requested_model || backend.kind)}`),
      node('div', `Fingerprint ${manifest.fingerprint}`));
    const completed = entries.filter(e => e.result);
    const stats = [
      ['Completed / planned', `${completed.length} / ${entries.length}`],
      ['Accepted', completed.filter(e => e.result.score.success).length],
      ['Evidence-relevant successes', completed.filter(e => e.result.score.evidence_relevant_success).length],
      ['Execution errors', completed.filter(e => e.result.status !== 'reported').length],
      ['Unfinished', entries.length - completed.length],
    ];
    $('run-stats').replaceChildren();
    for (const [label, value] of stats) {
      const stat = node('div', undefined, 'stat'); stat.append(node('strong', value), node('span', label));
      $('run-stats').append(stat);
    }
    renderEpisodes();
  }
  function renderEpisodes() {
    const filter = $('episode-filter').value;
    const matches = current.entries.filter(({result}) => filter === 'all' ||
      (filter === 'unfinished' && !result) || (filter === 'accepted' && result?.score.success) ||
      (filter === 'failed' && result?.status === 'reported' && !result.score.success) ||
      (filter === 'errors' && result && result.status !== 'reported'));
    if (!matches.some(e => e.job.job_id === selected)) selected = matches[0]?.job.job_id || null;
    $('episode-list').replaceChildren();
    for (const entry of matches) {
      const button = node('button', undefined, 'episode-button');
      button.type = 'button'; button.setAttribute('aria-pressed', String(entry.job.job_id === selected));
      button.append(node('strong', entry.job.case_id), node('small', `Budget ${entry.job.max_steps} · ${entry.job.difficulty}`), node('small', outcome(entry.result)));
      button.addEventListener('click', () => { selected = entry.job.job_id; renderEpisodes(); });
      $('episode-list').append(button);
    }
    if (!matches.length) $('episode-list').append(node('p', 'No episodes match this filter.', 'muted'));
    renderEpisode(current.entries.find(e => e.job.job_id === selected));
  }
  function renderEpisode(entry) {
    const target = $('episode-detail'); target.replaceChildren();
    if (!entry) { target.append(node('p', 'Choose an episode to inspect.')); return; }
    const {job, result, journals} = entry;
    const attempt = result?.attempt || Math.max(0, ...journals.keys());
    const journal = journals.get(attempt);
    const events = journal?.events || [];
    const heading = node('div', undefined, 'episode-heading');
    heading.append(node('h2', job.case_id), node('span', outcome(result), `outcome${result?.score.success ? ' accepted' : ''}`));
    target.append(heading);
    facts(target, [['Tool budget', job.max_steps], ['Recorded attempt', attempt || 'No journal'],
      ['Steps used', result?.score.steps], ['Elapsed seconds', result ? result.latency_seconds?.toFixed(2) : undefined]]);
    if (!result) notice(target, 'No saved result. This episode remains unfinished, even if a journal contains an earlier report.');
    if (!journal) notice(target, 'Matching attempt journal not imported. Citations and timeline cannot be verified against observations.');
    for (const warning of [...new Set(journal?.warnings || [])]) notice(target, warning);
    if (journals.size > 1) notice(target, `Showing attempt ${attempt}. ${journals.size - 1} other imported attempt(s) are excluded from this timeline.`);
    if (result?.error_code) notice(target, `Execution error: ${result.error_code}. ${result.report === null ? 'No final report was saved.' : ''}`);
    const report = result?.report;
    target.append(node('h3', 'Final diagnosis'));
    if (report) {
      facts(target, [['Root service', report.service], ['Fault type', report.fault_type],
        ['Proposed action', report.fix?.action], ['Action target', report.fix?.target],
        ['Confidence', report.confidence]]);
      if (report.summary) target.append(node('p', report.summary));
    } else target.append(node('p', 'No saved final report.', 'muted'));
    const observations = events.filter(e => e.kind === 'observation' && object(e.observation));
    const counts = new Map();
    observations.forEach(e => counts.set(e.observation.id, (counts.get(e.observation.id) || 0) + 1));
    const anchors = new Map();
    observations.forEach((e, i) => { if (counts.get(e.observation.id) === 1) anchors.set(e.observation.id, `observation-${i}`); });
    if (report) {
      target.append(node('h3', 'Cited observations'));
      const citations = node('div', undefined, 'citations');
      if (Array.isArray(report.evidence)) for (const id of report.evidence) {
        if (anchors.has(id)) {
          const button = node('button', id, 'citation'); button.type = 'button';
          button.addEventListener('click', () => {
            const evidence = $(anchors.get(id)); evidence.scrollIntoView({block: 'center'}); evidence.focus({preventScroll: true});
          });
          citations.append(button);
        } else citations.append(node('span', `${display(id)} · unavailable or ambiguous`, 'pill'));
      }
      if (!citations.children.length) citations.append(node('p', 'No citations recorded.', 'muted'));
      target.append(citations);
    }
    if (result) {
      target.append(node('h3', 'Recorded evaluation'));
      const score = result.score;
      facts(target, [['Report submitted', yes(score.submitted)], ['Report valid', yes(score.report_valid)],
        ['Accepted', yes(score.success)], ['Evidence-relevant success', yes(score.evidence_relevant_success)],
        ['Service correct', yes(score.service_ok)], ['Fault correct', yes(score.type_ok)],
        ['Repair correct', yes(score.fix_ok)], ['Brier loss', score.brier],
        ['Protocol errors', result.protocol_errors]]);
      if (!score.submitted) notice(target, 'The absent report counts as report_valid=false; this does not mean a malformed report was submitted.');
      if (Array.isArray(score.validation_errors) && score.validation_errors.length) raw(target, 'Recorded validation errors', score.validation_errors);
      raw(target, 'Recorded usage (known totals and missing calls)', result.usage || {});
      raw(target, 'Full saved result', result);
    }
    target.append(node('h3', 'Tool timeline'));
    const timeline = node('ol', undefined, 'timeline');
    observations.forEach((event, i) => {
      const o = event.observation, item = node('li');
      item.id = `observation-${i}`; item.tabIndex = -1;
      const title = node('div', undefined, 'timeline-heading');
      title.append(node('strong', `${display(o.id)} / ${display(o.tool)}`), node('small', `${display(event.steps_left)} steps left`));
      item.append(title);
      if (counts.get(o.id) > 1) notice(item, 'Duplicate observation ID; citation links are disabled for this ID.');
      raw(item, 'Tool arguments', o.args);
      item.append(node('pre', o.text || '(No observation text)'));
      if (o.error) notice(item, `Tool error: ${display(o.error)}`);
      raw(item, 'Structured observation', o.data);
      timeline.append(item);
    });
    target.append(timeline);
    if (!observations.length) target.append(node('p', 'No observations available for this attempt.', 'muted'));
    const errors = events.filter(e => ['protocol_error', 'backend_error', 'transport_result'].includes(e.kind));
    target.append(node('h3', 'Recorded execution events'));
    if (!errors.length) target.append(node('p', 'No execution errors in the imported journal.', 'muted'));
    for (const event of errors) raw(target, `${event.kind} · event ${display(event.seq)}`, event);
  }
  async function importFiles(files, append) {
    const version = ++generation;
    $('import-error').hidden = true;
    $('import-status').textContent = 'Reading local files…';
    try {
      const sources = append ? [...sourceFiles, ...files] : [...files];
      const run = await readRun(sources);
      if (version !== generation) return;
      current = run; sourceFiles = sources; selected = null; $('episode-filter').value = 'all';
      renderRun();
      $('import-status').textContent = `Opened ${run.entries.length} planned episodes. No files uploaded.`;
    } catch (error) {
      if (version !== generation) return;
      $('import-error').textContent = error.message; $('import-error').hidden = false;
      $('import-status').textContent = current ? 'Previous review retained.' : 'No run open.';
    }
  }
  function renderComparison(comparison) {
    require(object(comparison) && comparison.kind === 'paired_policy_comparison' &&
      object(comparison.baseline) && object(comparison.candidate) && object(comparison.groups) &&
      Object.keys(comparison.groups).length <= 1000 &&
      Array.isArray(comparison.cases) && comparison.cases.length <= 1000 &&
      Array.isArray(comparison.limitations) && comparison.limitations.length <= 100,
    'Expected JSON from python -m inquest compare, not a summary or run manifest.');
    const view = document.createDocumentFragment();
    notice(view, 'Imported comparison artifact. This browser has not rerun the CLI compatibility checks or authenticated these files.');
    facts(view, [['Baseline policy', comparison.baseline.policy], ['Candidate policy', comparison.candidate.policy],
      ['Baseline fingerprint', comparison.baseline.fingerprint], ['Candidate fingerprint', comparison.candidate.fingerprint]]);
    const table = node('table'), head = node('tr');
    ['Group', 'Cases', 'Baseline accepted', 'Candidate accepted', 'Evidence successes (base / candidate)', 'Change (points)'].forEach(t => head.append(node('th', t)));
    const thead = node('thead'); thead.append(head); table.append(thead);
    const body = node('tbody');
    for (const [name, group] of Object.entries(comparison.groups)) {
      require(object(group), 'Invalid comparison group.');
      const row = node('tr');
      [name, group.cases, group.baseline_successes, group.candidate_successes,
        `${display(group.baseline_evidence_successes)} / ${display(group.candidate_evidence_successes)}`,
        group.success_delta_percentage_points].forEach(value => row.append(node('td', value)));
      body.append(row);
    }
    table.append(body); const wrap = node('div', undefined, 'table-wrap'); wrap.append(table); view.append(wrap);
    for (const limit of comparison.limitations) notice(view, display(limit));
    raw(view, 'Per-case outcomes, gains and regressions', comparison.cases);
    raw(view, 'Usage and operational differences', {baseline: comparison.baseline.usage, candidate: comparison.candidate.usage,
      operational_differences: comparison.operational_differences});
    $('comparison-view').replaceChildren(view);
  }
  $('run-folder').addEventListener('change', event => {
    if (event.target.files.length) importFiles(event.target.files, false);
    event.target.value = '';
  });
  $('run-files').addEventListener('change', event => {
    if (event.target.files.length) importFiles(event.target.files, true);
    event.target.value = '';
  });
  $('episode-filter').addEventListener('change', () => { if (current) renderEpisodes(); });
  $('clear').addEventListener('click', () => {
    generation++; comparisonGeneration++; current = null; sourceFiles = []; selected = null;
    $('run-review').hidden = true;
    ['episode-detail', 'episode-list', 'run-meta', 'run-stats', 'comparison-view'].forEach(id => $(id).replaceChildren());
    ['run-title', 'run-policy', 'comparison-status', 'comparison-error', 'import-error'].forEach(id => { $(id).textContent = ''; });
    $('import-status').textContent = 'No run open.'; $('import-error').hidden = true; $('comparison-error').hidden = true;
  });
  $('comparison-file').addEventListener('change', async event => {
    const file = event.target.files[0]; event.target.value = '';
    if (!file) return;
    const version = ++comparisonGeneration;
    $('comparison-error').hidden = true;
    try {
      require(file.size <= MAX_FILE, 'Comparison exceeds the 20 MiB import limit.');
      const comparison = parse(await file.text(), 'Comparison');
      if (version !== comparisonGeneration) return;
      renderComparison(comparison); $('comparison-status').textContent = 'Saved comparison opened locally.';
    } catch (error) {
      if (version !== comparisonGeneration) return;
      $('comparison-error').textContent = error.message; $('comparison-error').hidden = false;
    }
  });
  const embedded = $('local-run-files');
  if (embedded) {
    try {
      const files = parse(embedded.textContent, 'Local run');
      require(Array.isArray(files) && files.length <= 5000, 'Invalid local run file list.');
      importFiles(files.map(file => {
        require(object(file) && typeof file.path === 'string' && typeof file.content === 'string', 'Invalid local run file.');
        return {name: file.path.split('/').pop(), webkitRelativePath: file.path,
          size: new Blob([file.content]).size, text: async () => file.content};
      }), false);
    } catch (error) {
      $('import-error').textContent = error.message; $('import-error').hidden = false;
    }
    embedded.remove();
  }
})();
