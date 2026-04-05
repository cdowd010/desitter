# Epistemic Web — Worked Examples

This document shows how data is ingested into the epistemic web through the gateway. It covers everything from the gateway inward: the entity model, the web's structural enforcement, the invariant validators, and the query traversals. The interface layer (CLI commands, MCP tool names) is not the focus here — what matters is the payload structure and the sequence rules the gateway enforces.

Read this alongside ARCHITECTURE.md. The architecture document explains *what* each piece is; these examples show *how they assemble*.

---

## How to Read These Examples

Each example shows a sequence of gateway calls and annotates what the web does automatically in response.

```python
# Call format
gateway.register("claim", { ... payload ... })
# → GatewayResult(status="ok", changed=True, tx_id="abc-123")

gateway.set("parameter", "PAR-001", { ... updated fields ... })
# → GatewayResult(status="ok", changed=True, tx_id="def-456")

gateway.transition("prediction", "P-001", "CONFIRMED")
# → GatewayResult(status="ok", changed=True, tx_id="ghi-789")

gateway.query("refutation_impact", pid="P-001")
# → GatewayResult(status="ok", changed=False, data={ ... })
```

**What the gateway enforces on every mutation:**
1. The resource alias resolves to a known entity type.
2. `repo.load()` reads the current web from disk — always fresh.
3. The entity is built from the payload and the web's mutation method is called. If this raises (broken reference, cycle, duplicate), the call returns `status="error"` immediately.
4. `validator.validate(new_web)` runs all ten semantic invariant checks. Any CRITICAL finding returns `status="BLOCKED"` and the disk is not touched.
5. If `dry_run=True`, returns `status="dry_run"` with findings but no write.
6. `repo.save(new_web)` atomically replaces the JSON files on disk.
7. The transaction is appended to the log. The result is returned.

**Bidirectional links the web maintains automatically** (you set the forward link, the web maintains the reverse):

| You set this… | Web automatically maintains… |
|---|---|
| `Claim.assumptions` | `Assumption.used_in_claims` |
| `Claim.analyses` | `Analysis.claims_covered` |
| `Analysis.uses_parameters` | `Parameter.used_in_analyses` |
| `Prediction.independence_group` | `IndependenceGroup.member_predictions` |
| `Prediction.tests_assumptions` | `Assumption.tested_by` |

**Registration order rules** (you cannot reference an entity that does not yet exist):
- Register `Parameter` before the `Analysis` that uses it.
- Register `Assumption` before the `Claim` that lists it.
- Register `Claim` before the `Prediction` that names it in `claim_ids`.
- Register `IndependenceGroup` before the `Prediction` that joins it.
- Register both `IndependenceGroup`s before the `PairwiseSeparation` that connects them.
- Register `Analysis` before the `Claim` that lists it in `analyses`.

---

## Section 1: Foundational Patterns

### 1.1 — Minimal Chain: One Claim, One Prediction, One Analysis

**Scenario:** A chemist claims that catalyst X increases reaction yield above 50%. They have one empirical assumption, one parameter, one analysis, and one prediction.

**Population sequence — registration order and auto-wired backlinks:**

| Step | Entity registered | Backlinks auto-wired by the web |
|------|------------------|--------------------------------|
| 1 | `PAR-001` parameter | (none — `used_in_analyses=∅` until AN-001 arrives) |
| 2 | `A-001` assumption | (none — `used_in_claims=∅`, `tested_by=∅`) |
| 3 | `AN-001` analysis | `PAR-001.used_in_analyses ← {AN-001}` |
| 4 | `C-001` claim | `A-001.used_in_claims ← {C-001}` · `AN-001.claims_covered ← {C-001}` |
| 5 | `IG-001` independence group | (none — `member_predictions=∅` until P-001 joins) |
| 6 | `P-001` prediction | `IG-001.member_predictions ← {P-001}` |
| 7 | transition `P-001 → CONFIRMED` | (status change only, no new structural links) |

**Entity graph (final state):**

```mermaid
graph LR
classDef bigText font-size:18px,color:#000;
    PAR001["PAR-001\nα = 0.05\n[Parameter]"]
    A001["A-001\nConditions controlled\n[Assumption · Methodological]"]
    AN001["AN-001\nyield_experiment.py\n[Analysis]"]
    C001["C-001\nCatalyst X raises yield > 0.50\n[Claim · Foundational · Numerical]"]
    IG001["IG-001\n2024-06 batch\n[IndependenceGroup]"]
    P001["P-001\npredict yield > 0.50\n✅ CONFIRMED  observed=0.57\n[Prediction]"]

    PAR001 -->|"used_in_analyses"| AN001
    AN001 -->|"claims_covered"| C001
    A001 -->|"used_in_claims"| C001
    C001 -->|"claim_ids"| P001
    P001 -->|"independence_group"| IG001
    IG001 -.->|"member_predictions"| P001

    style PAR001 fill:#ffd700,stroke:#b8860b
    style A001 fill:#ffa07a,stroke:#cd6600
    style AN001 fill:#87ceeb,stroke:#1e90ff
    style C001 fill:#90ee90,stroke:#228b22
    style P001 fill:#dda0dd,stroke:#8b008b
    style IG001 fill:#e0e0ff,stroke:#6666cc
```

```mermaid
graph LR
classDef bigText font-size:18px,color:#000;
    LP[" Parameter "] ~~~ LA[" Assumption "] ~~~ LAN[" Analysis "] ~~~ LC[" Claim "] ~~~ LPR[" Prediction "] ~~~ LIG[" Independence Group "]:::bigText
    style LP  fill:#ffd700,stroke:#b8860b
    style LA  fill:#ffa07a,stroke:#cd6600
    style LAN fill:#87ceeb,stroke:#1e90ff
    style LC  fill:#90ee90,stroke:#228b22
    style LPR fill:#dda0dd,stroke:#8b008b
    style LIG fill:#e0e0ff,stroke:#6666cc
```

Solid arrows = forward links you set explicitly. Dashed arrows = reverse backlinks the web maintains automatically.

**Step 1: Register the parameter.**

```python
gateway.register("parameter", {
    "id":    "PAR-001",
    "name":  "significance_threshold",
    "value": 0.05,
    "unit":  None,
    "notes": "Two-tailed t-test alpha level",
})
# → ok | PAR-001 registered
# Web state: parameters: {PAR-001: Parameter(value=0.05, used_in_analyses=set())}
# Note: used_in_analyses is empty — it will be auto-populated when AN-001 is registered.
```

**Step 2: Register the assumption.**

```python
gateway.register("assumption", {
    "id":                      "A-001",
    "statement":               "Reaction temperature, pressure, and reagent concentration "
                               "were held constant across all experimental runs.",
    "type":                    "M",                   # AssumptionType.METHODOLOGICAL
    "scope":                   "Yield experiment batch 2024-06",
    "falsifiable_consequence": None,                  # Methodological — no direct falsifier
})
# → ok | A-001 registered
# Web state: Assumption(used_in_claims=set(), tested_by=set())
# Backlinks start empty; they will be filled by the Claim and Prediction that reference this assumption.
```

**Step 3: Register the analysis.**

```python
gateway.register("analysis", {
    "id":              "AN-001",
    "path":            "analyses/yield_experiment.py",
    "command":         "python yield_experiment.py --batch 2024-06",
    "uses_parameters": ["PAR-001"],
    "notes":           "Two-tailed Welch t-test, 30 runs per condition",
})
# → ok | AN-001 registered
# Web auto-update: PAR-001.used_in_analyses now includes AN-001.
# Analysis.claims_covered starts empty — it will be auto-populated by the Claim.
```

**Step 4: Register the claim.**

```python
gateway.register("claim", {
    "id":                    "C-001",
    "statement":             "Catalyst X increases mean reaction yield above 0.50 "
                             "under standard laboratory conditions.",
    "type":                  "foundational",          # ClaimType.FOUNDATIONAL
    "scope":                 "Aqueous organic synthesis, batch process",
    "falsifiability":        "A controlled experiment showing mean yield ≤ 0.50 under "
                             "identical conditions would falsify this claim.",
    "category":              "numerical",             # ClaimCategory.NUMERICAL
    "assumptions":           ["A-001"],               # takes A-001 as given
    "analyses":              ["AN-001"],              # covered by AN-001
    "parameter_constraints": {"PAR-001": "< 0.05"},  # the t-test must be significant
})
# → ok | C-001 registered
# Web auto-updates:
#   A-001.used_in_claims now includes C-001
#   AN-001.claims_covered now includes C-001
```

**Step 5: Register the independence group.**

```python
gateway.register("independence_group", {
    "id":               "IG-001",
    "label":            "2024-06 yield experiment batch",
    "claim_lineage":    ["C-001"],
    "assumption_lineage": ["A-001"],
    "measurement_regime": "measured",
})
# → ok | IG-001 registered
# Note: only one independence group — zero pairwise separations are required.
# member_predictions starts empty; populated when P-001 is registered.
```

**Step 6: Register the prediction.**

```python
gateway.register("prediction", {
    "id":               "P-001",
    "observable":       "Mean yield in treated group relative to untreated control",
    "tier":             "fully_specified",         # ConfidenceTier.FULLY_SPECIFIED
    "status":           "PENDING",
    "evidence_kind":    "novel_prediction",        # EvidenceKind.NOVEL_PREDICTION
    "measurement_regime": "measured",
    "predicted":        0.55,                     # specific numerical forecast
    "specification":    "mean(yield_treated) > 0.50 with p < 0.05",
    "derivation":       "C-001 directly states yield exceeds 0.50; A-001 ensures the "
                        "difference is attributable to the catalyst.",
    "claim_ids":         ["C-001"],
    "tests_assumptions": [],                       # not testing A-001 — taking it as given
    "independence_group": "IG-001",
    "free_params":       0,                        # zero free parameters — pure forecast
    "falsifier":        "Mean yield ≤ 0.50 or p ≥ 0.05 would falsify.",
    "analysis":         "AN-001",
})
# → ok | P-001 registered
# Web auto-updates:
#   IG-001.member_predictions now includes P-001
# Validator runs: no CRITICAL findings.
#   INFO: C-001 is NUMERICAL with AN-001 linked — coverage is satisfied.
```

> **Web state after step 6:**
> ```
> parameters:  PAR-001 [used_in_analyses={AN-001}]:::bigText
> assumptions: A-001   [used_in_claims={C-001}, tested_by=∅]:::bigText
> analyses:    AN-001  [claims_covered={C-001}]:::bigText
> claims:      C-001   [assumptions={A-001}, analyses={AN-001}]:::bigText
> ind_groups:  IG-001  [member_predictions={P-001}]  ← auto-wired
> predictions: P-001   [PENDING, tier=FULLY_SPECIFIED, free_params=0]:::bigText
> ```
> All structural links are in place. The web is ready for the observation.

**Step 7: Researcher runs the experiment, result is p=0.02, mean yield=0.57. Transition prediction.**

```python
# First, record the observed value by updating the prediction.
gateway.set("prediction", "P-001", {
    "id":               "P-001",
    "observable":       "Mean yield in treated group relative to untreated control",
    "tier":             "fully_specified",
    "status":           "PENDING",
    "evidence_kind":    "novel_prediction",
    "measurement_regime": "measured",
    "predicted":        0.55,
    "observed":         0.57,                    # recorded result
    "specification":    "mean(yield_treated) > 0.50 with p < 0.05",
    "derivation":       "C-001 directly states yield exceeds 0.50; A-001 ensures the "
                        "difference is attributable to the catalyst.",
    "claim_ids":         ["C-001"],
    "tests_assumptions": [],
    "independence_group": "IG-001",
    "free_params":       0,
    "falsifier":        "Mean yield ≤ 0.50 or p ≥ 0.05 would falsify.",
    "analysis":         "AN-001",
})
# → ok | P-001 updated

# Now transition status.
gateway.transition("prediction", "P-001", "CONFIRMED")
# → ok | P-001 → CONFIRMED
```

**Final web state — what the queries now return:**

```python
gateway.query("assumption_support_status", aid="A-001")
# data = {
#   "direct_claims":          {"C-001"},
#   "dependent_predictions":  {"P-001"},   # P-001's derivation chain includes A-001
#   "tested_by":              set(),       # nobody explicitly tests A-001
# }

gateway.query("refutation_impact", pid="P-001")
# data = {
#   "claim_ids":             {"C-001"},
#   "claim_ancestors":       set(),        # C-001 is FOUNDATIONAL — no ancestors
#   "implicit_assumptions":  {"A-001"},    # the full assumption set behind C-001
# }
```

