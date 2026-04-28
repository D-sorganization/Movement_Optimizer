## 2026-04-26 - Optimize LagrangianKinematicsMixin com_position array allocations
**Learning:** In highly called NumPy calculations (e.g., com_position in LagrangianKinematicsMixin), creating intermediate small arrays using `np.array([np.sin(q[..]), np.cos(q[..])])` introduces significant overhead due to memory allocation compared to directly operating on unrolled scalar variables.
**Action:** Unroll the scalar calculations fully and compute `x` and `y` coordinates separately before re-grouping into an `np.array` at the end to drastically speed up repetitive math functions like calculating the center of mass.

## 2026-05-18 - Unroll matrix operations for inverse dynamics
**Learning:** In highly called scalar physical calculations like inverse dynamics, creating intermediate structural arrays (e.g., 3x3 mass matrices or 3x1 vectors) followed by array multiplication creates massive memory allocation and loop overhead.
**Action:** Unroll these operations into scalar calculations using Python's `math` module and direct assignments, avoiding `numpy.zeros` and intermediate array operations, which speeds up individual `inverse_dynamics` calls significantly (e.g., ~3.3x faster).
