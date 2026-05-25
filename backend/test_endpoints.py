import urllib.request, json, urllib.error

def post(url, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        return None, e.read().decode()

def get(url):
    try:
        resp = urllib.request.urlopen(url)
        return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        return None, e.read().decode()

BASE = "http://localhost:8000"
passed = 0
failed = 0

# ── Test 1: SOAP + NEWS2 + ICD-10 ────────────────────────────────────────────
result, err = post(f"{BASE}/api/analyze/soap", {
    "raw_notes": "58F chest tightness 2d, HR 92 irreg, BP 148/90, sats 96%, RR 22, temp 37.8. Likely AF.",
    "shift_id": 3
})
if err:
    print(f"[FAIL] SOAP: {err[:200]}")
    failed += 1
else:
    d = result["data"]
    news2 = d.get("news2", {})
    icd_count = len(d.get("icd10", {}).get("suggestions", []))
    score = news2.get("score", "?")
    sev = news2.get("severity", "?")
    ms = result["processing_time_ms"]
    print(f"[PASS] SOAP: NEWS2={score}/20 ({sev}) | ICD-10={icd_count} codes | {ms}ms")
    passed += 1

# ── Test 2: Prescription Safety ───────────────────────────────────────────────
result, err = post(f"{BASE}/api/analyze/prescription-safety", {
    "drugs": ["warfarin 5mg od", "aspirin 75mg od", "ibuprofen 400mg tds"],
    "shift_id": 3,
    "patient_context": {"allergies": ["penicillin"], "weight_kg": 72, "renal_function": "moderate", "age": 68}
})
if err:
    print(f"[FAIL] Rx Safety: {err[:200]}")
    failed += 1
else:
    d = result["data"]
    overall = d.get("overall_safety", "?")
    flags = len(d.get("flags", []))
    adj = len(d.get("dose_adjustments", []))
    ms = result["processing_time_ms"]
    print(f"[PASS] Rx Safety: {overall.upper()} | {flags} flags | {adj} dose adjustments | {ms}ms")
    passed += 1

# ── Test 3: Analytics ─────────────────────────────────────────────────────────
result, err = get(f"{BASE}/api/analytics/shift")
if err:
    print(f"[FAIL] Analytics: {err[:200]}")
    failed += 1
else:
    ta = result.get("total_analyses", 0)
    ts = result.get("total_shifts", 0)
    rf = result.get("red_flags", {}).get("total", 0)
    print(f"[PASS] Analytics: {ta} analyses | {ts} shifts | {rf} red flags")
    passed += 1

# ── Test 4: Patient management ────────────────────────────────────────────────
result, err = post(f"{BASE}/api/patients", {
    "name": "Test Patient", "mrn": "MRN-TEST-001",
    "allergies": ["aspirin"], "weight_kg": 70,
    "renal_function": "normal", "hepatic_function": "normal"
})
if err:
    if "UNIQUE constraint failed" in err:
        print("[PASS] Patient create: patient already exists (OK)")
        passed += 1
    else:
        print(f"[FAIL] Patient create: {err[:200]}")
        failed += 1
else:
    pid = result.get("id")
    print(f"[PASS] Patient created: id={pid} | mrn={result.get('mrn')}")
    passed += 1

# ── Test 5: FHIR metadata ─────────────────────────────────────────────────────
result, err = get(f"{BASE}/fhir/metadata")
if err:
    print(f"[FAIL] FHIR metadata: {err[:200]}")
    failed += 1
else:
    rt = result.get("resourceType", "?")
    print(f"[PASS] FHIR: resourceType={rt}")
    passed += 1

# ── Test 6: DDx + ICD-10 ─────────────────────────────────────────────────────
result, err = post(f"{BASE}/api/analyze/ddx", {
    "clinical_presentation": "72M sudden chest pain radiating to back, diaphoresis, BP asymmetric, CXR widened mediastinum",
    "shift_id": 3
})
if err:
    print(f"[FAIL] DDx: {err[:200]}")
    failed += 1
else:
    d = result["data"]
    diffs = len(d.get("differentials", []))
    icd = len(d.get("top_icd10", []))
    ml = d.get("most_likely", "?")
    print(f"[PASS] DDx: {diffs} differentials | {icd} ICD-10 codes | Most likely: {ml[:50]}")
    passed += 1

# ── Test 7: Shift end + discharge PDF ─────────────────────────────────────────
result, err = post(f"{BASE}/api/shift/end", {"shift_id": 3})
if err:
    print(f"[FAIL] Shift end: {err[:200]}")
    failed += 1
else:
    total = result.get("summary", {}).get("total_analyses", 0)
    dur = result.get("duration_minutes", 0)
    print(f"[PASS] Shift end: {total} analyses | {dur} min duration")
    passed += 1

# PDF test
try:
    resp = urllib.request.urlopen(f"{BASE}/api/shift/3/discharge-summary")
    content_type = resp.headers.get("Content-Type", "")
    size = len(resp.read())
    print(f"[PASS] Discharge PDF: {size} bytes | Content-Type: {content_type}")
    passed += 1
except urllib.error.HTTPError as e:
    print(f"[FAIL] Discharge PDF: {e.code} {e.read().decode()[:200]}")
    failed += 1

print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed")
print("="*50)
