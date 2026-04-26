## 2026-04-21 - Vectorized SciPy Splines
**Learning:** In the trajectory optimization loop, creating and evaluating separate `CubicSpline` instances for each degree of freedom in a list comprehension is a significant bottleneck. SciPy's `CubicSpline` natively supports multidimensional `y` arrays and interpolates along `axis=0` by default.
**Action:** Always prefer initializing a single multidimensional spline over a list of 1D splines to leverage underlying C/Fortran vectorization and eliminate Python loop overhead and `np.column_stack` operations.

## 2024-05-24 - Batch Inverse Dynamics Allocation Overhead
**Learning:** In the Python implementation of batch inverse dynamics, splitting calculations into separate `_batch_inertia_torques`, `_batch_coriolis_torques`, and `_batch_gravity_torques` functions causes massive performance degradation due to redundant allocations of large `(N, 3)` intermediate NumPy arrays and redundant passes over the data.
**Action:** Fuse such numerical computations into a single function that pre-allocates one output array (`np.empty((N, 3))`) and populates it directly using flattened arrays.

## 2024-06-15 - np.sum(x**2) vs np.vdot(x, x)
**Learning:** In highly called cost functions like trajectory optimizers, `np.sum(x**2)` allocates a large intermediate array for the squares before summing, which adds memory allocation overhead. `np.vdot(x, x)` achieves the exact same L2 norm natively in a C loop with zero intermediate allocations, which makes it over 4x faster on arrays.
**Action:** Always prefer `np.vdot(array, array)` for computing the sum of squares.

## 2026-05-18 - Fast Squared L2 Norms with NumPy
**Learning:** Computing the sum of squared elements via `np.sum(array**2)` incurs significant overhead from intermediate array allocation (`array**2`) and Python iteration logic, especially in hot loops like the trajectory optimizer cost functions. Using `np.vdot(array, array)` is entirely implemented in C (or fast BLAS) and avoids this overhead, making it 4-5x faster for 1D/2D arrays.
**Action:** Always use `np.vdot(array, array)` instead of `np.sum(array**2)` for computing squared L2 norms in performance-critical code paths.
## 2024-06-25 - Weighted Sums of Squares with NumPy
**Learning:** Computing a weighted sum of squares along an axis via `np.dot(w, np.sum(x**2, axis=1))` incurs significant overhead due to intermediate array allocations. Replacing this pattern with `np.vdot(w[:, np.newaxis] * x, x)` flattens the arrays to compute the dot product in C (or fast BLAS), resulting in ~2x speedup and minimal memory allocations. `np.einsum` was found to be slower in this context.
**Action:** Always prefer `np.vdot` with broadcasted weights for calculating weighted sums of squares in performance-critical code paths.

## 2026-05-19 - Replacing Sequential Additions with Matrix Multiplication
**Learning:** In hot loops like constraint evaluations or cost functions, computing weighted sums sequentially via explicit element-wise products and additions (e.g. `L[0]*sin(q[:,0]) + L[1]*sin(q[:,1]) + L[2]*sin(q[:,2])`) incurs substantial overhead from multiple intermediate array allocations and Python loop processing. Replacing these with Numpy's `@` operator for matrix-vector multiplication (e.g. `np.sin(q) @ L`) achieves the same result while offloading computation to highly optimized C/BLAS routines and minimizing intermediate arrays, yielding a 3-4x speedup.
**Action:** Always prefer matrix multiplication (`@`) over explicit sequential addition of element-wise array operations when computing weighted sums or coordinates across multiple segments.

## 2026-04-25 - NumPy Scalar Operations & Unrolling
**Learning:** In NumPy, combining explicit Python lists into `np.array([a, b])` inside frequently called kinematic methods (like `forward_kinematics`) creates massive intermediate allocation overhead. Additionally, using `** 2` for array exponentiation is slower than explicit array multiplication `array * array`, and `np.empty()` is slightly faster than `np.zeros()` when overwriting all array values.
**Action:** Unroll scalar components into simple python variables and only create the final arrays. Avoid `** 2` in favor of `a * a` in NumPy arrays.
## 2024-04-26 - Unrolling scalar trig calculations in NumPy

**Learning:** Fully unrolling scalar components and avoiding explicit intermediate array creation (like `np.array([np.sin(q), np.cos(q)])`) dramatically improves performance in iterative kinematic solvers in NumPy.

**Action:** In highly called NumPy calculations, compute scalar components first and directly construct the final array, bypassing intermediary arrays.
