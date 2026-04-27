## 2026-04-26 - Optimize LagrangianKinematicsMixin com_position array allocations
**Learning:** In highly called NumPy calculations (e.g., com_position in LagrangianKinematicsMixin), creating intermediate small arrays using `np.array([np.sin(q[..]), np.cos(q[..])])` introduces significant overhead due to memory allocation compared to directly operating on unrolled scalar variables.
**Action:** Unroll the scalar calculations fully and compute `x` and `y` coordinates separately before re-grouping into an `np.array` at the end to drastically speed up repetitive math functions like calculating the center of mass.
## 2026-04-26 - Optimize inverse dynamics with fully unrolled calculations
**Learning:** In highly called scalar physical calculations, avoid composing intermediate large structural arrays (e.g., a 3x3 mass matrix or 3x1 vector arrays for coriolis/gravity) when doing an immediate matrix multiplication.
**Action:** Unroll the matrix/vector operations into simple scalars instead to save memory allocation and loop overhead.
