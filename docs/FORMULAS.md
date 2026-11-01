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

## 4. GPS Accuracy Quality Score, Uncertainty & Position Confidence

Horizontal radial accuracy reported by the hardware GPS sensor is scored using an exponential decay model with reference constant scale $50.0\text{ m}$:

### Accuracy Quality Score Formula
$$S = 100.0 \times \exp\left(-\frac{\text{accuracy}}{50.0}\right), \quad S \in [0.0, 100.0]$$

If accuracy is null or invalid, $S = \text{null}$ (displayed as "n/a").

### Quality Tiers (Uncapped Raw Accuracy)
- **Excellent**: $\le 5.0\text{ m}$
- **Good**: $\le 15.0\text{ m}$
- **Fair**: $\le 50.0\text{ m}$
- **Poor**: $\le 100.0\text{ m}$
- **Very poor**: $> 100.0\text{ m}$

### Radius-Confidence Assumption (1-$\sigma$ Standard Deviation)
Modern operating systems report horizontal accuracy as a confidence circle. Android reports a $68\%$ probability radius ($p = 0.68$), while the W3C Geolocation specification specifies a $95\%$ probability ($p = 0.95$). FleetWise models this via the configurable parameter `ACCURACY_CONFIDENCE_P` (default $0.68$):

$$\sigma_{\text{pos}} = \frac{\text{accuracy}}{\sqrt{-2 \ln(1 - p)}}$$

For $p = 0.68$:
$$\sqrt{-2 \ln(1 - 0.68)} = \sqrt{-2 \ln(0.32)} \approx 1.5096 \implies \sigma_{\text{pos}} = \frac{\text{accuracy}}{1.5096}$$

### 95% Confidence Radius
$$r_{95} = \sigma_{\text{pos}} \times \sqrt{-2 \ln(0.05)} \approx 2.4477 \times \sigma_{\text{pos}}$$

### Position Confidence Probability
The analytical probability that the vehicle's true position is within $r$ meters of the estimated coordinate:

$$C_{\text{pos}}(r) = 1.0 - \exp\left(-\frac{r^2}{2 \sigma_{\text{pos}}^2}\right)$$

### Worked Example: Commercial Smartphone at 76 m Accuracy
- **Raw Accuracy**: $\text{accuracy} = 76.0\text{ m}$ (Tier: **Poor**)
- **Accuracy Quality Score**:
  $$S = 100.0 \times \exp\left(-\frac{76.0}{50.0}\right) = 100.0 \times \exp(-1.52) = 21.9$$
- **1-$\sigma$ Standard Deviation**:
  $$\sigma_{\text{pos}} = \frac{76.0}{1.5096} = 50.3\text{ m}$$
- **95% Confidence Radius**:
  $$r_{95} = 50.3447 \times 2.4477 = 123.2\text{ m}$$
- **Position Confidence at Geofence Radius ($r = 50.0\text{ m}$)**:
  $$C_{\text{pos}}(50.0\text{ m}) = 1.0 - \exp\left(-\frac{50.0^2}{2 \times 50.3447^2}\right) = 1.0 - \exp(-0.4932) \approx 0.389 \implies 38.9\% \ (\approx 39\%)$$

> [!NOTE]
> Physical GPS accuracy originates entirely from the client device hardware sensor and satellite geometry. Software algorithms and filtering cannot magically improve raw sensor accuracy. Laptops and desktop browsers relying on Wi-Fi positioning or IP geolocation typically exhibit accuracies of tens to hundreds of meters.

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

