## 2026-04-21 - Vectorized SciPy Splines
**Learning:** In the trajectory optimization loop, creating and evaluating separate `CubicSpline` instances for each degree of freedom in a list comprehension is a significant bottleneck. SciPy's `CubicSpline` natively supports multidimensional `y` arrays and interpolates along `axis=0` by default.
**Action:** Always prefer initializing a single multidimensional spline over a list of 1D splines to leverage underlying C/Fortran vectorization and eliminate Python loop overhead and `np.column_stack` operations.
