"""Small probability blend of already fitted CPU classifiers."""
import numpy as np


class AudioBlend:
    def __init__(self, reference, candidate, candidate_weight):
        if not 0 < candidate_weight < 1 or list(reference.classes_) != [0, 1] or list(candidate.classes_) != [0, 1]:
            raise ValueError("Audio blend requires two compatible classifiers and a weight between zero and one.")
        self.reference = reference
        self.candidate = candidate
        self.candidate_weight = float(candidate_weight)
        self.classes_ = np.array([0, 1])

    def predict_proba(self, features):
        return ((1 - self.candidate_weight) * self.reference.predict_proba(features)
                + self.candidate_weight * self.candidate.predict_proba(features))
