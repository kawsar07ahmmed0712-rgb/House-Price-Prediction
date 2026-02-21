(function () {
  const metrics = window.dashboardMetrics || {};
  const chartFiles = metrics.chart_files || {};
  const profile = metrics.profile_overview || {};

  const numberFmt = new Intl.NumberFormat("en-US");
  const currencyFmt = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
  const decimalFmt = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const compactFmt = new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  });

  function getValue(path) {
    if (!path) return null;
    return path.split(".").reduce((acc, key) => {
      if (acc && Object.prototype.hasOwnProperty.call(acc, key)) {
        return acc[key];
      }
      return null;
    }, metrics);
  }

  function formatValue(value, format) {
    if (value === null || value === undefined || Number.isNaN(value)) return "--";

    switch (format) {
      case "currency":
        return currencyFmt.format(Number(value));
      case "number":
        return numberFmt.format(Number(value));
      case "percent":
        return `${decimalFmt.format(Number(value))}%`;
      case "decimal":
        return decimalFmt.format(Number(value));
      case "compact":
        return compactFmt.format(Number(value));
      case "raw":
        return String(value);
      default:
        return String(value);
    }
  }

  function bindSimpleMetrics() {
    document.querySelectorAll("[data-metric]").forEach((node) => {
      const path = node.getAttribute("data-metric");
      const format = node.getAttribute("data-format") || "raw";
      node.textContent = formatValue(getValue(path), format);
    });
  }

  function bindCharts() {
    document.querySelectorAll("img[data-chart]").forEach((img) => {
      const chartKey = img.getAttribute("data-chart");
      if (chartKey && chartFiles[chartKey]) {
        img.src = chartFiles[chartKey];
      }
    });
  }

  function bindTopDriverCards() {
    const container = document.getElementById("driver-cards");
    if (!container) return;
    const drivers = metrics.top_drivers || [];
    container.innerHTML = "";
    drivers.forEach((driver, index) => {
      const card = document.createElement("article");
      card.className = "summary-card reveal";
      const corr =
        driver.correlation === null || driver.correlation === undefined
          ? "--"
          : decimalFmt.format(Number(driver.correlation));
      card.innerHTML = `
        <div class="summary-title">Driver ${index + 1}</div>
        <h3>${driver.feature || "--"}</h3>
        <p class="muted">Correlation with SalePrice: <strong>${corr}</strong></p>
      `;
      container.appendChild(card);
    });
  }

  function bindCorrelationList() {
    const tableBody = document.querySelector("#correlation-table tbody");
    if (!tableBody) return;
    const rows = metrics.top_correlations || [];
    tableBody.innerHTML = "";
    rows.forEach((row, index) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${index + 1}</td>
        <td>${row.feature || "--"}</td>
        <td>${decimalFmt.format(Number(row.correlation || 0))}</td>
      `;
      tableBody.appendChild(tr);
    });
  }

  function bindNeighborhoodTable() {
    const tableBody = document.querySelector("#neighborhood-table tbody");
    if (!tableBody) return;
    const rows = metrics.top_neighborhoods || [];
    tableBody.innerHTML = "";
    rows.forEach((row, index) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${index + 1}</td>
        <td>${row.neighborhood || "--"}</td>
        <td>${currencyFmt.format(Number(row.mean_saleprice || 0))}</td>
        <td>${currencyFmt.format(Number(row.median_saleprice || 0))}</td>
        <td>${numberFmt.format(Number(row.count || 0))}</td>
      `;
      tableBody.appendChild(tr);
    });
  }

  function bindMissingTable() {
    const tableBody = document.querySelector("#missing-table tbody");
    if (!tableBody) return;
    const rows = metrics.top_missing_features || [];
    tableBody.innerHTML = "";
    rows.slice(0, 10).forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${row.feature || "--"}</td>
        <td>${numberFmt.format(Number(row.missing_count || 0))}</td>
        <td>${decimalFmt.format(Number(row.missing_pct || 0))}%</td>
      `;
      tableBody.appendChild(tr);
    });
  }

  function bindSummaryBullets() {
    const ids = [
      ["drivers-bullets", "top_drivers_plain_english"],
      ["risk-bullets", "risks"],
      ["next-steps-bullets", "next_steps"],
    ];
    const summaryData = metrics.managerial_summary || {};

    ids.forEach(([id, key]) => {
      const list = document.getElementById(id);
      if (!list) return;
      list.innerHTML = "";
      const items = summaryData[key] || [];
      items.forEach((text) => {
        const li = document.createElement("li");
        li.textContent = text;
        list.appendChild(li);
      });
    });
  }

  function bindAlertTypePills() {
    const container = document.getElementById("alert-type-grid");
    if (!container) return;
    const counts = (profile && profile.alert_type_counts) || {};
    const entries = Object.entries(counts).sort((a, b) => Number(b[1]) - Number(a[1]));
    container.innerHTML = "";
    entries.forEach(([label, value]) => {
      const item = document.createElement("article");
      item.className = "alert-pill reveal";
      item.innerHTML = `
        <div class="alert-pill-label">${label}</div>
        <div class="alert-pill-value">${numberFmt.format(Number(value || 0))}</div>
      `;
      container.appendChild(item);
    });
  }

  function renderTableRows(tableId, rows, rowBuilder) {
    const tbody = document.querySelector(`#${tableId} tbody`);
    if (!tbody) return;
    tbody.innerHTML = "";
    rows.forEach((row, index) => {
      const tr = document.createElement("tr");
      tr.innerHTML = rowBuilder(row, index);
      tbody.appendChild(tr);
    });
  }

  function bindProfileTables() {
    const missingRows = ((profile && profile.top_missing_alerts) || []).slice(0, 10);
    const zeroRows = ((profile && profile.top_zero_alerts) || []).slice(0, 10);
    const imbalanceRows = ((profile && profile.top_imbalance_alerts) || []).slice(0, 10);
    const alertRows = ((profile && profile.alerts) || []).slice(0, 20);

    renderTableRows("profile-missing-table", missingRows, (row, index) => {
      return `
        <td>${index + 1}</td>
        <td>${row.feature || "--"}</td>
        <td>${numberFmt.format(Number(row.missing_count || 0))}</td>
        <td>${decimalFmt.format(Number(row.missing_pct || 0))}%</td>
      `;
    });

    renderTableRows("profile-zero-table", zeroRows, (row, index) => {
      return `
        <td>${index + 1}</td>
        <td>${row.feature || "--"}</td>
        <td>${numberFmt.format(Number(row.zero_count || 0))}</td>
        <td>${decimalFmt.format(Number(row.zero_pct || 0))}%</td>
      `;
    });

    renderTableRows("profile-imbalance-table", imbalanceRows, (row, index) => {
      return `
        <td>${index + 1}</td>
        <td>${row.feature || "--"}</td>
        <td>${decimalFmt.format(Number(row.dominant_pct || 0))}%</td>
      `;
    });

    renderTableRows("profile-alert-table", alertRows, (row, index) => {
      return `
        <td>${index + 1}</td>
        <td>${row.feature || "--"}</td>
        <td>${row.type || "--"}</td>
        <td>${row.message || "--"}</td>
      `;
    });
  }

  function bindGeneratedAt() {
    const node = document.querySelector("[data-generated-at]");
    if (!node) return;
    const generatedAt = metrics.meta && metrics.meta.generated_at_utc;
    if (!generatedAt) {
      node.textContent = "--";
      return;
    }
    const date = new Date(generatedAt);
    node.textContent = date.toLocaleString("en-US", {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
      timeZoneName: "short",
    });
  }

  function markActiveNav() {
    const path = window.location.pathname.split("/").pop() || "index.html";
    document.querySelectorAll(".nav-link").forEach((link) => {
      const href = link.getAttribute("href");
      if (href === path) {
        link.classList.add("active");
      }
    });
  }

  function revealOnScroll() {
    const revealNodes = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window)) {
      revealNodes.forEach((n) => n.classList.add("visible"));
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    revealNodes.forEach((node) => observer.observe(node));
  }

  function bindCopyrightYear() {
    const node = document.getElementById("year");
    if (node) node.textContent = String(new Date().getFullYear());
  }

  bindSimpleMetrics();
  bindCharts();
  bindTopDriverCards();
  bindCorrelationList();
  bindNeighborhoodTable();
  bindMissingTable();
  bindSummaryBullets();
  bindAlertTypePills();
  bindProfileTables();
  bindGeneratedAt();
  markActiveNav();
  revealOnScroll();
  bindCopyrightYear();
})();
