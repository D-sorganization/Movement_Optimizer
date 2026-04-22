## 2026-04-21 - Vectorized SciPy Splines
**Learning:** In the trajectory optimization loop, creating and evaluating separate `CubicSpline` instances for each degree of freedom in a list comprehension is a significant bottleneck. SciPy's `CubicSpline` natively supports multidimensional `y` arrays and interpolates along `axis=0` by default.
**Action:** Always prefer initializing a single multidimensional spline over a list of 1D splines to leverage underlying C/Fortran vectorization and eliminate Python loop overhead and `np.column_stack` operations.

## 2024-05-24 - Batch Inverse Dynamics Allocation Overhead
**Learning:** In the Python implementation of batch inverse dynamics, splitting calculations into separate `_batch_inertia_torques`, `_batch_coriolis_torques`, and `_batch_gravity_torques` functions causes massive performance degradation due to redundant allocations of large `(N, 3)` intermediate NumPy arrays and redundant passes over the data.
**Action:** Fuse such numerical computations into a single function that pre-allocates one output array (`np.empty((N, 3))`) and populates it directly using flattened arrays.

## 2024-11-20 - Fast L2 Norm Calculations
**Learning:** In optimization cost functions evaluated thousands of times, calculating the L2 norm (sum of squares) using `np.sum(x**2)` requires allocating an intermediate array for the squared elements before summing them.
**Action:** Replace `np.sum(x**2)` with `np.vdot(x, x)` for these inner products. `np.vdot` avoids allocating an intermediate array and operates natively on multidimensional arrays (it flattens them inherently in C), yielding a ~3-4x speedup on arrays of standard size for these calculations.
