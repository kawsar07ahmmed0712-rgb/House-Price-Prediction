# House-Price-Prediction

## Multi-page dashboard website

I converted the `House-Price.ipynb` analysis into a clean multi-page dashboard under `web/`.

### Pages

- `web/index.html` - overview and executive snapshot
- `web/market.html` - outlier treatment and neighborhood market pulse
- `web/drivers.html` - key feature drivers and correlation analysis
- `web/profile.html` - profile-report alerts, missingness, imbalance, zero-heavy diagnostics
- `web/strategy.html` - managerial summary, risk, and next steps

### Regenerate web assets from notebook outputs

The script extracts chart images and metrics directly from:

- `House-Price.ipynb` executed outputs
- `ames_house_prices_profile.html` (fallback: `house_profile_compact.html`)

```bash
python scripts/build_dashboard_assets.py
```

Generated assets:

- `web/assets/charts/*`
- `web/assets/data/metrics.json`
- `web/assets/js/metrics.js`

### Run locally

From project root:

```bash
python -m http.server 8000
```

Then open:

- `http://localhost:8000/web/index.html`
