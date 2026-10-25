(() => {
  "use strict";

  const colors = {
    ogr: "#0969da",
    ogrng: "#8250df",
    ogrp2: "#1a7f37",
    rc564: "#bf8700",
    rc572: "#cf222e",
  };
  const projectGroups = {
    keys: new Set(["rc564", "rc572"]),
    nodes: new Set(["ogr", "ogrng", "ogrp2"]),
  };
  const loadedFiles = new Map();
  const chartInstances = {};
  let manifest;
  let currentRange;
  let refreshId = 0;

  const status = document.querySelector("#status");
  const error = document.querySelector("#error");
  const fromInput = document.querySelector("#from-date");
  const toInput = document.querySelector("#to-date");
  const projectToggles = document.querySelector("#project-toggles");

  function dateInputValue(timestamp) {
    return new Date(timestamp * 1000).toISOString().slice(0, 10);
  }

  function projectIsEnabled(id) {
    return projectToggles.querySelector(`input[value="${id}"]`)?.checked ?? false;
  }

  function selectedProjects(group) {
    return manifest.projects.filter(
      (project) => projectGroups[group].has(project.id) && projectIsEnabled(project.id),
    );
  }

  function makeChart(canvasId, unit) {
    return new Chart(document.querySelector(`#${canvasId}`), {
      type: "line",
      data: { datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        parsing: false,
        interaction: { mode: "nearest", intersect: false },
        plugins: {
          legend: { display: false },
          decimation: { enabled: true, algorithm: "lttb", samples: 1200 },
          tooltip: {
            callbacks: {
              title(items) {
                return items.length
                  ? new Date(items[0].parsed.x).toLocaleString(undefined, { timeZone: "UTC" }) + " UTC"
                  : "";
              },
              label(item) {
                if (item.parsed.y == null) {
                  return `${item.dataset.label}: no rate recorded`;
                }
                return `${item.dataset.label}: ${item.parsed.y.toLocaleString(undefined, {
                  maximumFractionDigits: 3,
                })} ${unit}`;
              },
            },
          },
          zoom: {
            limits: { x: { min: "original", max: "original" } },
            pan: { enabled: true, mode: "x", modifierKey: "shift" },
            zoom: {
              mode: "x",
              drag: { enabled: true },
              wheel: { enabled: true },
              pinch: { enabled: true },
            },
          },
        },
        scales: {
          x: {
            type: "linear",
            min: currentRange.start * 1000,
            max: currentRange.end * 1000,
            ticks: {
              maxTicksLimit: 8,
              callback(value) {
                return new Date(Number(value)).toLocaleDateString(undefined, {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                  timeZone: "UTC",
                });
              },
            },
            title: { display: true, text: "Date (UTC)" },
          },
          y: {
            title: { display: true, text: unit },
            beginAtZero: true,
          },
        },
      },
    });
  }

  async function loadFile(file) {
    if (!loadedFiles.has(file)) {
      loadedFiles.set(
        file,
        fetch(new URL(file, document.baseURI)).then((response) => {
          if (!response.ok) {
            throw new Error(`Could not load ${file} (HTTP ${response.status}).`);
          }
          return response.json();
        }).catch((loadError) => {
          loadedFiles.delete(file);
          throw loadError;
        }),
      );
    }
    return loadedFiles.get(file);
  }

  async function pointsFor(project) {
    const years = project.years.filter(
      (entry) => entry.last >= currentRange.start && entry.first <= currentRange.end,
    );
    const shards = await Promise.all(years.map((entry) => loadFile(entry.file)));
    return shards
      .flat()
      .filter(([timestamp]) => timestamp >= currentRange.start && timestamp <= currentRange.end)
      .map(([timestamp, rate]) => ({ x: timestamp * 1000, y: rate }));
  }

  async function refreshCharts() {
    const thisRefresh = ++refreshId;
    error.hidden = true;
    status.textContent = "Loading selected projects…";
    try {
      const [keyProjects, nodeProjects] = [
        selectedProjects("keys"),
        selectedProjects("nodes"),
      ];
      const [keyData, nodeData] = await Promise.all([
        Promise.all(keyProjects.map(async (project) => ({
          label: project.label,
          data: await pointsFor(project),
          borderColor: colors[project.id],
        }))),
        Promise.all(nodeProjects.map(async (project) => ({
          label: project.label,
          data: await pointsFor(project),
          borderColor: colors[project.id],
        }))),
      ]);
      if (thisRefresh !== refreshId) return;

      for (const [chart, datasets] of [
        [chartInstances.keys, keyData],
        [chartInstances.nodes, nodeData],
      ]) {
        chart.data.datasets = datasets.map((dataset) => ({
          ...dataset,
          borderWidth: 1.5,
          pointRadius: 0,
          pointHitRadius: 5,
          tension: 0,
        }));
        chart.options.scales.x.min = currentRange.start * 1000;
        chart.options.scales.x.max = currentRange.end * 1000;
        chart.options.plugins.zoom.limits.x.min = currentRange.start * 1000;
        chart.options.plugins.zoom.limits.x.max = currentRange.end * 1000;
        chart.update("none");
      }

      const count = keyData.concat(nodeData).reduce((sum, dataset) => sum + dataset.data.length, 0);
      status.textContent = `${count.toLocaleString()} records shown · dates and times are UTC`;
    } catch (loadError) {
      if (thisRefresh !== refreshId) return;
      status.textContent = "Rate data could not be loaded.";
      error.textContent = loadError.message;
      error.hidden = false;
    }
  }

  function applyRange(start, end, selectedPreset = null) {
    if (!Number.isFinite(start) || !Number.isFinite(end) || start > end) {
      error.textContent = "Choose a valid date range.";
      error.hidden = false;
      return;
    }
    currentRange = { start, end };
    fromInput.value = dateInputValue(start);
    toInput.value = dateInputValue(end);
    document.querySelectorAll("[data-range]").forEach((button) => {
      button.classList.toggle("selected", button.dataset.range === selectedPreset);
    });
    refreshCharts();
  }

  function buildProjectToggles() {
    for (const project of manifest.projects) {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = project.id;
      input.checked = true;
      input.addEventListener("change", refreshCharts);
      const text = document.createElement("span");
      text.textContent = project.label;
      label.append(input, text);
      projectToggles.append(label);
    }
  }

  async function start() {
    if (typeof ChartZoom === "undefined") {
      throw new Error("The chart zoom library could not be loaded.");
    }
    Chart.register(ChartZoom);
    const response = await fetch(new URL("./data/manifest.json", document.baseURI));
    if (!response.ok) {
      throw new Error(`Could not load the rate data manifest (HTTP ${response.status}).`);
    }
    manifest = await response.json();
    if (manifest.version !== 1 || !Array.isArray(manifest.projects) || !manifest.projects.length) {
      throw new Error("The rate data manifest has an unsupported or empty format.");
    }

    buildProjectToggles();
    const allYears = manifest.projects.flatMap((project) => project.years);
    const first = Math.min(...allYears.map((year) => year.first));
    const last = Math.max(...allYears.map((year) => year.last));
    currentRange = { start: Math.max(first, last - 5 * 365 * 86400), end: last };
    chartInstances.keys = makeChart("keys-chart", "Gkeys/sec");
    chartInstances.nodes = makeChart("nodes-chart", "Gnodes/sec");

    document.querySelectorAll("[data-range]").forEach((button) => {
      button.addEventListener("click", () => {
        const end = last;
        const startByRange = {
          month: end - 30 * 86400,
          "six-months": end - 183 * 86400,
          year: end - 365 * 86400,
          "five-years": end - 5 * 365 * 86400,
          all: first,
        };
        applyRange(Math.max(first, startByRange[button.dataset.range]), end, button.dataset.range);
      });
    });
    document.querySelector("#apply-dates").addEventListener("click", () => {
      const start = Date.parse(`${fromInput.value}T00:00:00Z`) / 1000;
      const end = Date.parse(`${toInput.value}T23:59:59Z`) / 1000;
      applyRange(start, end);
    });
    document.querySelectorAll("[data-reset]").forEach((button) => {
      button.addEventListener("click", () => {
        const chart = chartInstances[button.dataset.reset];
        chart.resetZoom();
        chart.options.scales.x.min = currentRange.start * 1000;
        chart.options.scales.x.max = currentRange.end * 1000;
        chart.update("none");
      });
    });

    applyRange(Math.max(first, last - 5 * 365 * 86400), last, "five-years");
  }

  start().catch((startError) => {
    status.textContent = "Rate charts could not be initialized.";
    error.textContent = startError.message;
    error.hidden = false;
  });
})();
