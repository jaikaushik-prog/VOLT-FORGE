"""Same-side-terminal parallel ladder; static electrical solution only.

Positive branch and module current mean discharge. Each cell is an effective
voltage source E_i behind positive R0_i. E_i may later be U_i - v_p,i; this
solver makes no assumption about whether those quantities were identified.
Independent positive/negative rail segments carry the sums of downstream
branch currents. No experimental module validation is claimed.
"""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class LadderSolution:
    branch_A: np.ndarray
    terminal_V: float
    cell_terminal_V: np.ndarray
    positive_nodes_V: np.ndarray
    negative_nodes_V: np.ndarray
    rail_downstream_A: np.ndarray
    ohmic_cell_loss_W: float
    rail_loss_W: float
    kcl_residual_A: float
    energy_residual_W: float
    matrix_condition: float


def solve_ladder(effective_source_V, cell_ohm, positive_rail_ohm, negative_rail_ohm, module_A):
    e, r, rp, rn = [np.asarray(v, dtype=float) for v in
                    (effective_source_V, cell_ohm, positive_rail_ohm, negative_rail_ohm)]
    if e.ndim != 1 or not len(e) or r.shape != e.shape or rp.shape != (len(e)-1,) or rn.shape != rp.shape:
        raise ValueError("Expected n cell sources/resistances and n-1 segments on each rail")
    if not all(np.isfinite(x).all() for x in (e,r,rp,rn)) or not np.isfinite(module_A):
        raise ValueError("All electrical inputs must be finite")
    if np.any(r <= 0) or np.any(rp < 0) or np.any(rn < 0):
        raise ValueError("Cell resistance must be positive and rail resistance nonnegative")
    n = len(e)
    # S[j,i] is 1 when branch i lies downstream of rail segment j.
    s = (np.arange(n)[None,:] > np.arange(n-1)[:,None]).astype(float)
    z = np.diag(r) + s.T @ np.diag(rp+rn) @ s
    a = np.block([[z, np.ones((n,1))], [np.ones((1,n)), np.zeros((1,1))]])
    sol = np.linalg.solve(a, np.r_[e,float(module_A)])
    branch, v = sol[:n], float(sol[-1])
    downstream = s @ branch
    p = v + np.r_[0., np.cumsum(rp*downstream)]
    neg = -np.r_[0., np.cumsum(rn*downstream)]
    cell_loss = float(np.dot(r,branch**2))
    rail_loss = float(np.dot(rp+rn,downstream**2))
    return LadderSolution(branch, v, e-r*branch, p, neg, downstream, cell_loss, rail_loss,
                          float(branch.sum()-module_A), float(e@branch-v*module_A-cell_loss-rail_loss),
                          float(np.linalg.cond(a)))
