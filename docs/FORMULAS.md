# FleetWise — Mathematical Formulas & Heuristics Specification

This document formally specifies all mathematical formulas, heuristics, coordinate geometry models, and confidence algorithms implemented within FleetWise.

Every formula in this document is tested for mathematical accuracy and deterministic reproducibility via `tests/test_docs_formulas.py` and `scripts/formula_examples.py`.

---

## 1. Spherical Distance: Haversine Formulation

FleetWise uses the great-circle Haversine formula over the WGS-84 reference ellipsoid approximated as a sphere with mean volumetric radius $R = 6\,371\,000.0\text{ m}$.

### Formula
Given two points $P_1 = (\phi_1, \lambda_1)$ and $P_2 = (\phi_2, \lambda_2)$ in decimal degrees:

$$\Delta \phi = \operatorname{radians}(\phi_2 - \phi_1), \quad \Delta \lambda = \operatorname{radians}(\lambda_2 - \lambda_1)$$

$$a = \sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\operatorname{radians}(\phi_1)) \cdot \cos(\operatorname{radians}(\phi_2)) \cdot \sin^2\left(\frac{\Delta \lambda}{2}\right)$$

$$c = 2 \cdot \operatorname{atan2}\left(\sqrt{a}, \sqrt{1 - a}\right)$$

$$d = R \cdot c$$

### Worked Example (Bangalore Urban Corridor)
- **Point 1 (Cubbon Park)**: $\phi_1 = 12.9716^\circ\text{ N}, \ \lambda_1 = 77.5946^\circ\text{ E}$
- **Point 2 (Indiranagar)**: $\phi_2 = 12.9784^\circ\text{ N}, \ \lambda_2 = 77.6408^\circ\text{ E}$
- **Calculated Distance**:
  $$d = 5062.82\text{ meters} \quad (5.06\text{ km})$$

---

## 2. Step Kinematics & Velocity Estimation

Velocity between sequential GPS fixes is derived from the geodesic displacement and elapsed server/device time.

### Formula
$$\Delta t = t_2 - t_1 \quad (\text{seconds})$$

$$v_{\text{derived}} = \frac{d}{\Delta t} \quad (\text{m/s}), \qquad v_{\text{km/h}} = v_{\text{derived}} \times 3.6$$

### Worked Example
- For $d = 5062.82\text{ m}$ over $\Delta t = 240.0\text{ s}$:
  $$v_{\text{derived}} = \frac{5062.82}{240.0} = 21.10\text{ m/s} = 75.94\text{ km/h}$$

### Kinematic Jump Filter (Anti-Spoofing Heuristic)
A fix is flagged as an implausible kinematic jump (`is_implausible_jump = 1`) if:
1. $v_{\text{derived}} > 50.0\text{ m/s}$ ($180\text{ km/h}$), OR
2. $d > 300.0\text{ m}$ when $\Delta t \le 2.0\text{ s}$ ($> 150\text{ m/s}$).

---

## 3. Telemetry Freshness & Temporal Decay

Telemetry freshness is measured from the **server receipt timestamp** ($t_{\text{recv}}$), completely independent of client device clock drifts.

### Freshness Status Thresholds
$$\Delta t_{\text{age}} = t_{\text{server\_now}} - t_{\text{server\_received\_at}}$$

$$\text{Status} = \begin{cases} 
\text{LIVE} & \Delta t_{\text{age}} < 90\text{ s} \\
\text{STALE} & 90\text{ s} \le \Delta t_{\text{age}} \le 300\text{ s} \\
\text{OFFLINE} & \Delta t_{\text{age}} > 300\text{ s}
\end{cases}$$

### Freshness Quality Score ($Q_{\text{freshness}}$)
Exponential decay function with scale constant $\tau = 300\text{ s}$:

$$Q_{\text{freshness}} = 100.0 \times \exp\left(-\frac{\Delta t_{\text{age}}}{300.0}\right)$$

- At $\Delta t_{\text{age}} = 0\text{ s} \implies Q_{\text{freshness}} = 100.0$
- At $\Delta t_{\text{age}} = 90\text{ s} \implies Q_{\text{freshness}} = 74.08$
- At $\Delta t_{\text{age}} = 300\text{ s} \implies Q_{\text{freshness}} = 36.79$

