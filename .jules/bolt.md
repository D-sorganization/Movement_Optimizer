## 2026-04-26 - Optimize LagrangianKinematicsMixin com_position array allocations
**Learning:** In highly called NumPy calculations (e.g., com_position in LagrangianKinematicsMixin), creating intermediate small arrays using `np.array([np.sin(q[..]), np.cos(q[..])])` introduces significant overhead due to memory allocation compared to directly operating on unrolled scalar variables.
**Action:** Unroll the scalar calculations fully and compute `x` and `y` coordinates separately before re-grouping into an `np.array` at the end to drastically speed up repetitive math functions like calculating the center of mass.

## 2024-05-18 - Math module vs Numpy scalar ops
**Learning:** For highly called functions calculating small vectors, unrolling array logic to convert parameters to float, computing with python's `math` module instead of `np` equivalents, squaring by explicit multiplication rather than `** 2`, and outputting directly into a new `np.array` saves substantial overhead compared to using numpy operations.
**Action:** Unroll hot loops over small fixed-length vectors (like size 3) replacing `np.sin`, `** 2`, and individual array index assignments into an initialized zero array with direct `math` functions, float operations and single array creations.