The full chain is intact: one parameter, one assumption, one analysis, one claim, one prediction — confirmed by a single independent experiment.

**Conclusion chain — how the epistemic path leads to the outcome:**

```mermaid
graph TD
classDef bigText font-size:18px;
    A001["A-001\nConditions were controlled\n[Methodological assumption — taken as given]"]
    PAR001["PAR-001\nα = 0.05"]:::bigText
    AN001["AN-001\nyield_experiment.py"]:::bigText
    C001["C-001\nCatalyst X raises reaction yield above 0.50"]:::bigText
    P001["P-001\nPredict: mean yield > 0.50  free_params=0"]:::bigText
    OBS["Observation\nmean yield = 0.57,  p = 0.02"]:::bigText
    OUT["✅ CONFIRMED\nThe claim is grounded.\nOne independent experimental run supports it."]:::bigText

    A001 -->|"underpins"| C001
    PAR001 -->|"parameterises"| AN001
    AN001 -->|"covers"| C001
    C001 -->|"grounds"| P001
    OBS -->|"confirms"| P001
    P001 --> OUT

    style A001 fill:#ffa07a
    style PAR001 fill:#ffd700
    style AN001 fill:#87ceeb
    style C001 fill:#90ee90
    style P001 fill:#dda0dd
    style OBS fill:#fff0f0,stroke:#ff6666
    style OUT fill:#e8ffe8,stroke:#228b22,stroke-width:2px
```

```mermaid
graph LR
classDef bigText font-size:18px;
    LA[" Assumption "] ~~~ LAN[" Analysis "] ~~~ LC[" Claim "] ~~~ LPR[" Prediction "] ~~~ LOBS[" Observation "] ~~~ LOUT[" Confirmed outcome "]:::bigText
    style LA   fill:#ffa07a,stroke:#cd6600
    style LAN  fill:#87ceeb,stroke:#1e90ff
    style LC   fill:#90ee90,stroke:#228b22
    style LPR  fill:#dda0dd,stroke:#8b008b
    style LOBS fill:#fff0f0,stroke:#ff6666
    style LOUT fill:#e8ffe8,stroke:#228b22,stroke-width:2px
```

---

### 1.2 — Claim DAG: Derived Claims and Dependency Traversal

**Scenario:** A materials scientist has three claims. Two are foundational observations; the third is derived from both. A prediction tests the derived claim.

**Claim dependency graph:**
```
C-001 (FOUNDATIONAL): alloy composition determines grain size
C-002 (FOUNDATIONAL): grain size determines tensile strength
    ↓ depends_on
C-003 (DERIVED):      alloy composition predicts tensile strength
    ↓ depends_on C-001 AND C-002
```

```python
gateway.register("claim", {
    "id":            "C-001",
    "statement":     "The ratio of chromium to nickel in the alloy determines "
                     "the average grain size after annealing.",
    "type":          "foundational",
    "scope":         "Cr-Ni alloy series, 800°C anneal",
    "falsifiability": "Different Cr:Ni ratios producing identical grain size distributions "
                      "would falsify this.",
    "category":      "qualitative",
})
# → ok

gateway.register("claim", {
    "id":            "C-002",
    "statement":     "Smaller grain size increases tensile strength through the "
                     "Hall-Petch mechanism.",
    "type":          "foundational",
    "scope":         "Polycrystalline metals, ambient temperature",
    "falsifiability": "A metal with smaller grains showing equivalent or lower tensile "
                      "strength than a coarser-grained sample would falsify this.",
    "category":      "numerical",
})
# → ok

gateway.register("claim", {
    "id":            "C-003",
    "statement":     "Increasing the chromium fraction in Cr-Ni alloys above 18% "
                     "increases tensile strength above 650 MPa after standard annealing.",
    "type":          "derived",
    "scope":         "Cr-Ni alloys, 18–25% Cr range, 800°C anneal",
    "falsifiability": "A Cr fraction above 18% producing tensile strength ≤ 650 MPa "
                      "under identical conditions would falsify this.",
    "category":      "numerical",
    "depends_on":    ["C-001", "C-002"],    # derives from both foundational claims
})
# → ok | C-003 registered
# Web validates: DFS from C-003 checks C-001 and C-002 — no cycle.
```

**What the traversal queries return:**

```python
gateway.query("claim_lineage", cid="C-003")
# data = {"lineage": {"C-001", "C-002"}}
# "C-003 rests on C-001 and C-002. Both must hold for C-003 to be valid."

gateway.query("claims_depending_on_claim", cid="C-001")
# data = {"depending": {"C-003"}}
# "If C-001 is retracted, C-003 is immediately downstream."
```

**Claim dependency graph and traversal results:**

```mermaid
graph TD
classDef bigText font-size:18px;
    C001["C-001\nAlloy composition → grain size\n[Foundational]"]
    C002["C-002\nGrain size → tensile strength\n[Foundational]"]
    C003["C-003\nAlloy composition → tensile strength ≥ 650 MPa\n[Derived]"]

    C001 -->|"depends_on"| C003
    C002 -->|"depends_on"| C003

    LIN["claim_lineage(C-003)\n= {C-001, C-002}\n'C-003 rests on both foundational claims'"]:::bigText
    DEP["claims_depending_on(C-001)\n= {C-003}\n'Retract C-001 → C-003 is downstream'"]:::bigText
    style LIN color:#000
    style DEP color:#000

    C003 -.->|"lineage traversal"| LIN
    C001 -.->|"dependents traversal"| DEP

    style C001 fill:#90ee90,stroke:#228b22
    style C002 fill:#90ee90,stroke:#228b22
    style C003 fill:#c8e6c9,stroke:#388e3c,stroke-width:2px
    style LIN fill:#f5f5f5,stroke:#999
    style DEP fill:#f5f5f5,stroke:#999
```

```mermaid
graph LR
classDef bigText font-size:18px;
    LCF[" Foundational Claim "] ~~~ LCD[" Derived Claim "] ~~~ LQ[" Query result "]:::bigText
    style LCF fill:#90ee90,stroke:#228b22,stroke-width:2px
    style LCD fill:#c8e6c9,stroke:#388e3c
    style LQ  fill:#f5f5f5,stroke:#999
```

**Cycle detection: what happens if you try to create a cycle.**

After these three claims exist, this registration is attempted:

```python
gateway.register("claim", {
    "id":         "C-004",
    "statement":  "Tensile strength feeds back into grain size during work hardening.",
    "type":       "derived",
    "scope":      "...",
    "falsifiability": "...",
    "depends_on": ["C-002", "C-003"],
})
# → ok (C-004 is not a cycle — it depends on C-002 and C-003, but nothing depends on C-004 yet)

# Now attempt a problematic update that would make C-002 depend on C-004,
# which already transitively depends on C-002:
gateway.set("claim", "C-002", {
    "id":            "C-002",
    "statement":     "Smaller grain size increases tensile strength through the Hall-Petch mechanism.",
    "type":          "foundational",
    "scope":         "Polycrystalline metals, ambient temperature",
    "falsifiability": "...",
    "category":      "numerical",
    "depends_on":    ["C-004"],   # C-004 → C-003 → C-002: this would be a cycle
})
# → error | EpistemicError: cycle detected in depends_on graph for C-002
# GatewayResult(status="error", changed=False)
# The disk is untouched. C-002 still has no depends_on.
```

---

### 1.3 — Assumption Testability: `tests_assumptions` vs `conditional_on`

**Scenario:** A physicist has an empirical assumption about detector calibration. Two predictions correctly reference it in different ways. A third prediction (incorrectly) tries to put it in both roles at once.

```python
gateway.register("assumption", {
    "id":                      "A-001",
    "statement":               "The calorimeter energy scale is calibrated to within ±2% "
                               "across the full detection range.",
    "type":                    "E",               # AssumptionType.EMPIRICAL
    "scope":                   "LHC Run 3 dataset",
    "falsifiable_consequence": "Known-mass particle resonances reconstructed with a mean "
                               "energy offset > 2% would falsify this calibration claim.",
})
# → ok | A-001 registered. tested_by is empty — no predictions yet.
```

**P-001 is explicitly designed to test whether A-001 holds** (tests_assumptions):

```python
gateway.register("prediction", {
    "id":               "P-001",
    "observable":       "Z boson mass reconstructed from calorimeter deposits",
    "tier":             "fully_specified",
    "status":           "PENDING",
    "evidence_kind":    "novel_prediction",
    "measurement_regime": "measured",
    "predicted":        91.188,            # known Z mass in GeV
    "specification":    "Reconstructed Z mass within ±2% of 91.188 GeV",
    "claim_ids":        [],                # tests the assumption directly, not a downstream claim
    "tests_assumptions": ["A-001"],        # THIS prediction tests the calibration
    "free_params":      0,
    "falsifier":        "Reconstructed Z mass offset > 2% of nominal would falsify A-001.",
})
# → ok | P-001 registered
# Web auto-update: A-001.tested_by now includes P-001.
```

**P-002 takes A-001 as a given (conditional_on):**

```python
gateway.register("claim", {
    "id":            "C-001",
    "statement":     "The Higgs boson couples to the Z boson with strength predicted by the SM.",
    "type":          "foundational",
    "scope":         "Standard Model predictions",
    "falsifiability": "A measured HZZ coupling deviating > 3σ from SM prediction.",
    "assumptions":   ["A-001"],            # takes calibration as given
})

gateway.register("prediction", {
    "id":               "P-002",
    "observable":       "HZZ coupling strength κ_Z",
    "tier":             "conditional",
    "status":           "PENDING",
    "evidence_kind":    "novel_prediction",
    "measurement_regime": "measured",
    "predicted":        1.0,               # SM predicts exactly 1.0
    "specification":    "κ_Z within 1.0 ± 0.15 (current experimental precision)",
    "claim_ids":        ["C-001"],
    "conditional_on":   ["A-001"],         # prediction only valid IF calibration holds
    "tests_assumptions": [],
    "free_params":      0,
    "falsifier":        "κ_Z deviating > 3σ from 1.0.",
})
# → ok | P-002 registered
# P-002 takes A-001 as a given. If A-001 is later falsified, P-002's results are suspect.
```

**Semantic distinction between the two valid predictions:**

```mermaid
graph TD
classDef bigText font-size:18px;
    A001["A-001\nCalorimeter calibration ±2%\n[Assumption · Empirical]"]

    P001["P-001\nZ boson mass reconstruction\ntests_assumptions: A-001\n\nDesigned to VERIFY whether A-001 is true.\nIf CONFIRMED → A-001 is validated.\nIf REFUTED → A-001 is under direct pressure."]:::bigText

    P002["P-002\nHZZ coupling strength κ_Z\nconditional_on: A-001\n\nTakes A-001 as a GIVEN.\nOnly valid if calibration holds.\nDoes not test whether it holds."]:::bigText

    A001 -->|"tested_by  [auto-wired]"| P001
    A001 -.->|"conditional dependency\n(P-002 is only valid while A-001 holds)"| P002

    style A001 fill:#ffa07a,stroke:#cd6600,stroke-width:2px
    style P001 fill:#dda0dd,stroke:#228b22,stroke-width:2px
    style P002 fill:#dda0dd,stroke:#8b008b
```

```mermaid
graph LR
classDef bigText font-size:18px;
    LA[" Assumption "] ~~~ LTEST[" Prediction: tests assumption "] ~~~ LCOND[" Prediction: conditional on assumption "]:::bigText
    style LA    fill:#ffa07a,stroke:#cd6600
    style LTEST fill:#dda0dd,stroke:#228b22,stroke-width:2px
    style LCOND fill:#dda0dd,stroke:#8b008b
```

If P-001 is later REFUTED, `validate_conditional_assumption_pressure` will emit a WARNING for P-002 — because P-002's conditional basis is now under adversarial pressure.

**P-003 (incorrect) tries to both test and condition on A-001:**

```python
gateway.register("prediction", {
    "id":               "P-003",
    "observable":       "Some other observable",
    "tier":             "conditional",
    "status":           "PENDING",
    "evidence_kind":    "novel_prediction",
    "measurement_regime": "measured",
    "predicted":        42.0,
    "claim_ids":        ["C-001"],
    "conditional_on":   ["A-001"],         # takes A-001 as given...
    "tests_assumptions": ["A-001"],        # ...AND tests A-001 simultaneously — contradiction
    "free_params":      0,
})
# Step 4 (web mutation): register_prediction succeeds — this is a structural operation.
# Step 5 (validation): validate_tests_conditional_overlap fires.
#   → CRITICAL: Prediction P-003 has A-001 in both tests_assumptions and conditional_on.
#     A prediction cannot simultaneously test an assumption and depend on it being true.
# → GatewayResult(status="BLOCKED", changed=False,
#                 findings=[Finding(severity=CRITICAL, source="predictions/P-003", ...)])
# The disk is untouched. P-003 does not exist in the web.
```

