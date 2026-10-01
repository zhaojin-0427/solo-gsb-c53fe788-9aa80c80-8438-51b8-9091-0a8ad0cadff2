const EXAMPLE_GROUPS = [
  { id: 'G1', voc: '40.00', isc: '10.00' },
  { id: 'G2', voc: '40.00', isc: '8.00' },
  { id: 'G3', voc: '38.00', isc: '10.00' },
  { id: 'G4', voc: '38.00', isc: '8.00' },
];

const EXAMPLE_BASELINE = ['G1 G2 G3 G4'];

const state = {
  groups: clone(EXAMPLE_GROUPS),
  result: null,
  lastInput: null,
};

const els = {};

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function formatNumber(value, digits = 2) {
  return Number(value).toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function setMessage(element, text, success = false) {
  element.textContent = text || '';
  element.classList.toggle('success', Boolean(success));
}

document.addEventListener('DOMContentLoaded', () => {
  for (const id of [
    'title', 'baseline', 'groupsBody', 'addGroup', 'removeGroup', 'calculate',
    'resetExample', 'formMessage', 'records', 'refreshRecords', 'emptyResult',
    'resultPanel', 'baselineWiring', 'optimalWiring', 'baselineVoltage',
    'baselineCurrent', 'baselinePower', 'optimalVoltage', 'optimalCurrent',
    'optimalPower', 'comparison', 'pvChart', 'saveRecord', 'resultMessage',
  ]) {
    els[id] = document.getElementById(id);
  }

  els.addGroup.addEventListener('click', addGroup);
  els.removeGroup.addEventListener('click', removeGroup);
  els.calculate.addEventListener('click', submitCalculation);
  els.resetExample.addEventListener('click', resetExample);
  els.refreshRecords.addEventListener('click', loadRecords);
  els.saveRecord.addEventListener('click', saveCurrentResult);

  resetExample(false);
  loadRecords();
});

function renderGroups() {
  els.groupsBody.innerHTML = state.groups.map((group, index) => `
    <tr>
      <td><input data-index="${index}" data-field="id" value="${escapeHtml(group.id)}" maxlength="32"></td>
      <td><input data-index="${index}" data-field="voc" value="${escapeHtml(group.voc)}" inputmode="decimal"></td>
      <td><input data-index="${index}" data-field="isc" value="${escapeHtml(group.isc)}" inputmode="decimal"></td>
    </tr>
  `).join('');

  els.groupsBody.querySelectorAll('input').forEach((input) => {
    input.addEventListener('input', () => {
      state.groups[Number(input.dataset.index)][input.dataset.field] = input.value;
    });
  });
}

function addGroup() {
  if (state.groups.length >= 9) {
    setMessage(els.formMessage, '最多只能录入 9 个旁路组。');
    return;
  }
  const nextIndex = state.groups.length + 1;
  state.groups.push({ id: `G${nextIndex}`, voc: '', isc: '' });
  renderGroups();
}

function removeGroup() {
  if (state.groups.length <= 3) {
    setMessage(els.formMessage, '至少需要保留 3 个旁路组。');
    return;
  }
  state.groups.pop();
  renderGroups();
}

function resetExample(showMessage = true) {
  state.groups = clone(EXAMPLE_GROUPS);
  els.title.value = '';
  els.baseline.value = EXAMPLE_BASELINE.join('\n');
  renderGroups();
  setMessage(els.formMessage, '');
  if (showMessage) setMessage(els.resultMessage, '已恢复示例参数。', true);
}

function parseBaseline(text, knownIds) {
  const lines = text.split(/\n+/).map((line) => line.trim()).filter(Boolean);
  if (lines.length < 1 || lines.length > 3) {
    throw new Error('基线接线必须由 1～3 行非空串组成。');
  }

  const seen = new Set();
  const strings = lines.map((line, lineIndex) => {
    const ids = line.split(/[\s,，、;；]+/).map((id) => id.trim()).filter(Boolean);
    if (ids.length === 0) {
      throw new Error(`基线第 ${lineIndex + 1} 串不能为空。`);
    }
    for (const id of ids) {
      if (!knownIds.has(id)) throw new Error(`基线包含不存在的组编号：${id}`);
      if (seen.has(id)) throw new Error(`组 ${id} 在基线中必须恰好出现一次。`);
      seen.add(id);
    }
    return ids;
  });

  if (seen.size !== knownIds.size) {
    const missing = [...knownIds].filter((id) => !seen.has(id));
    throw new Error(`每组必须恰好出现一次，缺少：${missing.join('、')}`);
  }
  return strings;
}

function collectInput() {
  const groups = state.groups.map((group) => ({
    id: String(group.id ?? '').trim(),
    voc: String(group.voc ?? '').trim(),
    isc: String(group.isc ?? '').trim(),
  }));

  if (groups.length < 3 || groups.length > 9) {
    throw new Error('旁路组数量必须为 3～9 个。');
  }
  const ids = new Set(groups.map((group) => group.id));
  if (ids.size !== groups.length) throw new Error('旁路组编号必须唯一。');
  const idPattern = /^[\w一-鿿][\w一-鿿.-]{0,31}$/u;
  if ([...ids].some((id) => !idPattern.test(id))) {
    throw new Error('编号需为 1～32 个字符，可含中英文、数字、下划线、点或连字符。');
  }

  for (const group of groups) {
    const voc = Number(group.voc);
    const isc = Number(group.isc);
    if (!/^\d+(\.\d{1,2})?$/.test(group.voc) || !(voc > 0 && voc <= 100)) {
      throw new Error(`组 ${group.id} 的 Voc 必须是 0～100 V（不含 0）且至多两位小数。`);
    }
    if (!/^\d+(\.\d{1,2})?$/.test(group.isc) || !(isc > 0 && isc <= 30)) {
      throw new Error(`组 ${group.id} 的 Isc 必须是 0～30 A（不含 0）且至多两位小数。`);
    }
  }

  return {
    title: els.title.value.trim() || null,
    groups,
    baseline: parseBaseline(els.baseline.value, ids),
  };
}

async function submitCalculation() {
  setMessage(els.formMessage, '');
  setMessage(els.resultMessage, '');
  let payload;
  try {
    payload = collectInput();
  } catch (error) {
    setMessage(els.formMessage, error.message);
    return;
  }

  els.calculate.disabled = true;
  els.calculate.textContent = '计算中...';
  try {
    const response = await fetch('/api/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '试算失败');
    state.lastInput = payload;
    state.result = data;
    renderResult(data);
  } catch (error) {
    setMessage(els.formMessage, error.message);
  } finally {
    els.calculate.disabled = false;
    els.calculate.textContent = '开始试算';
  }
}

function renderWiring(element, strings) {
  element.innerHTML = strings.map((string, index) => `
    <div class="string-line">串 ${index + 1}：${string.map(escapeHtml).join(' — ')}</div>
  `).join('');
}

function renderResult(data) {
  els.emptyResult.hidden = true;
  els.resultPanel.hidden = false;

  renderWiring(els.baselineWiring, data.baseline.strings);
  renderWiring(els.optimalWiring, data.optimal.strings);

  els.baselineVoltage.textContent = formatNumber(data.baseline.peak.voltage);
  els.baselineCurrent.textContent = formatNumber(data.baseline.peak.current);
  els.baselinePower.textContent = formatNumber(data.baseline.peak.power);
  els.optimalVoltage.textContent = formatNumber(data.optimal.peak.voltage);
  els.optimalCurrent.textContent = formatNumber(data.optimal.peak.current);
  els.optimalPower.textContent = formatNumber(data.optimal.peak.power);

  const gain = data.comparison.powerGain;
  const ratio = data.comparison.powerGainRatio * 100;
  els.comparison.textContent = data.comparison.sameWiring
    ? `共枚举 ${data.candidateCount} 种 1～3 串分组：基线已是全局最大功率接线，峰值 ${formatNumber(data.optimal.peak.power)} W。`
    : `共枚举 ${data.candidateCount} 种 1～3 串分组：最优方案功率提升 ${formatNumber(gain)} W（${formatNumber(ratio, 2)}%）。`;

  drawChart(data);
}

function curvePoints(curve, maxVoltage) {
  const points = [];
  for (const segment of curve.segments) {
    const samples = Math.max(8, Math.round(48 / curve.segments.length));
    for (let i = 0; i <= samples; i += 1) {
      const t = i / samples;
      const voltage = segment.v0 + (segment.v1 - segment.v0) * t;
      const current = segment.a * voltage + segment.b;
      points.push({ x: voltage, y: voltage * Math.max(current, 0) });
    }
  }
  if (curve.voc < maxVoltage) {
    points.push({ x: curve.voc, y: 0 }, { x: maxVoltage, y: 0 });
  }
  return dedupePoints(points);
}

function dedupePoints(points) {
  return points.filter((point, index) => {
    if (index === 0) return true;
    const previous = points[index - 1];
    return Math.abs(previous.x - point.x) > 1e-12 || Math.abs(previous.y - point.y) > 1e-12;
  });
}

function drawChart(data) {
  const canvas = els.pvChart;
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);

  const margin = { left: 78, right: 34, top: 48, bottom: 64 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const maxVoltage = Math.max(data.baseline.curve.voc, data.optimal.curve.voc) * 1.05;
  const maxPower = Math.max(data.baseline.peak.power, data.optimal.peak.power) * 1.12 || 1;

  const xScale = (x) => margin.left + (x / maxVoltage) * plotWidth;
  const yScale = (y) => margin.top + plotHeight - (y / maxPower) * plotHeight;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = '#e4eaf0';
  ctx.lineWidth = 1;
  ctx.fillStyle = '#5f6b7a';
  ctx.font = '13px sans-serif';
  ctx.textAlign = 'center';
  for (let i = 0; i <= 6; i += 1) {
    const x = margin.left + (i / 6) * plotWidth;
    const value = maxVoltage * i / 6;
    ctx.beginPath();
    ctx.moveTo(x, margin.top);
    ctx.lineTo(x, margin.top + plotHeight);
    ctx.stroke();
    ctx.fillText(formatNumber(value, 1), x, margin.top + plotHeight + 22);
  }

  ctx.textAlign = 'right';
  for (let i = 0; i <= 5; i += 1) {
    const y = margin.top + plotHeight - (i / 5) * plotHeight;
    const value = maxPower * i / 5;
    ctx.beginPath();
    ctx.moveTo(margin.left, y);
    ctx.lineTo(margin.left + plotWidth, y);
    ctx.stroke();
    ctx.fillText(formatNumber(value, 1), margin.left - 10, y + 4);
  }

  ctx.strokeStyle = '#172033';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(margin.left, margin.top);
  ctx.lineTo(margin.left, margin.top + plotHeight);
  ctx.lineTo(margin.left + plotWidth, margin.top + plotHeight);
  ctx.stroke();

  drawCurve(ctx, curvePoints(data.baseline.curve, maxVoltage), xScale, yScale, '#5b6572', 3);
  drawCurve(ctx, curvePoints(data.optimal.curve, maxVoltage), xScale, yScale, '#d1492f', 3);
  drawPeak(ctx, data.baseline.peak, xScale, yScale, '#5b6572', '基线峰值');
  drawPeak(ctx, data.optimal.peak, xScale, yScale, '#d1492f', '最优峰值');

  drawLegend(ctx, width, margin);

  ctx.fillStyle = '#172033';
  ctx.font = '15px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('端电压 V (V)', margin.left + plotWidth / 2, height - 18);

  ctx.save();
  ctx.translate(22, margin.top + plotHeight / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText('功率 P (W)', 0, 0);
  ctx.restore();
}

function drawCurve(ctx, points, xScale, yScale, color, lineWidth) {
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.lineJoin = 'round';
  ctx.beginPath();
  points.forEach((point, index) => {
    const x = xScale(point.x);
    const y = yScale(point.y);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function drawPeak(ctx, peak, xScale, yScale, color, label) {
  const x = xScale(peak.voltage);
  const y = yScale(peak.power);
  ctx.fillStyle = color;
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(x, y, 6, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = color;
  ctx.font = 'bold 13px sans-serif';
  ctx.textAlign = x > 720 ? 'right' : 'left';
  const textX = x > 720 ? x - 10 : x + 10;
  ctx.fillText(`${label} ${formatNumber(peak.voltage, 2)} V / ${formatNumber(peak.power, 2)} W`, textX, y - 10);
}

function drawLegend(ctx, width, margin) {
  const items = [
    { color: '#5b6572', label: '基线接线' },
    { color: '#d1492f', label: '最优接线' },
  ];
  let x = width - margin.right - 210;
  ctx.font = '14px sans-serif';
  ctx.textAlign = 'left';
  for (const item of items) {
    ctx.strokeStyle = item.color;
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(x, margin.top - 18);
    ctx.lineTo(x + 32, margin.top - 18);
    ctx.stroke();
    ctx.fillStyle = '#172033';
    ctx.fillText(item.label, x + 40, margin.top - 13);
    x += 112;
  }
}

async function saveCurrentResult() {
  setMessage(els.resultMessage, '');
  if (!state.lastInput || !state.result) {
    setMessage(els.resultMessage, '请先完成一次试算。');
    return;
  }

  try {
    const response = await fetch('/api/records', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: els.title.value.trim() || state.lastInput.title || null,
        input: state.lastInput,
        result: state.result,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '保存失败');
    setMessage(els.resultMessage, `已保存：${data.title}`, true);
    await loadRecords();
  } catch (error) {
    setMessage(els.resultMessage, error.message);
  }
}

async function loadRecords() {
  try {
    const response = await fetch('/api/records');
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '记录加载失败');
    renderRecords(data);
  } catch (error) {
    els.records.className = 'records-list empty';
    els.records.textContent = error.message;
  }
}

function renderRecords(records) {
  if (!records.length) {
    els.records.className = 'records-list empty';
    els.records.textContent = '暂无保存记录';
    return;
  }

  els.records.className = 'records-list';
  els.records.innerHTML = records.map((record) => `
    <div class="record-item">
      <div>
        <div class="record-title">${escapeHtml(record.title)}</div>
        <div class="record-time">#${record.id} · ${formatTime(record.createdAt)}</div>
      </div>
      <div class="record-actions">
        <button type="button" class="secondary" data-action="open" data-id="${record.id}">打开</button>
        <button type="button" class="danger" data-action="delete" data-id="${record.id}">删除</button>
      </div>
    </div>
  `).join('');

  els.records.querySelectorAll('button').forEach((button) => {
    button.addEventListener('click', () => {
      const id = Number(button.dataset.id);
      if (button.dataset.action === 'open') openRecord(id);
      else deleteRecord(id);
    });
  });
}

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}

async function openRecord(id) {
  try {
    const response = await fetch(`/api/records/${id}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '记录打开失败');

    const input = data.payload.input;
    state.groups = clone(input.groups);
    state.lastInput = input;
    state.result = data.payload.result;
    els.title.value = data.title || input.title || '';
    els.baseline.value = input.baseline.map((string) => string.join(' ')).join('\n');
    renderGroups();
    renderResult(state.result);
    setMessage(els.resultMessage, `已打开记录 #${id}：${data.title}`, true);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } catch (error) {
    setMessage(els.resultMessage, error.message);
  }
}

async function deleteRecord(id) {
  if (!window.confirm(`确定删除记录 #${id} 吗？`)) return;
  try {
    const response = await fetch(`/api/records/${id}`, { method: 'DELETE' });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || '删除失败');
    }
    await loadRecords();
    setMessage(els.resultMessage, `记录 #${id} 已删除。`, true);
  } catch (error) {
    setMessage(els.resultMessage, error.message);
  }
}