---

## 4. GPS Accuracy Quality Score ($Q_{\text{GPS}}$)

Horizontal radial accuracy reported by the hardware GPS sensor is scored using an exponential decay model with reference constant $\sigma_{\text{GPS}} = 50.0\text{ m}$:

$$Q_{\text{GPS}} = 100.0 \times \exp\left(-\frac{\text{accuracy}}{50.0}\right)$$

### Worked Example
- For a high-precision mobile fix with $\text{accuracy} = 15.0\text{ m}$:
  $$Q_{\text{GPS}} = 100.0 \times \exp\left(-\frac{15.0}{50.0}\right) = 74.08$$
- For $\text{accuracy} = 5.0\text{ m}$:
  $$Q_{\text{GPS}} = 100.0 \times \exp(-0.1) = 90.48$$

---

## 5. Capacity Suitability Heuristic

Evaluates how efficiently a vehicle's payload capacity satisfies a delivery's required weight.

### Formula
Let $W = \text{package\_weight}$ and $C = \text{vehicle\_capacity}$:

$$\text{Score}(W, C) = \begin{cases}
0.0 & \text{if } W \le 0 \text{ or } C \le 0 \\
0.0 & \text{if } W > C \quad (\text{overloaded: hard rejected}) \\
\max\left(0.0, \, \min\left(100.0, \, 100.0 - \left(\frac{C - W}{C} \times 20.0\right)\right)\right) & \text{if } W \le C
\end{cases}$$

### Properties
1. **Bounded**: Strictly in $[0.0, 100.0]$.
2. **Monotonic**: Score decreases smoothly from $100.0$ (exact fit $W = C$) down to $80.0$ as surplus vehicle capacity increases.
3. **Hard Constraint**: Any overload ($W > C$) yields strictly $0.0$, preventing illegal assignments.

### Worked Examples
- **Exact Fit**: $W = 1000\text{ kg}, \ C = 1000\text{ kg} \implies \text{ratio} = 0.0 \implies \text{Score} = 100.0$
- **Efficient Fit**: $W = 800\text{ kg}, \ C = 1000\text{ kg} \implies \text{ratio} = \frac{200}{1000} = 0.20 \implies \text{Score} = 100.0 - (0.20 \times 20.0) = 96.0$
- **Overload**: $W = 1200\text{ kg}, \ C = 1000\text{ kg} \implies \text{Score} = 0.0$

---

## 6. Composite Telemetry Quality & Renormalization

When evaluating telemetry quality across heterogeneous devices, missing sensors (e.g. absent altitude or magnetometer heading) are dynamically renormalized so missing optional data does not artificially depress scores.

### Formula
$$Q_{\text{telemetry}} = \frac{\sum_{k \in \mathcal{A}} w_k \cdot Q_k}{\sum_{k \in \mathcal{A}} w_k}$$

Where $\mathcal{A}$ is the set of available component scores and $w_k$ are heuristic weights:
- $w_{\text{GPS}} = 0.35$
- $w_{\text{freshness}} = 0.25$
- $w_{\text{movement}} = 0.25$
- $w_{\text{completeness}} = 0.15$

If $\sum_{k \in \mathcal{A}} w_k = 0$, $Q_{\text{telemetry}} = \text{null}$.

---

## 7. Operational Rate Limits & Ingestion Invariants

To protect SQLite transaction throughput against telemetry flooding:

1. **Per-Device Burst Rate Limit**:
   $$t_{\text{recv}} - t_{\text{last\_recv}} \ge 0.5\text{ s}$$
2. **Device-Reported Throttle**:
   $$t_{\text{dev}} - t_{\text{last\_dev}} \ge 0.8\text{ s}$$
3. **Clock Skew Threshold**:
   $$|t_{\text{server}} - t_{\text{device}}| > 5.0\text{ s} \implies \text{status: clock\_skew\_high}$$

---

## 8. Zero-Denominator Safety Rule

In all aggregate analytics and operational formulas:
$$\text{If denominator } = 0 \implies \text{return } \text{null} \ (\text{"Not available"})$$

No fallback percentages, fake averages, or synthetic defaults are ever emitted when sample count is zero.