**What `validate_web` returns at this point (no P-003 in the web):**

```python
gateway.query("validate_web")   # equivalent to running validate_project
# findings = [
#   Finding(INFO, "assumptions/A-001",
#           "Assumption A-001 has a falsifiable_consequence and a tested_by prediction (P-001)."
#           " Coverage satisfied."),
# ]
# overall: CLEAN — no critical or warning issues.
```

---

## Section 2: Complex Patterns and Edge Cases

### 2.1 — Parameter Update Cascade

**Scenario:** A computational biologist runs a gene expression analysis using a false-discovery-rate threshold. She later changes the threshold. This does not automatically invalidate any results — it creates a staleness signal that the blast-radius query surfaces.

**Initial state after registering all entities:**

```python
gateway.register("parameter", {
    "id":    "PAR-001",
    "name":  "fdr_threshold",
    "value": 0.05,
    "unit":  None,
    "notes": "Benjamini-Hochberg FDR threshold for differential expression calls",
})
# → ok

gateway.register("analysis", {
    "id":              "AN-001",
    "path":            "analyses/rna_seq_deg.py",
    "command":         "python rna_seq_deg.py --fdr 0.05",
    "uses_parameters": ["PAR-001"],
})
# → ok | PAR-001.used_in_analyses auto-updated to {AN-001}

gateway.register("claim", {
    "id":                    "C-001",
    "statement":             "BRCA1 expression is significantly downregulated in "
                             "triple-negative breast cancer samples relative to controls.",
    "type":                  "foundational",
    "scope":                 "TCGA BRCA cohort, n=120",
    "falsifiability":        "A well-powered study finding no significant differential "
                             "expression at FDR < 0.05 would falsify this.",
    "category":              "numerical",
    "analyses":              ["AN-001"],
    "parameter_constraints": {"PAR-001": "< 0.05"},  # this claim has a threshold on PAR-001
})
# → ok | AN-001.claims_covered auto-updated to {C-001}

gateway.register("claim", {
    "id":                    "C-002",
    "statement":             "ATM expression is significantly upregulated in "
                             "triple-negative breast cancer samples relative to controls.",
    "type":                  "foundational",
    "scope":                 "TCGA BRCA cohort, n=120",
    "falsifiability":        "...",
    "category":              "numerical",
    "analyses":              ["AN-001"],
    "parameter_constraints": {"PAR-001": "< 0.05"},
})
# → ok

gateway.register("independence_group", {
    "id":    "IG-001",
    "label": "TCGA BRCA RNA-seq differential expression analysis",
    "claim_lineage":      ["C-001", "C-002"],
    "assumption_lineage": [],
    "measurement_regime": "measured",
})

gateway.register("prediction", {
    "id":               "P-001",
    "observable":       "BRCA1 log2 fold-change between TNBC and control",
    "tier":             "fully_specified",
    "status":           "CONFIRMED",
    "evidence_kind":    "retrodiction",
    "measurement_regime": "measured",
    "predicted":        -1.5,
    "observed":          -1.7,
    "claim_ids":        ["C-001"],
    "independence_group": "IG-001",
    "analysis":         "AN-001",
    "free_params":      0,
})
# → ok

gateway.register("prediction", {
    "id":               "P-002",
    "observable":       "ATM log2 fold-change between TNBC and control",
    "tier":             "fully_specified",
    "status":           "CONFIRMED",
    "evidence_kind":    "retrodiction",
    "measurement_regime": "measured",
    "predicted":        1.2,
    "observed":          1.1,
    "claim_ids":        ["C-002"],
    "independence_group": "IG-001",
    "analysis":         "AN-001",
    "free_params":      0,
})
# → ok
```

**Web state after initial registration (before parameter change):**

```mermaid
graph LR
classDef bigText font-size:18px;
    PAR001["PAR-001\nfdr_threshold = 0.05\n[Parameter]"]
    AN001["AN-001\nrna_seq_deg.py\n[Analysis]"]
    C001["C-001\nBRCA1 downregulated\n[Claim · Foundational]"]
    C002["C-002\nATM upregulated\n[Claim · Foundational]"]
    IG001["IG-001\nTCGA BRCA cohort\n[IndependenceGroup]"]
    P001["P-001\nBRCA1 log2FC\nCONFIRMED  observed=−1.7\n[Prediction]"]
    P002["P-002\nATM log2FC\nCONFIRMED  observed=1.1\n[Prediction]"]

    PAR001 -->|"used_in_analyses"| AN001
    AN001 -->|"claims_covered"| C001
    AN001 -->|"claims_covered"| C002
    C001 -->|"claim_ids"| P001
    C002 -->|"claim_ids"| P002
    P001 -->|"independence_group"| IG001
    P002 -->|"independence_group"| IG001

    style PAR001 fill:#ffd700
    style AN001 fill:#87ceeb
    style C001 fill:#90ee90
    style C002 fill:#90ee90
    style IG001 fill:#e0e0ff
    style P001 fill:#dda0dd
    style P002 fill:#dda0dd
```

```mermaid
graph LR
classDef bigText font-size:18px;
    LP[" Parameter "] ~~~ LAN[" Analysis "] ~~~ LC[" Claim "] ~~~ LPR[" Prediction "] ~~~ LIG[" Independence Group "]:::bigText
    style LP  fill:#ffd700,stroke:#b8860b
    style LAN fill:#87ceeb,stroke:#1e90ff
    style LC  fill:#90ee90,stroke:#228b22
    style LPR fill:#dda0dd,stroke:#8b008b
    style LIG fill:#e0e0ff,stroke:#6666cc
```

**Regulatory guidance changes the FDR standard to 0.01.**

```python
gateway.set("parameter", "PAR-001", {
    "id":    "PAR-001",
    "name":  "fdr_threshold",
    "value": 0.01,           # changed from 0.05 → 0.01
    "unit":  None,
    "notes": "Updated to 0.01 per journal submission requirements (Nature Methods 2024)",
})
# → ok | PAR-001 updated, changed=True
# The web stores the new value. That is all.
# P-001 and P-002 remain CONFIRMED. AN-001 is unchanged.
# Nothing is automatically invalidated. The web records what IS; it does not
# make judgments about what SHOULD be done.
```

**Now query the blast radius:**

```python
gateway.query("parameter_impact", pid="PAR-001")
# data = {
#   "stale_analyses":       {"AN-001"},         # AN-001 uses PAR-001
#   "constrained_claims":   {"C-001", "C-002"}, # both have parameter_constraints on PAR-001
#   "affected_claims":      {"C-001", "C-002"}, # union of stale_analyses coverage + constrained
#   "affected_predictions": {"P-001", "P-002"}, # all predictions downstream
# }
```

**Blast-radius diagram — what `parameter_impact(PAR-001)` surfaces:**

```mermaid
graph TD
classDef bigText font-size:18px;
    PAR001["PAR-001\nfdr_threshold: 0.05 → 0.01\n[Parameter changed]"]
    AN001["AN-001\n⚠️ STALE\n(was run with --fdr 0.05)"]:::bigText
    C001["C-001  ⚠️ AFFECTED\nparameter_constraints: PAR-001 < 0.05\n→ constraint annotation now stale"]:::bigText
    C002["C-002  ⚠️ AFFECTED\nparameter_constraints: PAR-001 < 0.05\n→ constraint annotation now stale"]:::bigText
    P001["P-001  ⚠️ AFFECTED\nCONFIRMED — but based on stale analysis"]:::bigText
    P002["P-002  ⚠️ AFFECTED\nCONFIRMED — but based on stale analysis"]:::bigText
    ACTION["Researcher must:\n1. Re-run AN-001 with --fdr 0.01\n2. Record new results\n3. Decide whether to transition P-001/P-002\n4. Update C-001/C-002 constraint annotations"]:::bigText

    PAR001 -->|"stale_analyses"| AN001
    PAR001 -->|"constrained_claims"| C001
    PAR001 -->|"constrained_claims"| C002
    AN001 -->|"affected_claims"| C001
    AN001 -->|"affected_claims"| C002
    C001 -->|"affected_predictions"| P001
    C002 -->|"affected_predictions"| P002
    P001 & P002 -.->|"researcher decision required"| ACTION

    style PAR001 fill:#ff9999,stroke:#cc0000,stroke-width:2px
    style AN001 fill:#ffcccc,stroke:#cc3333
    style C001 fill:#ffe0b2,stroke:#e65100
    style C002 fill:#ffe0b2,stroke:#e65100
    style P001 fill:#f3e5f5,stroke:#7b1fa2
    style P002 fill:#f3e5f5,stroke:#7b1fa2
    style ACTION fill:#fff9c4,stroke:#f57f17
```

```mermaid
graph LR
classDef bigText font-size:18px;
    LCP[" Changed parameter "] ~~~ LST[" Stale analysis "] ~~~ LAC[" Affected claim "] ~~~ LAP[" Affected prediction "] ~~~ LRA[" Required action "]:::bigText
    style LCP fill:#ff9999,stroke:#cc0000,stroke-width:2px
    style LST fill:#ffcccc,stroke:#cc3333
    style LAC fill:#ffe0b2,stroke:#e65100
    style LAP fill:#f3e5f5,stroke:#7b1fa2
    style LRA fill:#fff9c4,stroke:#f57f17
```

**What this means:** The analysis `AN-001` was run with `--fdr 0.05`. The threshold is now 0.01. Some genes that were called significant at 0.05 may not meet 0.01. The researcher needs to:
1. Re-run `AN-001` with `--fdr 0.01`.
2. Record the new result (via `ds record` once implemented).
3. Check whether P-001 and P-002's observed values still hold under the stricter threshold.
4. If BRCA1 no longer meets FDR < 0.01, transition P-001 to `STRESSED` or `REFUTED`.
5. Update `C-001.parameter_constraints` to reflect the new threshold.

The web has not made any of these decisions. It has surfaced the complete structural consequence of the parameter change and left the scientific judgment to the researcher.

**What `check_stale` will report:**

Once `check_stale` is implemented, it will compare the SHA fingerprint of the rendered views against the current web state. Because PAR-001 has changed, the rendered "parameters" view surface is stale and will be flagged. The analysis-staleness signal (AN-001 was run under different parameters) will be reported as a finding tied to the analysis record.

---

### 2.2 — Claim Retraction and the Downstream Block

**Scenario:** Three claims in a dependency chain. A foundational claim is found to be wrong. Naively retract it — get blocked. Understand why, then do it correctly.

```python
gateway.register("claim", {
    "id":            "C-001",
    "statement":     "Aspirin irreversibly inhibits COX-1 and COX-2 enzymes.",
    "type":          "foundational",
    "scope":         "In vitro and in vivo pharmacological studies",
    "falsifiability": "Reversal of platelet aggregation inhibition after aspirin "
                      "cessation within 24 hours would falsify irreversibility.",
    "category":      "qualitative",
})

gateway.register("claim", {
    "id":            "C-002",
    "statement":     "COX inhibition by aspirin reduces thromboxane A2 synthesis.",
    "type":          "derived",
    "scope":         "Platelet function studies",
    "falsifiability": "...",
    "category":      "qualitative",
    "depends_on":    ["C-001"],
})

gateway.register("claim", {
    "id":            "C-003",
    "statement":     "Low-dose aspirin reduces secondary cardiovascular event risk "
                     "through sustained platelet inhibition.",
    "type":          "derived",
    "scope":         "Secondary prevention population, 81mg daily",
    "falsifiability": "...",
    "category":      "qualitative",
    "depends_on":    ["C-002"],
})

gateway.register("prediction", {
    "id":               "P-001",
    "observable":       "Relative risk of MI in aspirin vs. placebo group",
    "tier":             "fully_specified",
    "status":           "CONFIRMED",
    "evidence_kind":    "retrodiction",
    "measurement_regime": "measured",
    "predicted":        0.75,
    "observed":          0.72,
    "claim_ids":        ["C-001", "C-002", "C-003"],
    "free_params":      0,
})
```

**Dependency graph — why the retraction is blocked:**

