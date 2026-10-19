from pathlib import Path
from datetime import datetime
import shutil
import sys

ROOT = Path.cwd()
app = ROOT / "frontend" / "src" / "App.tsx"
layout = ROOT / "frontend" / "src" / "components" / "AppLayout.tsx"
source = Path(__file__).resolve().parents[1] / "frontend" / "src" / "pages" / "ReportsPage.tsx"
dest = ROOT / "frontend" / "src" / "pages" / "ReportsPage.tsx"

for path in (app, layout, source):
    if not path.exists():
        print(f"ERROR: expected file not found: {path}")
        print("Run this installer from the MedIntel repository root (the folder containing frontend/ and backend/).")
        sys.exit(1)

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
for path in (app, layout):
    backup = path.with_suffix(path.suffix + f".before_reports_{stamp}.bak")
    shutil.copy2(path, backup)
    print(f"Backup: {backup.relative_to(ROOT)}")

if source.resolve() != dest.resolve():
    shutil.copy2(source, dest)
print(f"Added: {dest.relative_to(ROOT)}")

app_text = app.read_text(encoding="utf-8")
if 'from "./pages/ReportsPage"' not in app_text:
    anchor = 'import { GlucoTwinPage } from "./pages/GlucoTwinPage";'
    if anchor not in app_text:
        print("ERROR: could not find the GlucoTwin import in App.tsx. Page copied, but route was not auto-added.")
        sys.exit(2)
    app_text = app_text.replace(anchor, anchor + '\nimport { ReportsPage } from "./pages/ReportsPage";')
if 'path="/reports"' not in app_text:
    anchor = '''      <Route
        path="/patients"
        element={
          <ProtectedRoute>
            <PatientsPage />
          </ProtectedRoute>
        }
      />'''
    route = '''      <Route
        path="/reports"
        element={
          <ProtectedRoute>
            <ReportsPage />
          </ProtectedRoute>
        }
      />
'''
    if anchor not in app_text:
        print("ERROR: could not find the Patients route in App.tsx. Page copied, but route was not auto-added.")
        sys.exit(2)
    app_text = app_text.replace(anchor, anchor + '\n' + route.rstrip())
app.write_text(app_text, encoding="utf-8")
print("Updated: frontend/src/App.tsx")

layout_text = layout.read_text(encoding="utf-8")
if 'to: "/reports"' not in layout_text:
    anchor = '  { to: "/analytics", label: "Disease Analytics", section: "INTELLIGENCE", icon: "chart" },'
    nav = anchor + '\n  { to: "/reports", label: "Reports", section: "OPERATIONS", icon: "chart" },'
    if anchor not in layout_text:
        print("ERROR: could not find the Disease Analytics navigation item. Route added, but add Reports to NAV manually.")
        sys.exit(3)
    layout_text = layout_text.replace(anchor, nav)
    layout.write_text(layout_text, encoding="utf-8")
    print("Updated: frontend/src/components/AppLayout.tsx")
else:
    print("Reports navigation already exists; no duplicate added.")

print("\nReports feature installed. It refreshes every 30 seconds and includes manual refresh, CSV export and Print / PDF.")
print("Next run: cd frontend && npm run build")
