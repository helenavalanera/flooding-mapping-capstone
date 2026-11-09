"""A rainfall rule dressed as a scikit-learn scorer.

When no learned model beats the simple rainfall rules, the rule is what runs. Wrapping it with
``predict_proba`` lets training, the forecast-skew evaluation and the live inference treat a
rule and a model alike: the "probability" column is just the rule's value (an unbounded score);
the isotonic calibrator stored next to it turns it into an empirical frequency.
"""

from __future__ import annotations

import numpy as np


class RuleScorer:
    """Scores a row by one input column (for example ``rel_p3d``); nothing is fitted."""

    def __init__(self, index: int = 0) -> None:
        self.index = index

    def predict_proba(self, X) -> np.ndarray:
        score = np.asarray(X, dtype=float)[:, self.index]
        return np.column_stack([-score, score])