```mermaid
graph TD
classDef bigText font-size:18px;
    C001["C-001\nAspirin inhibits COX-1 & COX-2\n[Attempting: RETRACT]"]
    C002["C-002\nCOX inhibition reduces TXA2\n[depends_on C-001]"]
    C003["C-003\nAspirin reduces CV risk\n[depends_on C-002]"]
    P001["P-001\nRR of MI = 0.75\nCONFIRMED\n[claim_ids: C-001, C-002, C-003]"]
    BLOCK["❌ BLOCKED\nCRITICAL: P-001.claim_ids ∋ C-001\nCRITICAL: C-002.depends_on ∋ C-001\nDisk untouched. Must clear downstream first."]:::bigText

    C001 -->|"depends_on"| C002
    C002 -->|"depends_on"| C003
    C001 -.->|"cited by"| P001
    C002 -.->|"cited by"| P001
    C003 -.->|"cited by"| P001
    C001 -->|"validate_retracted_claim_citations fires"| BLOCK

    style C001 fill:#ff6666,stroke:#cc0000,stroke-width:2px
    style C002 fill:#90ee90
    style C003 fill:#90ee90
    style P001 fill:#dda0dd
    style BLOCK fill:#ffe0e0,stroke:#cc0000,stroke-width:2px
```

```mermaid
graph LR
classDef bigText font-size:18px;
    LR[" Being retracted "] ~~~ LC[" Downstream claim "] ~~~ LPR[" Prediction (cites retracted) "] ~~~ LBK[" BLOCKED "]:::bigText
    style LR  fill:#ff6666,stroke:#cc0000,stroke-width:2px
    style LC  fill:#90ee90,stroke:#228b22
    style LPR fill:#dda0dd,stroke:#8b008b
    style LBK fill:#ffe0e0,stroke:#cc0000,stroke-width:2px
```

**Suppose new research suggests COX-2 inhibition is actually reversible in endothelial tissue. The researcher wants to revise C-001 to "REVISED" first, then later retract it entirely.**

```python
# Step 1: Transition to REVISED — succeeds because no validator blocks status=REVISED.
gateway.transition("claim", "C-001", "REVISED")
# → ok | C-001 → REVISED

# Step 2: Attempt full retraction.
gateway.transition("claim", "C-001", "RETRACTED")
# Step 4: web.transition_claim("C-001", RETRACTED) → new_web where C-001.status = RETRACTED
# Step 5: validator.validate(new_web)
#   → validate_retracted_claim_citations fires.
#   → P-001.claim_ids contains C-001. C-001 is now RETRACTED.
#     CRITICAL: Prediction P-001 still cites retracted claim C-001.
#   → C-002.depends_on contains C-001. C-001 is now RETRACTED.
#     CRITICAL: Claim C-002 still depends on retracted claim C-001.
# → GatewayResult(status="BLOCKED", changed=False,
#                 findings=[
#                   Finding(CRITICAL, "predictions/P-001", "cites retracted C-001"),
#                   Finding(CRITICAL, "claims/C-002",      "depends on retracted C-001"),
#                 ])
```

**The correct sequence — clear the downstream first.**

```python
# First: update P-001 to remove C-001 from its claim_ids.
# (In practice this would also require updating derivation and specification.)
gateway.set("prediction", "P-001", {
    "id":               "P-001",
    "observable":       "Relative risk of MI in aspirin vs. placebo group",
    "tier":             "fully_specified",
    "status":           "CONFIRMED",
    "evidence_kind":    "retrodiction",
    "measurement_regime": "measured",
    "predicted":        0.75,
    "observed":          0.72,
    "claim_ids":        ["C-002", "C-003"],   # C-001 removed
    "derivation":       "Revised: rests on C-002 and C-003 only. The reversibility "
                        "of COX-1 inhibition (C-001) is now under review.",
    "free_params":      0,
})
# → ok

# Second: update C-002 to remove depends_on C-001.
gateway.set("claim", "C-002", {
    "id":            "C-002",
    "statement":     "COX inhibition by aspirin reduces thromboxane A2 synthesis.",
    "type":          "foundational",          # promoted to foundational since C-001 is gone
    "scope":         "Platelet function studies",
    "falsifiability": "...",
    "category":      "qualitative",
    "depends_on":    [],                      # C-001 removed
})
# → ok

# Now the retraction succeeds.
gateway.transition("claim", "C-001", "RETRACTED")
# → ok | C-001 → RETRACTED
# Validator re-runs: no references to C-001 remain in any active prediction or claim.
```

**Lesson:** The gateway enforces epistemic hygiene aggressively. You cannot silently break the derivation chain. Every entity that cited a retracted claim must be updated first. This forces the researcher to explicitly acknowledge that downstream conclusions are now ungrounded — the cascade is made visible and unbypassable.

---

### 2.3 — Independence Groups: Registration Order

**Scenario:** A researcher wants to register two independent experimental runs as separate independence groups and document why they are independent. The correct registration order is: groups first (empty), then the pairwise separation, then predictions into each group.

```python
gateway.register("independence_group", {"id": "IG-001", "label": "Lab A: NMR experiment", ...})
# → ok | 1 group, 0 pairs, 0 separations needed.

gateway.register("independence_group", {"id": "IG-002", "label": "Lab B: independent NMR replication", ...})
# → ok | 2 groups, neither has predictions yet — separation check does not fire.

gateway.register("pairwise_separation", {
    "id": "PS-001", "group_a": "IG-001", "group_b": "IG-002",
    "basis": "Different instruments at geographically separate sites.",
})
# → ok | both groups exist; separation documented.

gateway.register("prediction", {
    "id": "P-001", ..., "independence_group": "IG-001",
})
# → ok | IG-001 now has 1 prediction; IG-002 still has 0 — separation check does not fire.

gateway.register("prediction", {
    "id": "P-002", ..., "independence_group": "IG-002",
})
# → ok | IG-002 now has 1 prediction; both groups active; PS-001 already exists — clean.
```

The validator rule: *a PairwiseSeparation is required for every pair of independence groups where **both** have at least one member prediction. Empty groups are declarations of intent — no separation is required until predictions join them.*

**The consequence of skipping the separation:** if you add predictions to both groups without first registering a PairwiseSeparation, the next mutation will be blocked.

```python
# Wrong order: predictions first, separation never registered.
gateway.register("prediction", {"id": "P-001", ..., "independence_group": "IG-001"})
# → ok (IG-002 is still empty — no check fires yet)
gateway.register("prediction", {"id": "P-002", ..., "independence_group": "IG-002"})
# Step 5: validator.validate(new_web)
#   → validate_independence_semantics: both groups now have predictions, 0 separations.
#   → CRITICAL: Missing PairwiseSeparation for (IG-001, IG-002).
# → GatewayResult(status="BLOCKED", changed=False)
# Fix: register PS-001 first, then retry P-002.
```

**Correct registration sequence:**

```mermaid
graph TD
classDef bigText font-size:18px;
    S1["1. Register IG-001  (empty)  ✓"]:::bigText
    S2["2. Register IG-002  (empty)  ✓\n   Neither group has predictions yet —\n   separation check does not fire"]:::bigText
    S3["3. Register PS-001  ✓\n   (basis: different instruments, different sites)"]:::bigText
    S4["4. Register P-001 → IG-001  ✓\n   (IG-002 still empty — check skipped)"]:::bigText
    S5["5. Register P-002 → IG-002  ✓\n   Both groups now active + PS-001 exists\n   → validator satisfied"]:::bigText
    S1 --> S2 --> S3 --> S4 --> S5
```

```mermaid
graph LR
classDef bigText font-size:18px;
    LS[" Registration step "]:::bigText
    style LS fill:#f0f0f0,stroke:#888
```

---

## Section 3: Real-World Full Chains

### 3.1 — Eddington 1919: Confirming General Relativity

**Context:** Einstein's General Relativity (1915) predicted that light passing near a massive body would be deflected. The predicted angle — 1.75 arcseconds at the solar limb — was exactly twice the Newtonian prediction. In May 1919, Arthur Eddington led expeditions to Sobral (Brazil) to photograph stars near the solar limb during a total eclipse. The Sobral result confirmed the GR prediction.

This example shows: foundational + derived claim chain, FULLY_SPECIFIED prediction from a pure theoretical deduction, NOVEL_PREDICTION evidence kind (prediction made in 1915, measured in 1919), and a parameter carrying the numerical forecast.

**Population sequence:**

| Step | Entity | Backlinks auto-wired |
|------|--------|---------------------|
| 1 | `PAR-001` 1.75 arcsec | — |
| 2 | `A-001` plate accuracy | — |
| 3 | `A-002` reference stars stable | — |
| 4 | `T-001` General Relativity | — |
| 5 | `C-001` spacetime curvature | — |
| 6 | `C-002` null geodesics | — |
| 7 | `C-003` 1.75 arcsec deflection (derived) | `A-001.used_in_claims ← {C-003}` · `A-002.used_in_claims ← {C-003}` |
| 8 | `AN-001` eddington_sobral_1919.py | `PAR-001.used_in_analyses ← {AN-001}` |
| 9 | update `C-003` to link `AN-001` | `AN-001.claims_covered ← {C-003}` |
| 10 | `IG-001` Sobral expedition | — |
| 11 | `P-001` predict 1.75 arcsec | `IG-001.member_predictions ← {P-001}` · `A-001.tested_by ← {P-001}` |
| 12 | record observed=1.98, transition `P-001 → CONFIRMED` | — |
| 13 | update `T-001` with related entities | — |
| 14 | register `D-001` Discovery | — |

**Entities registered in order:**

