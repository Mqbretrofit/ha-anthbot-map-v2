# ANTHBOT Reports changelog

## 1.0.0-test.11

- Adds the current Anthbot Reports diagnostics UI from Anthbot Map v2.4.6-beta.12.
- Shows robot identity/model directly in the diagnostics list.
- Distinguishes manufacturer-shareable reports (`gyári riport`) from Anthbot Map integration diagnostics (`integráció`).
- Adds the diagnostic detail route and lightweight diagnostics summary endpoint used by the dashboard.
- Fixes the Home Assistant App image packaging so `diagnostics_dashboard.py` and `diagnostic_detail.html` are included at runtime.
- Keeps the Reports app version independent from the Anthbot Map integration version so Home Assistant can offer Reports updates separately.
