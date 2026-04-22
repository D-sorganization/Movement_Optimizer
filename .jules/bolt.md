## 2026-04-21 - Vectorized SciPy Splines
**Learning:** In the trajectory optimization loop, creating and evaluating separate `CubicSpline` instances for each degree of freedom in a list comprehension is a significant bottleneck. SciPy's `CubicSpline` natively supports multidimensional `y` arrays and interpolates along `axis=0` by default.
**Action:** Always prefer initializing a single multidimensional spline over a list of 1D splines to leverage underlying C/Fortran vectorization and eliminate Python loop overhead and `np.column_stack` operations.

## 2024-05-24 - Batch Inverse Dynamics Allocation Overhead
**Learning:** In the Python implementation of batch inverse dynamics, splitting calculations into separate `_batch_inertia_torques`, `_batch_coriolis_torques`, and `_batch_gravity_torques` functions causes massive performance degradation due to redundant allocations of large `(N, 3)` intermediate NumPy arrays and redundant passes over the data.
**Action:** Fuse such numerical computations into a single function that pre-allocates one output array (`np.empty((N, 3))`) and populates it directly using flattened arrays.

## 2026-05-18 - Fast Squared L2 Norms with NumPy
**Learning:** Computing the sum of squared elements via `np.sum(array**2)` incurs significant overhead from intermediate array allocation (`array**2`) and Python iteration logic, especially in hot loops like the trajectory optimizer cost functions. Using `np.vdot(array, array)` is entirely implemented in C (or fast BLAS) and avoids this overhead, making it 4-5x faster for 1D/2D arrays.
**Action:** Always use `np.vdot(array, array)` instead of `np.sum(array**2)` for computing squared L2 norms in performance-critical code paths.