```python
# --- Parameters ---

gateway.register("parameter", {
    "id":     "PAR-001",
    "name":   "gr_predicted_deflection_arcsec",
    "value":  1.75,
    "unit":   "arcsec",
    "source": "Einstein 1915, Annalen der Physik",
    "notes":  "Predicted angular deflection of starlight at the solar limb under GR. "
              "Newtonian prediction is exactly half this value (0.875 arcsec).",
})
# → ok

# --- Assumptions ---

gateway.register("assumption", {
    "id":                      "A-001",
    "statement":               "Photographic plate astrometry at the Sobral site achieved "
                               "positional accuracy sufficient to distinguish 1.75 arcsec "
                               "deflection from 0.875 arcsec.",
    "type":                    "E",            # EMPIRICAL
    "scope":                   "Sobral eclipse expedition, 29 May 1919",
    "falsifiable_consequence": "If calibration stars show systematic position errors "
                               "> 0.3 arcsec, the measurement precision is insufficient "
                               "to discriminate between the GR and Newtonian predictions.",
    "source":                  "Dyson, Eddington, Davidson 1920 MNRAS",
})
# → ok

gateway.register("assumption", {
    "id":       "A-002",
    "statement": "The reference star positions measured during the eclipse are not "
                 "themselves displaced by the solar gravitational field at the plate scale.",
    "type":     "M",            # METHODOLOGICAL — systematic control
    "scope":    "Sobral eclipse expedition, 29 May 1919",
    "notes":    "Reference stars were chosen sufficiently far from the solar limb to "
                "keep their own deflection below 0.05 arcsec.",
})
# → ok

# --- Theory ---

gateway.register("theory", {
    "id":     "T-001",
    "title":  "General Relativity",
    "status": "active",
    "summary": "Einstein's theory that gravity is the curvature of spacetime produced "
               "by mass-energy. Replaces Newtonian gravity at high mass/velocity regimes.",
    "source": "Einstein 1915",
})
# → ok

# --- Claims ---

gateway.register("claim", {
    "id":            "C-001",
    "statement":     "General Relativity describes gravity as spacetime curvature "
                     "proportional to the local mass-energy density.",
    "type":          "foundational",
    "scope":         "All physical regimes where GR has been tested",
    "falsifiability": "Any observation inconsistent with the Einstein field equations "
                      "at a statistically significant level would falsify this.",
    "category":      "qualitative",
    "source":        "Einstein 1915",
})
# → ok

gateway.register("claim", {
    "id":            "C-002",
    "statement":     "Electromagnetic radiation propagates along null geodesics in "
                     "curved spacetime.",
    "type":          "foundational",
    "scope":         "All physical regimes where GR has been tested",
    "falsifiability": "Detection of photons following paths inconsistent with null "
                      "geodesic equations in a known gravitational field.",
    "category":      "qualitative",
    "source":        "Einstein 1916",
})
# → ok

gateway.register("claim", {
    "id":            "C-003",
    "statement":     "The gravitational field of the Sun causes a measurable deflection "
                     "of light rays passing near the solar limb, equal to 1.75 arcsec.",
    "type":          "derived",
    "scope":         "Solar limb, passing starlight",
    "falsifiability": "Measured deflection outside the range 1.75 ± 0.3 arcsec would "
                      "falsify this claim (within 1919 measurement precision).",
    "category":      "numerical",
    "depends_on":    ["C-001", "C-002"],
    "assumptions":   ["A-001", "A-002"],
    "parameter_constraints": {"PAR-001": "== 1.75"},
})
# → ok
# C-001.used_in_claims, C-002... wait — claims do not use other claims as assumptions.
# The depends_on is between claims.
# A-001.used_in_claims auto-updated to {C-003}
# A-002.used_in_claims auto-updated to {C-003}

# --- Analysis ---

gateway.register("analysis", {
    "id":              "AN-001",
    "path":            "analyses/eddington_sobral_1919.py",
    "command":         "python eddington_sobral_1919.py --plates astrographic --stars 7",
    "uses_parameters": ["PAR-001"],
    "notes":           "Re-reduction of Sobral astrographic plates. "
                       "7 stars measured. Mean deflection derived by least squares.",
})
# → ok | PAR-001.used_in_analyses auto-updated to {AN-001}

# Update C-003 to link to the analysis.
# (We register the analysis first, then link C-003 to it.)
gateway.set("claim", "C-003", {
    "id":            "C-003",
    "statement":     "The gravitational field of the Sun causes a measurable deflection "
                     "of light rays passing near the solar limb, equal to 1.75 arcsec.",
    "type":          "derived",
    "scope":         "Solar limb, passing starlight",
    "falsifiability": "Measured deflection outside the range 1.75 ± 0.3 arcsec would "
                      "falsify this claim.",
    "category":      "numerical",
    "depends_on":    ["C-001", "C-002"],
    "assumptions":   ["A-001", "A-002"],
    "analyses":      ["AN-001"],
    "parameter_constraints": {"PAR-001": "== 1.75"},
})
# → ok | AN-001.claims_covered auto-updated to {C-003}

# --- Independence group ---

gateway.register("independence_group", {
    "id":               "IG-001",
    "label":            "Sobral 1919 eclipse expedition — astrographic telescope",
    "claim_lineage":    ["C-001", "C-002", "C-003"],
    "assumption_lineage": ["A-001", "A-002"],
    "measurement_regime": "measured",
    "notes":            "Four-inch astrographic refractor. 7 comparison stars. "
                        "Plates re-measured in Cambridge by Crommelin and Davidson.",
})
# → ok | only 1 group — no pairwise separation required.

# --- Prediction ---

gateway.register("prediction", {
    "id":               "P-001",
    "observable":       "Mean angular displacement of Hyades stars near solar limb "
                        "relative to comparison positions taken 6 months prior",
    "tier":             "fully_specified",
    "status":           "PENDING",
    "evidence_kind":    "novel_prediction",     # predicted in 1915; measured in 1919
    "measurement_regime": "measured",
    "predicted":        1.75,
    "specification":    "Mean deflection at mean distance from solar centre corresponding "
                        "to 1.75 × (solar radius / angular separation) arcsec",
    "derivation":       "C-001 gives the curvature of spacetime near the Sun. "
                        "C-002 requires light to follow null geodesics in that curvature. "
                        "C-003 quantifies the resulting deflection at the solar limb. "
                        "Together they make a unique numerical prediction requiring no "
                        "free parameter adjustments.",
    "claim_ids":        ["C-001", "C-002", "C-003"],
    "tests_assumptions": ["A-001"],    # confirmation tests whether the plates were accurate
    "conditional_on":   ["A-002"],     # takes reference star stability as given
    "independence_group": "IG-001",
    "analysis":         "AN-001",
    "free_params":      0,
    "falsifier":        "Mean deflection < 1.0 or > 2.5 arcsec at the 95% confidence "
                        "level would falsify the GR prediction.",
    "source":           "Einstein 1916 prediction; Dyson, Eddington, Davidson 1920 result",
})
# → ok
# Web auto-updates: IG-001.member_predictions = {P-001}
#                  A-001.tested_by = {P-001}
```

**Full entity relationship graph (before transition):**

```mermaid
graph TD
classDef bigText font-size:18px;
    PAR001["PAR-001\n1.75 arcsec\n[Parameter]"]
    A001["A-001\nPlate accuracy sufficient\n[Assumption · Empirical]"]
    A002["A-002\nRef. stars not displaced\n[Assumption · Methodological]"]
    T001["T-001\nGeneral Relativity\n[Theory]"]
    C001["C-001\nGravity = spacetime curvature\n[Claim · Foundational]"]
    C002["C-002\nLight follows null geodesics\n[Claim · Foundational]"]
    C003["C-003\n1.75 arcsec solar limb deflection\n[Claim · Derived · Numerical]"]
    AN001["AN-001\neddington_sobral_1919.py\n[Analysis]"]
    IG001["IG-001\nSobral 1919 expedition\n[IndependenceGroup]"]
    P001["P-001\npredict 1.75 arcsec deflection\n[Prediction · FULLY_SPECIFIED]"]

    T001 -->|"related_claims"| C001
    T001 -->|"related_claims"| C002
    C001 -->|"depends_on"| C003
    C002 -->|"depends_on"| C003
    A001 -->|"used_in_claims"| C003
    A002 -->|"used_in_claims"| C003
    PAR001 -->|"used_in_analyses"| AN001
    AN001 -->|"claims_covered"| C003
    C001 & C002 & C003 -->|"claim_ids"| P001
    P001 -->|"tests_assumptions"| A001
    P001 -.->|"conditional_on"| A002
    P001 -->|"independence_group"| IG001
    IG001 -.->|"member_predictions"| P001

    style PAR001 fill:#ffd700
    style A001 fill:#ffa07a,stroke:#cd6600,stroke-width:2px
    style A002 fill:#ffa07a
    style T001 fill:#b0c4de,stroke:#4682b4
    style C001 fill:#90ee90
    style C002 fill:#90ee90
    style C003 fill:#c8e6c9,stroke:#388e3c,stroke-width:2px
    style AN001 fill:#87ceeb
    style IG001 fill:#e0e0ff
    style P001 fill:#dda0dd,stroke:#8b008b
```

```mermaid
graph LR
classDef bigText font-size:18px;
    LP[" Parameter "] ~~~ LA[" Assumption "] ~~~ LT[" Theory "] ~~~ LAN[" Analysis "] ~~~ LCF[" Foundational Claim "] ~~~ LCD[" Derived Claim "] ~~~ LPR[" Prediction "] ~~~ LIG[" Independence Group "]:::bigText
    style LP  fill:#ffd700,stroke:#b8860b
    style LA  fill:#ffa07a,stroke:#cd6600
    style LT  fill:#b0c4de,stroke:#4682b4
    style LAN fill:#87ceeb,stroke:#1e90ff
    style LCF fill:#90ee90,stroke:#228b22
    style LCD fill:#c8e6c9,stroke:#388e3c
    style LPR fill:#dda0dd,stroke:#8b008b
    style LIG fill:#e0e0ff,stroke:#6666cc
```

**Transition to CONFIRMED after the Sobral plates are measured.**

```python
# Record observed value.
gateway.set("prediction", "P-001", {
    # ... same fields as above, plus:
    "observed":  1.98,     # Sobral astrographic result (arcsec); within the error bars of 1.75
    "status":    "PENDING",
    # ... all other fields unchanged
})
# → ok

gateway.transition("prediction", "P-001", "CONFIRMED")
# → ok | P-001 → CONFIRMED

# Link the theory to its supporting entities.
gateway.set("theory", "T-001", {
    "id":                  "T-001",
    "title":               "General Relativity",
    "status":              "active",
    "summary":             "...",
    "related_claims":      ["C-001", "C-002", "C-003"],
    "related_predictions": ["P-001"],
    "source":              "Einstein 1915",
})
# → ok

# Register the discovery.
gateway.register("discovery", {
    "id":       "D-001",
    "title":    "First experimental confirmation of GR light bending",
    "date":     "1919-11-06",       # date of Royal Society announcement
    "summary":  "Sobral eclipse expedition measured a mean stellar deflection consistent "
                "with the GR prediction of 1.75 arcsec and inconsistent with the "
                "Newtonian prediction of 0.875 arcsec.",
    "impact":   "First direct observational test of general relativity beyond the "
                "solar system; established GR as the correct theory of gravity at "
                "macroscopic scales.",
    "status":   "integrated",
    "related_claims":      ["C-001", "C-002", "C-003"],
    "related_predictions": ["P-001"],
    "source":   "Dyson, Eddington, Davidson 1920 MNRAS",
})
# → ok
```

**What the queries reveal:**

```python
gateway.query("claim_lineage", cid="C-003")
# {"lineage": {"C-001", "C-002"}}
# C-003 rests on two foundational claims — both must hold.

gateway.query("assumption_lineage", cid="C-003")
# {"lineage": {"A-001", "A-002"}}
# C-003 takes both assumptions as given.

gateway.query("prediction_implicit_assumptions", pid="P-001")
# {"implicit_assumptions": {"A-001", "A-002"}}
# P-001 explicitly lists A-001 in tests_assumptions and A-002 in conditional_on.
# Both are surfaced here as the full implicit assumption set.

gateway.query("refutation_impact", pid="P-001")
# {
#   "claim_ids":             {"C-001", "C-002", "C-003"},
#   "claim_ancestors":       {"C-001", "C-002"},    # ancestors of C-003 (C-001 and C-002 are foundational)
#   "implicit_assumptions":  {"A-001", "A-002"},
# }
# If P-001 were refuted, ALL THREE claims and BOTH assumptions would be called into question.
```

**Conclusion chain — how the epistemic path leads to confirmation:**

```mermaid
graph TD
classDef bigText font-size:18px;
    GR["T-001: General Relativity\nEinstein 1915\ngravity = spacetime curvature"]:::bigText
    C1["C-001\ngravity curves spacetime\n[Foundational]"]
    C2["C-002\nlight follows null geodesics\n[Foundational]"]
    C3["C-003\n1.75 arcsec deflection at solar limb\n[Derived — mathematically computed\nfrom C-001 + C-002]"]
    P001["P-001  FULLY_SPECIFIED  free_params=0\npredict 1.75 arcsec deflection\nNOVEL_PREDICTION: made 1915, measured 1919"]:::bigText
    A001["A-001\nplate accuracy ±0.3 arcsec\n[Empirical — tested by P-001]"]
    A002["A-002\nref. stars stable\n[Methodological — P-001 conditional on this]"]
    OBS["Sobral, 29 May 1919\nobserved = 1.98 arcsec\n(within error bars of 1.75 arcsec)"]:::bigText
    OUT["✅ CONFIRMED\nGR prediction validated\nNewtonian prediction (0.875 arcsec) excluded\nD-001 Discovery registered"]:::bigText

    GR --> C1 & C2
    C1 & C2 -->|"derive"| C3
    C3 -->|"quantified by PAR-001"| P001
    A001 -->|"tested by P-001"| P001
    A002 -.->|"P-001 conditional on"| P001
    P001 -->|"compared against"| OBS
    OBS --> OUT

    style GR fill:#b0c4de
    style C1 fill:#90ee90
    style C2 fill:#90ee90
    style C3 fill:#c8e6c9,stroke:#388e3c,stroke-width:2px
    style A001 fill:#ffa07a,stroke:#228b22,stroke-width:2px
    style A002 fill:#ffa07a
    style P001 fill:#dda0dd,stroke:#8b008b,stroke-width:2px
    style OBS fill:#fff0f0,stroke:#ff6666
    style OUT fill:#e8ffe8,stroke:#228b22,stroke-width:2px
```

```mermaid
graph LR
classDef bigText font-size:18px;
    LT[" Theory "] ~~~ LCF[" Foundational Claim "] ~~~ LCD[" Derived Claim "] ~~~ LA[" Assumption "] ~~~ LPR[" Prediction "] ~~~ LOBS[" Observation "] ~~~ LOUT[" Confirmed outcome "]:::bigText
    style LT   fill:#b0c4de,stroke:#4682b4
    style LCF  fill:#90ee90,stroke:#228b22
    style LCD  fill:#c8e6c9,stroke:#388e3c
    style LA   fill:#ffa07a,stroke:#cd6600
    style LPR  fill:#dda0dd,stroke:#8b008b
    style LOBS fill:#fff0f0,stroke:#ff6666
    style LOUT fill:#e8ffe8,stroke:#228b22,stroke-width:2px
```

**Note on the second expedition (Principe):** Eddington's Principe expedition also measured the deflection but with lower precision. It forms a natural second independence group `IG-002`. Using the registration order from Section 2.3: register IG-001 and IG-002 (both empty), then register a `PairwiseSeparation` documenting why the two sites are independent (different telescopes, different locations, different observers), then add predictions to each group. The full two-site chain models cleanly.

