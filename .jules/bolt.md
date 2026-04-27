## 2026-04-26 - Optimize LagrangianKinematicsMixin com_position array allocations
**Learning:** In highly called NumPy calculations (e.g., com_position in LagrangianKinematicsMixin), creating intermediate small arrays using `np.array([np.sin(q[..]), np.cos(q[..])])` introduces significant overhead due to memory allocation compared to directly operating on unrolled scalar variables.
**Action:** Unroll the scalar calculations fully and compute `x` and `y` coordinates separately before re-grouping into an `np.array` at the end to drastically speed up repetitive math functions like calculating the center of mass.

## 2026-04-26 - Unroll intermediate arrays in inverse dynamics
**Learning:** In highly called scalar physical calculations like `inverse_dynamics`, composing intermediate structural arrays (e.g., 3x3 mass matrices via `mass_matrix()`, 3x1 vectors via `_coriolis_vector()` and `_gravity_vector()`) for immediate matrix multiplication introduces significant memory allocation and loop overhead.
**Action:** Unroll operations into simple scalars to avoid multiple array allocations and use mathematical operations directly.
