//! Rust-accelerated hot-path functions for the Movement Optimizer.
//!
//! Provides vectorised inverse dynamics and COM computation using
//! pre-computed coupling coefficients.  Uses rayon for parallel
//! iteration over timesteps when N is large.

use numpy::ndarray::{Array1, Array2, ArrayView2, Axis};
use numpy::{IntoPyArray, PyArray1, PyArray2, PyReadonlyArray2};
use pyo3::prelude::*;
use rayon::prelude::*;

/// Parallel threshold: use rayon only if N exceeds this.
const PAR_THRESHOLD: usize = 128;

/// Compute inverse dynamics for all timesteps in batch.
///
/// Parameters are pre-computed scalar constants from LagrangianDynamics:
///   M00, M11, M22  -- diagonal mass-matrix entries
///   a01, a02, a12  -- coupling coefficients
///   g0, g1, g2     -- gravity coefficients
///
/// q, qd, qdd: (N, 3) arrays
/// Returns: torques (N, 3)
#[pyfunction]
fn inverse_dynamics_batch_rs<'py>(
    py: Python<'py>,
    q: PyReadonlyArray2<'py, f64>,
    qd: PyReadonlyArray2<'py, f64>,
    qdd: PyReadonlyArray2<'py, f64>,
    m00: f64,
    m11: f64,
    m22: f64,
    a01: f64,
    a02: f64,
    a12: f64,
    g0: f64,
    g1: f64,
    g2: f64,
) -> Bound<'py, PyArray2<f64>> {
    let q = q.as_array();
    let qd = qd.as_array();
    let qdd = qdd.as_array();
    let n = q.shape()[0];

    let mut tau = Array2::<f64>::zeros((n, 3));

    let compute_row = |i: usize| -> [f64; 3] {
        let q0 = q[[i, 0]];
        let q1 = q[[i, 1]];
        let q2 = q[[i, 2]];
        let qd0 = qd[[i, 0]];
        let qd1 = qd[[i, 1]];
        let qd2 = qd[[i, 2]];
        let qdd0 = qdd[[i, 0]];
        let qdd1 = qdd[[i, 1]];
        let qdd2 = qdd[[i, 2]];

        let d01 = q0 - q1;
        let d02 = q0 - q2;
        let d12 = q1 - q2;

        let c01 = d01.cos();
        let c02 = d02.cos();
        let c12 = d12.cos();
        let s01 = d01.sin();
        let s02 = d02.sin();
        let s12 = d12.sin();

        // M(q) * qdd
        let t0 = m00 * qdd0 + a01 * c01 * qdd1 + a02 * c02 * qdd2;
        let t1 = a01 * c01 * qdd0 + m11 * qdd1 + a12 * c12 * qdd2;
        let t2 = a02 * c02 * qdd0 + a12 * c12 * qdd1 + m22 * qdd2;

        // + Coriolis
        let t0 = t0 + a01 * s01 * qd1 * qd1 + a02 * s02 * qd2 * qd2;
        let t1 = t1 - a01 * s01 * qd0 * qd0 + a12 * s12 * qd2 * qd2;
        let t2 = t2 - a02 * s02 * qd0 * qd0 - a12 * s12 * qd1 * qd1;

        // + Gravity
        let t0 = t0 + g0 * q0.sin();
        let t1 = t1 + g1 * q1.sin();
        let t2 = t2 + g2 * q2.sin();

        [t0, t1, t2]
    };

    if n >= PAR_THRESHOLD {
        // Parallel: collect results then copy
        let rows: Vec<[f64; 3]> = (0..n).into_par_iter().map(compute_row).collect();
        for (i, row) in rows.iter().enumerate() {
            tau[[i, 0]] = row[0];
            tau[[i, 1]] = row[1];
            tau[[i, 2]] = row[2];
        }
    } else {
        // Sequential for small N (avoids rayon overhead)
        for i in 0..n {
            let row = compute_row(i);
            tau[[i, 0]] = row[0];
            tau[[i, 1]] = row[1];
            tau[[i, 2]] = row[2];
        }
    }

    tau.into_pyarray(py).into()
}

/// Compute COM x-coordinate for all timesteps.
///
/// Parameters:
///   q: (N, 3) joint angles
///   l0, l1, l2: segment lengths
///   d0, d1, d2: COM distances from proximal joint
///   m0, m1, m2: segment masses
///   m_feet, foot_com_x: foot mass and COM x
///   bar_mass, body_mass: load and total body mass
///   is_squat: true for squat/full_squat, false for deadlift
///   m_arms: arm mass (used for deadlift)
///
/// Returns: com_x (N,)
#[pyfunction]
fn com_x_batch_rs<'py>(
    py: Python<'py>,
    q: PyReadonlyArray2<'py, f64>,
    l0: f64, l1: f64, l2: f64,
    d0: f64, d1: f64, d2: f64,
    m0: f64, m1: f64, m2: f64,
    m_feet: f64,
    foot_com_x: f64,
    bar_mass: f64,
    body_mass: f64,
    is_squat: bool,
    m_arms: f64,
) -> Bound<'py, PyArray1<f64>> {
    let q = q.as_array();
    let n = q.shape()[0];
    let total_mass = body_mass + bar_mass;

    let compute_one = |i: usize| -> f64 {
        let sq0 = q[[i, 0]].sin();
        let sq1 = q[[i, 1]].sin();
        let sq2 = q[[i, 2]].sin();

        let knee_x = l0 * sq0;
        let hip_x = knee_x + l1 * sq1;
        let shoulder_x = hip_x + l2 * sq2;

        let c1x = d0 * sq0;
        let c2x = knee_x + d1 * sq1;
        let c3x = hip_x + d2 * sq2;

        let mut num = m_feet * foot_com_x + m0 * c1x + m1 * c2x + m2 * c3x;

        if is_squat {
            num += bar_mass * shoulder_x;
        } else {
            num += (m_arms + bar_mass) * shoulder_x;
        }

        num / total_mass
    };

    let result: Vec<f64> = if n >= PAR_THRESHOLD {
        (0..n).into_par_iter().map(compute_one).collect()
    } else {
        (0..n).map(compute_one).collect()
    };

    Array1::from_vec(result).into_pyarray(py).into()
}

#[pymodule]
fn movement_optimizer_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(inverse_dynamics_batch_rs, m)?)?;
    m.add_function(wrap_pyfunction!(com_x_batch_rs, m)?)?;
    Ok(())
}