---

### 3.2 — Michelson-Morley 1887: A Null Result That Broke an Assumption

**Context:** In 1887, Michelson and Morley used an interferometer to test whether the luminiferous ether — the hypothetical medium through which light was thought to propagate — was detectable through Earth's orbital motion. The experiment found no fringe shift. This null result falsified the prediction that ether wind would be detectable, placed the ether assumption under severe pressure, and ultimately contributed to the development of special relativity.

This example shows: a prediction that `tests_assumptions`, a `REFUTED` transition, the full `refutation_impact` and `assumption_support_status` traversals, and a `DeadEnd` registration documenting what was abandoned.

```python
# --- Parameters ---

gateway.register("parameter", {
    "id":     "PAR-001",
    "name":   "expected_fringe_shift",
    "value":  0.4,
    "unit":   "fringes",
    "source": "Michelson 1881 theoretical calculation",
    "notes":  "Expected shift at Earth orbital velocity ~30 km/s, arm length 11m, "
              "wavelength 590nm. Full calculation: 2vL/λc² ≈ 0.4 fringes.",
})
# → ok

# --- Assumptions ---

gateway.register("assumption", {
    "id":                      "A-001",
    "statement":               "Luminiferous ether exists as an absolute rest frame "
                               "through which electromagnetic radiation propagates.",
    "type":                    "E",                  # EMPIRICAL — central hypothesis under test
    "scope":                   "Electrodynamics, 1887",
    "falsifiable_consequence": "If ether exists, Earth's orbital velocity (~30 km/s) "
                               "would produce a detectable fringe shift of approximately "
                               "0.4 fringes in an 11-metre arm interferometer.",
    "source":                  "Maxwell 1878; Michelson 1881",
})
# → ok

gateway.register("assumption", {
    "id":       "A-002",
    "statement": "The interferometer apparatus does not drag ether locally (no ether drag).",
    "type":     "E",
    "scope":    "Michelson-Morley apparatus, 1887",
    "falsifiable_consequence": "Fresnel drag coefficient measurements with moving media "
                               "would reveal partial ether drag if present.",
    "source":   "Stokes 1845 ether drag theory (no drag variant)",
})
# → ok

# --- Claims ---

gateway.register("claim", {
    "id":            "C-001",
    "statement":     "Light requires a medium (ether) to propagate, and its speed is "
                     "measured relative to that medium.",
    "type":          "foundational",
    "scope":         "Classical wave mechanics of light",
    "falsifiability": "Detection of a constant speed of light in all inertial frames "
                      "would falsify the ether medium requirement.",
    "category":      "qualitative",
    "assumptions":   ["A-001"],
})
# → ok | A-001.used_in_claims → {C-001}

gateway.register("claim", {
    "id":            "C-002",
    "statement":     "Earth's orbital motion at ~30 km/s relative to the ether "
                     "produces a measurable ether wind detectable by interferometry.",
    "type":          "derived",
    "scope":         "Earth-based interferometry, 1887",
    "falsifiability": "An interferometer with sufficient sensitivity showing no fringe "
                      "shift through a full rotation would falsify ether wind detectability.",
    "category":      "numerical",
    "depends_on":    ["C-001"],
    "assumptions":   ["A-001", "A-002"],
    "parameter_constraints": {"PAR-001": "~= 0.4"},
})
# → ok | A-001.used_in_claims → {C-001, C-002}, A-002.used_in_claims → {C-002}

# --- Analysis ---

gateway.register("parameter", {
    "id":     "PAR-002",
    "name":   "interferometer_sensitivity",
    "value":  0.01,
    "unit":   "fringes",
    "notes":  "Minimum detectable fringe shift. Expected signal (0.4) is 40× the "
              "noise floor — sensitivity is not the limiting factor.",
})
# → ok

gateway.register("analysis", {
    "id":              "AN-001",
    "path":            "analyses/mm_interferometer_1887.py",
    "command":         "python mm_interferometer_1887.py --observations 36 --rotations full",
    "uses_parameters": ["PAR-001", "PAR-002"],
    "notes":           "36 observations over July 8-12 1887. "
                       "Interferometer on stone slab floating in mercury to allow full rotation. "
                       "Mean fringe shift measured: 0.01 fringes.",
})
# → ok

gateway.set("claim", "C-002", {
    # ... same as above with:
    "analyses": ["AN-001"],
})
# → ok | AN-001.claims_covered → {C-002}

# --- Independence group and prediction ---

gateway.register("independence_group", {
    "id":               "IG-001",
    "label":            "Michelson-Morley interferometer, Case Western Reserve, July 1887",
    "claim_lineage":    ["C-001", "C-002"],
    "assumption_lineage": ["A-001", "A-002"],
    "measurement_regime": "measured",
})
# → ok

gateway.register("prediction", {
    "id":               "P-001",
    "observable":       "Fringe shift in Michelson interferometer during full rotation "
                        "of the apparatus",
    "tier":             "fully_specified",
    "status":           "PENDING",
    "evidence_kind":    "novel_prediction",
    "measurement_regime": "measured",
    "predicted":        0.4,
    "specification":    "Fringe shift amplitude ≈ 0.4 fringes across a full rotation, "
                        "peaking when one arm is aligned with Earth's orbital velocity vector",
    "derivation":       "C-001 requires light speed to depend on ether frame velocity. "
                        "C-002 quantifies the ether wind at Earth's orbital velocity. "
                        "Together they predict a specific and measurable fringe pattern.",
    "claim_ids":        ["C-001", "C-002"],
    "tests_assumptions": ["A-001", "A-002"],   # this prediction directly tests both
    "independence_group": "IG-001",
    "analysis":         "AN-001",
    "free_params":      0,
    "falsifier":        "Fringe shift < 0.02 fringes through a full rotation would be "
                        "inconsistent with ether wind at any Earth orbital phase.",
    "source":           "Michelson and Morley 1887 Am. J. Sci.",
})
# → ok
# A-001.tested_by → {P-001}, A-002.tested_by → {P-001}
```

**Full entity graph (before the measurement):**

```mermaid
graph TD
classDef bigText font-size:18px;
    PAR001["PAR-001\nexpected_fringe_shift = 0.4\n[Parameter]"]
    PAR002["PAR-002\nsensitivity = 0.01 fringes\n[Parameter]"]
    A001["A-001\nEther exists as absolute rest frame\n[Assumption · Empirical  ← central hypothesis]"]
    A002["A-002\nNo local ether drag on apparatus\n[Assumption · Empirical]"]
    C001["C-001\nLight speed is relative to ether\n[Claim · Foundational]"]
    C002["C-002\nEarth's motion → detectable ether wind\n[Claim · Derived · Numerical]"]
    AN001["AN-001\nmm_interferometer_1887.py\n[Analysis · 36 observations]"]
    IG001["IG-001\nMichelson-Morley apparatus  July 1887\n[IndependenceGroup]"]
    P001["P-001\npredict 0.4 fringe shift\n[Prediction · FULLY_SPECIFIED · NOVEL]"]

    PAR001 -->|"used_in_analyses"| AN001
    PAR002 -->|"used_in_analyses"| AN001
    A001 -->|"used_in_claims"| C001
    A001 -->|"used_in_claims"| C002
    A002 -->|"used_in_claims"| C002
    C001 -->|"depends_on"| C002
    AN001 -->|"claims_covered"| C002
    C001 & C002 -->|"claim_ids"| P001
    P001 -->|"tests_assumptions"| A001
    P001 -->|"tests_assumptions"| A002
    P001 -->|"independence_group"| IG001

    style PAR001 fill:#ffd700
    style PAR002 fill:#ffd700
    style A001 fill:#ffa07a,stroke:#cc3300,stroke-width:2px
    style A002 fill:#ffa07a
    style C001 fill:#90ee90
    style C002 fill:#90ee90
    style AN001 fill:#87ceeb
    style IG001 fill:#e0e0ff
    style P001 fill:#dda0dd,stroke:#8b008b
```

```mermaid
graph LR
classDef bigText font-size:18px;
    LP[" Parameter "] ~~~ LAH[" Assumption: central hypothesis "] ~~~ LA[" Assumption "] ~~~ LAN[" Analysis "] ~~~ LC[" Claim "] ~~~ LPR[" Prediction "] ~~~ LIG[" Independence Group "]:::bigText
    style LP  fill:#ffd700,stroke:#b8860b
    style LAH fill:#ffa07a,stroke:#cc3300,stroke-width:2px
    style LA  fill:#ffa07a,stroke:#cd6600
    style LAN fill:#87ceeb,stroke:#1e90ff
    style LC  fill:#90ee90,stroke:#228b22
    style LPR fill:#dda0dd,stroke:#8b008b
    style LIG fill:#e0e0ff,stroke:#6666cc
```

**The measurement returns 0.01 fringes. The prediction is refuted.**

```python
# Record the observed value.
gateway.set("prediction", "P-001", {
    # ... same as above with:
    "observed": 0.01,    # measured; expected 0.4
    "status":   "PENDING",
})
# → ok

# Transition to STRESSED first — the result is anomalous but perhaps not conclusive alone.
gateway.transition("prediction", "P-001", "STRESSED")
# → ok | P-001 → STRESSED

# After replication and analysis, transition to REFUTED.
gateway.transition("prediction", "P-001", "REFUTED")
# → ok | P-001 → REFUTED
# Validator: validate_evidence_consistency checks that REFUTED predictions have an analysis.
# P-001.analysis = "AN-001" — satisfied.
```

**Query the consequences.**

```python
gateway.query("refutation_impact", pid="P-001")
# {
#   "claim_ids":            {"C-001", "C-002"},
#   "claim_ancestors":      {"C-001"},              # C-002 depends_on C-001
#   "implicit_assumptions": {"A-001", "A-002"},     # both assumptions are in the chain
# }
# The refutation of P-001 calls into question both claims and both assumptions.

gateway.query("assumption_support_status", aid="A-001")
# {
#   "direct_claims":         {"C-001", "C-002"},    # both claims reference A-001
#   "dependent_predictions": {"P-001"},             # P-001's chain includes A-001
#   "tested_by":             {"P-001"},             # P-001 was explicitly testing A-001
# }
# A-001 is now under direct pressure: the prediction that was testing it has been refuted.

gateway.query("assumption_support_status", aid="A-002")
# {
#   "direct_claims":         {"C-002"},
#   "dependent_predictions": {"P-001"},
#   "tested_by":             {"P-001"},
# }
```

**Refutation impact — what the queries surface:**

```mermaid
graph TD
classDef bigText font-size:18px;
    P001["P-001 → ❌ REFUTED\nobserved = 0.01 fringes\nexpected = 0.4 fringes  (40× above noise floor)"]:::bigText

    subgraph ri["refutation_impact(P-001)"]:::bigText
        C001["C-001  ⚠️ called into question\nLight requires ether medium"]:::bigText
        C002["C-002  ⚠️ called into question\nDetectable ether wind  [ancestor: C-001]"]
        A001["A-001  ⚠️ DIRECT PRESSURE\ntested_by = {P-001 — REFUTED}\nEther as absolute rest frame"]:::bigText
        A002["A-002  ⚠️ DIRECT PRESSURE\ntested_by = {P-001 — REFUTED}\nNo local ether drag"]:::bigText
    end

    DE001["DE-001\nLuminiferous ether abandoned\n[DeadEnd · resolved]"]

    P001 -->|"claim_ids"| C001
    P001 -->|"claim_ids"| C002
    P001 -->|"tests_assumptions"| A001
    P001 -->|"tests_assumptions"| A002
    A001 -.->|"concept abandoned → "| DE001

    NOTE["The web surfaces these connections.\nIt does NOT automatically retract C-001/C-002\nor mark A-001 false.\nResearcher judgment required."]:::bigText

    style P001 fill:#ffcccc,stroke:#cc0000,stroke-width:2px
    style C001 fill:#ffe0b2,stroke:#e65100
    style C002 fill:#ffe0b2,stroke:#e65100
    style A001 fill:#ff9966,stroke:#cc3300,stroke-width:2px
    style A002 fill:#ff9966,stroke:#cc3300
    style DE001 fill:#ffe4e4,stroke:#cc0000
    style NOTE fill:#f5f5f5,stroke:#999,stroke-dasharray:4
```

