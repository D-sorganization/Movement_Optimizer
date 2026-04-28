## 2026-04-26 - Optimize LagrangianKinematicsMixin com_position array allocations
**Learning:** In highly called NumPy calculations (e.g., com_position in LagrangianKinematicsMixin), creating intermediate small arrays using `np.array([np.sin(q[..]), np.cos(q[..])])` introduces significant overhead due to memory allocation compared to directly operating on unrolled scalar variables.
**Action:** Unroll the scalar calculations fully and compute `x` and `y` coordinates separately before re-grouping into an `np.array` at the end to drastically speed up repetitive math functions like calculating the center of mass.

## 2026-04-26 - Optimize LagrangianDynamics scalar math overhead
**Learning:** In highly called internal methods like `inverse_dynamics()`, using NumPy's `np.cos`/`np.sin` on unrolled scalar variables incurs measurable function-dispatch overhead (approx. 20%) compared to Python's built-in `math` module equivalents.
**Action:** Always prefer `math.cos`/`math.sin` over `np.cos`/`np.sin` when operating strictly on single `float` scalars inside performance-sensitive loop bodies.
