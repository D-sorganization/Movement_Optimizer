## 2026-04-26 - Optimize LagrangianKinematicsMixin com_position array allocations

**Learning:** In highly called NumPy calculations (e.g., com_position in LagrangianKinematicsMixin), creating intermediate small arrays using `np.array([np.sin(q[..]), np.cos(q[..])])` introduces significant overhead due to memory allocation compared to directly operating on unrolled scalar variables.
**Action:** Unroll the scalar calculations fully and compute `x` and `y` coordinates separately before re-grouping into an `np.array` at the end to drastically speed up repetitive math functions like calculating the center of mass.
## 2026-04-29 - Optimize unrolled scalar math calculations
**Learning:** In highly called scalar physical calculations (like `inverse_dynamics`), unrolling the vector components and using Python's built-in `math.cos`/`math.sin` is significantly faster than using `np.cos`/`np.sin` on individual scalar components due to NumPy's dispatch and allocation overhead.
**Action:** Use Python's built-in `math` module instead of NumPy equivalents for scalar math operations within performance-critical, unrolled computational loops.