```mermaid
graph LR
classDef bigText font-size:18px;
    LREF[" Refuted prediction "] ~~~ LCQ[" Claim under question "] ~~~ LAP[" Assumption under pressure "] ~~~ LDE[" Dead end "] ~~~ LN[" Note "]:::bigText
    style LREF fill:#ffcccc,stroke:#cc0000,stroke-width:2px
    style LCQ  fill:#ffe0b2,stroke:#e65100
    style LAP  fill:#ff9966,stroke:#cc3300,stroke-width:2px
    style LDE  fill:#ffe4e4,stroke:#cc0000
    style LN   fill:#f5f5f5,stroke:#999,stroke-dasharray:4
```

**Conclusion chain — how null result leads to paradigm shift:**

```mermaid
graph TD
classDef bigText font-size:18px;
    A001["A-001\nEther exists as absolute rest frame\n[Empirical assumption — the central hypothesis]"]
    A002["A-002\nNo local ether drag\n[Empirical — structural control]"]
    C001["C-001\nLight speed is relative to ether\n[Foundational claim]"]
    C002["C-002\nEarth's orbital velocity → 0.4 fringe shift\n[Derived — PAR-001 = 0.4 fringes]"]
    P001["P-001  FULLY_SPECIFIED  free_params=0\npredict 0.4 fringe shift across full rotation"]:::bigText
    OBS["Measurement\nCase Western Reserve, July 8-12 1887\nobserved = 0.01 fringes\n(apparatus sensitivity = 0.01 — at the noise floor)"]:::bigText
    REFUTED["❌ REFUTED\nNull result: fringe shift is 40× below prediction\nP-001 → STRESSED → REFUTED"]:::bigText
    AFTERMATH["A-001 tested_by = {P-001 — REFUTED}\nA-002 tested_by = {P-001 — REFUTED}\nC-001, C-002 called into question\nDE-001 registered — ether hypothesis abandoned\n→ Einstein 1905: special relativity, no ether needed"]:::bigText

    A001 -->|"grounds"| C001
    A001 & A002 -->|"underpins"| C002
    C001 -->|"depends_on"| C002
    C002 -->|"grounds"| P001
    P001 -->|"compared against"| OBS
    OBS --> REFUTED
    REFUTED --> AFTERMATH

    style A001 fill:#ffa07a,stroke:#cc3300,stroke-width:2px
    style A002 fill:#ffa07a
    style C001 fill:#90ee90
    style C002 fill:#90ee90
    style P001 fill:#dda0dd,stroke:#8b008b
    style OBS fill:#fff0f0,stroke:#ff6666
    style REFUTED fill:#ffcccc,stroke:#cc0000,stroke-width:2px
    style AFTERMATH fill:#f0f0ff,stroke:#6666cc,stroke-width:2px
```

```mermaid
graph LR
classDef bigText font-size:18px;
    LA[" Assumption "] ~~~ LC[" Claim "] ~~~ LPR[" Prediction "] ~~~ LOBS[" Observation "] ~~~ LREF[" Refuted outcome "] ~~~ LAFT[" Aftermath / paradigm shift "]:::bigText
    style LA   fill:#ffa07a,stroke:#cd6600
    style LC   fill:#90ee90,stroke:#228b22
    style LPR  fill:#dda0dd,stroke:#8b008b
    style LOBS fill:#fff0f0,stroke:#ff6666
    style LREF fill:#ffcccc,stroke:#cc0000,stroke-width:2px
    style LAFT fill:#f0f0ff,stroke:#6666cc
```

**The researcher records the ether hypothesis as a dead end.**

```python
gateway.register("dead_end", {
    "id":          "DE-001",
    "title":       "Luminiferous ether as absolute rest frame",
    "description": "The Michelson-Morley experiment showed no detectable fringe shift "
                   "at 40× the apparatus sensitivity floor. Subsequent repetitions "
                   "(Morley and Miller 1902-1905, Miller 1925) produced similarly null "
                   "results. Attempts to salvage the ether via partial drag (Stokes) or "
                   "Lorentz contraction could not reconcile the full set of observations. "
                   "The concept was abandoned following Einstein's 1905 special relativity "
                   "paper, which explained all results without requiring an ether.",
    "status":      "resolved",
    "related_predictions": ["P-001"],
    "related_claims":      ["C-001", "C-002"],
    "references":  [
        "Michelson and Morley 1887 Am. J. Sci. 34:333",
        "Einstein 1905 Ann. Phys. 17:891",
    ],
})
# → ok
```

**What the web now shows — a complete epistemic record:**

The web records that:
- P-001 is REFUTED and was testing A-001 and A-002.
- A-001 is an empirical assumption with a known falsifiable consequence and has been tested — adversely.
- C-001 and C-002 have a refuted prediction in their derivation chain.
- DE-001 documents what was tried and why it was abandoned.

No inference has been drawn automatically. The web does not mark A-001 as "false" or C-001 as "retracted." That judgment belongs to the researcher. The web surfaces the structural consequences and waits.

---

### 3.3 — Fraud Detection Model: Parameter Drift and Compound Assumptions

**Context:** A machine learning team builds a fraud detection classifier. Two months after deployment, the data science team changes two parameters: a precision threshold (for business reporting) and the train-test split ratio (for model governance). One change is benign; the other makes an already-confirmed prediction suspect.

This example shows: a CONDITIONAL prediction (depends on distributional assumptions), a parameter update that stales an analysis, and the distinction between a prediction that is still structurally "CONFIRMED" but whose analytical basis is now stale.

```python
# --- Parameters ---

gateway.register("parameter", {
    "id":    "PAR-001",
    "name":  "test_split_ratio",
    "value": 0.20,
    "unit":  None,
    "notes": "Fraction of historical data held out as test set. Temporal split: "
             "most recent 20% of transactions.",
})
# → ok

gateway.register("parameter", {
    "id":    "PAR-002",
    "name":  "minimum_precision_threshold",
    "value": 0.85,
    "unit":  None,
    "notes": "Minimum acceptable precision for fraud alerts. Business requirement: "
             "false positive rate must stay below 15% of all alerts.",
})
# → ok

# --- Assumptions ---

gateway.register("assumption", {
    "id":                      "A-001",
    "statement":               "The statistical distribution of fraudulent transaction "
                               "patterns in the training period is representative of "
                               "the distribution during deployment.",
    "type":                    "E",               # EMPIRICAL
    "scope":                   "FraudNet v1.0, training window Jan–Dec 2023",
    "falsifiable_consequence": "A significant drop in model precision or recall on "
                               "fresh deployment data — not explained by volume changes "
                               "— would indicate distributional shift.",
})
# → ok

gateway.register("assumption", {
    "id":       "A-002",
    "statement": "The temporal 80/20 train-test split provides a stable and unbiased "
                 "estimate of out-of-sample performance.",
    "type":     "M",                # METHODOLOGICAL
    "scope":    "FraudNet v1.0 evaluation",
    "notes":    "Temporal split was chosen over random split to respect the sequential "
                "nature of fraud patterns.",
})
# → ok

# --- Claims ---

gateway.register("claim", {
    "id":            "C-001",
    "statement":     "FraudNet v1.0 has learned genuine fraud-indicative patterns "
                     "from the labeled training data.",
    "type":          "foundational",
    "scope":         "FraudNet v1.0, training window Jan–Dec 2023",
    "falsifiability": "Precision and recall significantly above a random baseline on "
                      "the held-out test set would confirm learning; at or below baseline "
                      "would falsify.",
    "category":      "qualitative",
    "assumptions":   ["A-001"],
})
# → ok

gateway.register("claim", {
    "id":            "C-002",
    "statement":     "The patterns learned by FraudNet v1.0 generalise to unseen "
                     "transactions at precision ≥ 0.85.",
    "type":          "derived",
    "scope":         "FraudNet v1.0, temporal test set from deployment window",
    "falsifiability": "Observed precision < 0.85 on the held-out test set would falsify.",
    "category":      "numerical",
    "depends_on":    ["C-001"],
    "assumptions":   ["A-001", "A-002"],
    "parameter_constraints": {"PAR-002": ">= 0.85"},   # claim threshold references PAR-002
})
# → ok

# --- Analysis ---

gateway.register("analysis", {
    "id":              "AN-001",
    "path":            "analyses/model_evaluation.py",
    "command":         "python model_evaluation.py --split 0.20 --threshold 0.85",
    "uses_parameters": ["PAR-001", "PAR-002"],
    "notes":           "Sklearn classification_report on temporal test split. "
                       "Result: precision=0.91, recall=0.78, f1=0.84.",
})
# → ok | PAR-001.used_in_analyses → {AN-001}, PAR-002.used_in_analyses → {AN-001}

gateway.set("claim", "C-002", {
    # ... same as above with:
    "analyses": ["AN-001"],
})
# → ok | AN-001.claims_covered → {C-002}

# --- Independence group and prediction ---

gateway.register("independence_group", {
    "id":    "IG-001",
    "label": "FraudNet v1.0 temporal test split evaluation",
    "claim_lineage":    ["C-001", "C-002"],
    "assumption_lineage": ["A-001", "A-002"],
    "measurement_regime": "measured",
})
# → ok

gateway.register("prediction", {
    "id":               "P-001",
    "observable":       "FraudNet v1.0 precision on temporal hold-out test set",
    "tier":             "conditional",          # CONDITIONAL — depends on distributional assumption
    "status":           "PENDING",
    "evidence_kind":    "novel_prediction",
    "measurement_regime": "measured",
    "predicted":        0.88,
    "specification":    "Precision ≥ 0.85 on the temporal test split (most recent 20% of data)",
    "derivation":       "C-001 asserts that genuine patterns were learned. C-002 asserts "
                        "those patterns generalise at ≥ 0.85 precision. Both require A-001 "
                        "to hold — if distribution has shifted, generalization may not hold.",
    "claim_ids":        ["C-001", "C-002"],
    "conditional_on":   ["A-001", "A-002"],     # prediction only valid if distribution is stable
    "tests_assumptions": [],                    # not explicitly designed to test distribution
    "independence_group": "IG-001",
    "analysis":         "AN-001",
    "free_params":      0,
    "falsifier":        "Precision < 0.85 on the test set.",
})
# → ok
# Validator: CONDITIONAL prediction must have conditional_on — it does. ok.
```

**Full entity graph (after initial registration, before any parameter changes):**

```mermaid
graph TD
classDef bigText font-size:18px;
    PAR001["PAR-001\ntest_split_ratio = 0.20\n[Parameter]"]
    PAR002["PAR-002\nmin_precision_threshold = 0.85\n[Parameter]"]
    A001["A-001\nDistribution stable: train ≈ deploy\n[Assumption · Empirical]\nfalsifiable_consequence: ✓  tested_by: ∅ ← gap"]
    A002["A-002\nTemporal split is unbiased\n[Assumption · Methodological]"]
    C001["C-001\nFraudNet learned genuine patterns\n[Claim · Foundational]"]
    C002["C-002\nPatterns generalise at precision ≥ 0.85\n[Claim · Derived · Numerical]"]
    AN001["AN-001\nmodel_evaluation.py\n--split 0.20 --threshold 0.85\n[Analysis]"]
    IG001["IG-001\nFraudNet v1.0 temporal split eval\n[IndependenceGroup]"]
    P001["P-001\npredict precision ≥ 0.85\n[Prediction · CONDITIONAL]"]

    PAR001 -->|"used_in_analyses"| AN001
    PAR002 -->|"used_in_analyses"| AN001
    A001 -->|"used_in_claims"| C001
    A001 & A002 -->|"used_in_claims"| C002
    C001 -->|"depends_on"| C002
    AN001 -->|"claims_covered"| C002
    C001 & C002 -->|"claim_ids"| P001
    P001 -.->|"conditional_on"| A001
    P001 -.->|"conditional_on"| A002
    P001 -->|"independence_group"| IG001
    PAR002 -.->|"parameter_constraints ≥ 0.85"| C002

    style PAR001 fill:#ffd700
    style PAR002 fill:#ffd700
    style A001 fill:#ffa07a,stroke:#cc3300,stroke-width:2px
    style A002 fill:#ffa07a
    style C001 fill:#90ee90
    style C002 fill:#c8e6c9,stroke:#388e3c
    style AN001 fill:#87ceeb
    style IG001 fill:#e0e0ff
    style P001 fill:#dda0dd,stroke:#8b008b
```

```mermaid
graph LR
classDef bigText font-size:18px;
    LP[" Parameter "] ~~~ LAR[" Assumption: unmonitored risk "] ~~~ LA[" Assumption "] ~~~ LAN[" Analysis "] ~~~ LCF[" Foundational Claim "] ~~~ LCD[" Derived Claim "] ~~~ LPR[" Prediction "] ~~~ LIG[" Independence Group "]:::bigText
    style LP  fill:#ffd700,stroke:#b8860b
    style LAR fill:#ffa07a,stroke:#cc3300,stroke-width:2px
    style LA  fill:#ffa07a,stroke:#cd6600
    style LAN fill:#87ceeb,stroke:#1e90ff
    style LCF fill:#90ee90,stroke:#228b22
    style LCD fill:#c8e6c9,stroke:#388e3c
    style LPR fill:#dda0dd,stroke:#8b008b
    style LIG fill:#e0e0ff,stroke:#6666cc
```

**Evaluation runs. Precision = 0.91. Prediction confirmed.**

```python
gateway.set("prediction", "P-001", {
    # ... same as above with:
    "observed": 0.91,
    "status":   "PENDING",
})
# → ok

gateway.transition("prediction", "P-001", "CONFIRMED")
# → ok | P-001 → CONFIRMED
```

**Two months later — regulatory governance change 1: precision threshold raised to 0.90.**

```python
gateway.set("parameter", "PAR-002", {
    "id":    "PAR-002",
    "name":  "minimum_precision_threshold",
    "value": 0.90,
    "unit":  None,
    "notes": "Raised from 0.85 to 0.90 per Q4 governance review. "
             "Regulatory guidance requires false positive rate below 10%.",
})
# → ok | PAR-002 updated

gateway.query("parameter_impact", pid="PAR-002")
# {
#   "stale_analyses":       {"AN-001"},
#   "constrained_claims":   {"C-002"},       # C-002 has parameter_constraints on PAR-002
#   "affected_claims":      {"C-002"},
#   "affected_predictions": {"P-001"},
# }
```

**This change is benign for the current result.** P-001.observed = 0.91 > 0.90, so the prediction still passes the new threshold. But C-002's `parameter_constraints` entry says `{"PAR-002": ">= 0.85"}` — this annotation is now stale. The researcher updates C-002's constraint to reflect the new threshold:

```python
gateway.set("claim", "C-002", {
    # ... same as above with:
    "parameter_constraints": {"PAR-002": ">= 0.90"},   # updated
})
# → ok
```

**Regulatory governance change 2: test split ratio changed from 0.20 to 0.30.**

```python
gateway.set("parameter", "PAR-001", {
    "id":    "PAR-001",
    "name":  "test_split_ratio",
    "value": 0.30,
    "unit":  None,
    "notes": "Increased from 0.20 to 0.30. Larger test window provides more stable "
             "precision estimates and includes Q3 seasonality in evaluation.",
})
# → ok

gateway.query("parameter_impact", pid="PAR-001")
# {
#   "stale_analyses":       {"AN-001"},       # AN-001 was run with --split 0.20
#   "constrained_claims":   set(),            # no claims annotate PAR-001 constraints
#   "affected_claims":      {"C-002"},        # C-002 is covered by the now-stale AN-001
#   "affected_predictions": {"P-001"},        # P-001 depends on C-002
# }
```

**This change is NOT benign.** `AN-001` was run with `--split 0.20`. The split is now 0.30. The test set has changed. The observed precision of 0.91 was measured on the 20% holdout, not the 30% holdout. P-001 is CONFIRMED based on a result produced under different parameters.

**The web does not automatically change P-001.status.** The CONFIRMED status remains. But the staleness signal is visible to anyone querying `parameter_impact`. The researcher must:

```python
# 1. Re-run AN-001 with the new split.
#    (ds record, once implemented, would capture the new result here.)

# 2. Suppose the new result returns precision = 0.87 (Q3 has seasonal fraud patterns
#    that weren't in the training window — A-001 is showing signs of strain).

# 3. Update the observed value.
gateway.set("prediction", "P-001", {
    # ... same fields as above with:
    "observed": 0.87,    # new result under 0.30 split
    "status":   "CONFIRMED",
})
# → ok

# 4. 0.87 > 0.90? No. Precision has dropped below the new threshold.
#    Transition to STRESSED — the evidence is under tension but not decisively refuted.
gateway.transition("prediction", "P-001", "STRESSED")
# → ok | P-001 → STRESSED
# Validator: validate_coverage will surface STRESSED predictions in its findings.
# This is a WARNING, not a CRITICAL — it calls for review, not a block.
```

**Two-parameter cascade diagram — which change is benign and which is not:**

```mermaid
graph LR
classDef bigText font-size:18px;
    subgraph par2["PAR-002: precision threshold  0.85 → 0.90"]:::bigText
        direction TB
        PAR2["PAR-002 updated"]:::bigText
        AN1a["AN-001  ⚠️ stale"]:::bigText
        C2a["C-002  ⚠️ constrained\nannotation says '≥ 0.85'\n→ update to '≥ 0.90'"]:::bigText
        P1a["P-001\nobserved = 0.91 > 0.90  ✓\n→ still CONFIRMED"]:::bigText
        OK["✅ BENIGN\nCurrent result still passes\nUpdate C-002 annotation only"]:::bigText
        PAR2 --> AN1a --> C2a --> P1a --> OK
    end

    subgraph par1["PAR-001: test split ratio  0.20 → 0.30"]:::bigText
        direction TB
        PAR1["PAR-001 updated"]:::bigText
        AN1b["AN-001  ⚠️ stale\n(was run with --split 0.20)"]:::bigText
        C2b["C-002  ⚠️ affected"]:::bigText
        P1b["P-001  ⚠️ affected\nobserved=0.91 was on 0.20 split\n→ rerun with 0.30 → 0.87"]:::bigText
        STRESS["⚠️ NOT BENIGN\n0.87 < new threshold 0.90\nP-001 → STRESSED\nvalidate_coverage flags it"]:::bigText
        PAR1 --> AN1b --> C2b --> P1b --> STRESS
    end

    style PAR1 fill:#ff9999,stroke:#cc0000
    style PAR2 fill:#ffd700,stroke:#b8860b
    style AN1a fill:#ffcccc
    style AN1b fill:#ffcccc
    style C2a fill:#ffe0b2
    style C2b fill:#ffe0b2
    style P1a fill:#dda0dd
    style P1b fill:#dda0dd
    style OK fill:#e8ffe8,stroke:#228b22
    style STRESS fill:#fff3e0,stroke:#e65100,stroke-width:2px
```

```mermaid
graph LR
classDef bigText font-size:18px;
    LCP[" Changed parameter "] ~~~ LST[" Stale analysis "] ~~~ LAC[" Affected claim "] ~~~ LPR[" Affected prediction "] ~~~ LOK[" Benign — result still passes "] ~~~ LWN[" Warning — result now fails threshold "]:::bigText
    style LCP fill:#ff9999,stroke:#cc0000
    style LST fill:#ffcccc,stroke:#cc3333
    style LAC fill:#ffe0b2,stroke:#e65100
    style LPR fill:#dda0dd,stroke:#8b008b
    style LOK fill:#e8ffe8,stroke:#228b22
    style LWN fill:#fff3e0,stroke:#e65100,stroke-width:2px
```

**What the health check now shows:**

```python
gateway.query("health_check")
# findings = [
#   Finding(WARNING, "predictions/P-001",
#           "Prediction P-001 is STRESSED: observed precision 0.87 is below the "
#           "current threshold of 0.90. Review A-001 (distributional stability) "
#           "and consider whether a model retrain is warranted."),
#   Finding(INFO, "analyses/AN-001",
#           "AN-001 uses parameters PAR-001 (now 0.30) and PAR-002 (now 0.90). "
#           "Last recorded result was obtained under different parameter values."),
# ]

gateway.query("assumption_support_status", aid="A-001")
# {
#   "direct_claims":         {"C-001", "C-002"},
#   "dependent_predictions": {"P-001"},
#   "tested_by":             set(),     # nobody explicitly tests distribution stability
# }
# Note: A-001 (distributional stability) is an empirical assumption with a falsifiable
# consequence but NO prediction in tested_by. This means the team has identified the
# risk but has not set up a formal test for it.
# Validator: validate_assumption_testability will flag A-001 as WARNING.
```

**Full epistemic chain — from initial claim to stressed conclusion:**

```mermaid
graph TD
classDef bigText font-size:18px;
    A001["A-001\nDistribution stable: train ≈ deploy\n[Empirical · tested_by=∅  ← unmonitored risk]"]
    A002["A-002\nTemporal split is unbiased\n[Methodological]"]
    C001["C-001\nFraudNet learned genuine patterns"]:::bigText
    C002["C-002\nPatterns generalise at precision ≥ 0.85\n→ updated to ≥ 0.90 after PAR-002 change"]:::bigText
    P001_init["P-001  CONDITIONAL on A-001, A-002\npredict precision ≥ 0.85\nCONFIRMED  observed=0.91\n[based on split=0.20]"]
    PAR1["PAR-001\n0.20 → 0.30"]:::bigText
    RERUN["Re-run AN-001 with split=0.30\nnew observed = 0.87\n(Q3 seasonality not in training window)"]:::bigText
    P001_final["P-001 → STRESSED\n0.87 < threshold 0.90\nA-001 conditional basis showing strain"]:::bigText
    GAP["Structural gaps exposed:\n1. A-001 has falsifiable_consequence\n   but tested_by=∅\n   → validate_assumption_testability: WARNING\n2. P-001 is CONDITIONAL on A-001\n   but A-001 is never formally tested\n   → the risk was always there, now visible"]:::bigText

    A001 & A002 -->|"underpin"| C001 & C002
    C001 & C002 -->|"ground"| P001_init
    P001_init -->|"PAR-001 change triggers rerun"| PAR1
    PAR1 --> RERUN
    RERUN -->|"result drops below threshold"| P001_final
    P001_final -.->|"exposes"| GAP

    style A001 fill:#ffa07a,stroke:#cc3300,stroke-width:2px
    style A002 fill:#ffa07a
    style C001 fill:#90ee90
    style C002 fill:#c8e6c9
    style P001_init fill:#dda0dd
    style PAR1 fill:#ff9999,stroke:#cc0000
    style RERUN fill:#fff0f0,stroke:#ff6666
    style P001_final fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style GAP fill:#fff9c4,stroke:#f57f17,stroke-width:2px
```

```mermaid
graph LR
classDef bigText font-size:18px;
    LA[" Assumption "] ~~~ LC[" Claim "] ~~~ LPR[" Prediction "] ~~~ LCP[" Changed parameter "] ~~~ LOBS[" Rerun / observation "] ~~~ LST[" Stressed outcome "] ~~~ LGP[" Structural gap exposed "]:::bigText
    style LA   fill:#ffa07a,stroke:#cd6600
    style LC   fill:#90ee90,stroke:#228b22
    style LPR  fill:#dda0dd,stroke:#8b008b
    style LCP  fill:#ff9999,stroke:#cc0000,stroke-width:2px
    style LOBS fill:#fff0f0,stroke:#ff6666
    style LST  fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style LGP  fill:#fff9c4,stroke:#f57f17
```

**The web has revealed two structural gaps that pre-existed the parameter changes:**
1. A-001 has a `falsifiable_consequence` but no prediction in `tested_by`. The team never formally instrumented the distribution monitoring.
2. P-001 is CONDITIONAL on A-001 but A-001 is not being actively tested. The conditional dependency is a known risk that was never formally tracked.

These are not bugs introduced by the examples. They are real design gaps that the epistemic web makes visible.

---

## Summary: What These Examples Reveal

### Rules the gateway enforces that you cannot work around

| Situation | What happens |
|---|---|
| Register entity with reference to non-existent ID | `status="error"` immediately (web raises `BrokenReferenceError`) |
| Register claim with `depends_on` that creates a cycle | `status="error"` immediately |
| Register duplicate ID | `status="error"` immediately |
| Transition claim to RETRACTED while predictions still cite it | `status="BLOCKED"` (CRITICAL finding) |
| Prediction has same assumption in both `tests_assumptions` and `conditional_on` | `status="BLOCKED"` (CRITICAL finding) |
| `FULLY_SPECIFIED` prediction with `free_params != 0` | `status="BLOCKED"` (CRITICAL finding) |
| Both independence groups have member predictions but no pairwise separation exists | `status="BLOCKED"` (CRITICAL finding) |

### Things the gateway does NOT do automatically

| Situation | What you must do manually |
|---|---|
| Parameter value changes | Query `parameter_impact`, re-run affected analyses, record results, decide whether to transition prediction status |
| Prediction refuted | Query `refutation_impact` to see blast radius; decide whether to retract upstream claims |
| Assumption under pressure from a refuted prediction | Explicitly review the assumption; the web flags it, it does not change the assumption's status |
| Analysis re-run with new parameters | Record the new result; transition the prediction status if warranted |

