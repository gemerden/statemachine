import random

from statemachine.machine import StateMachine, State, MachineError, callbackify, Transition


class RandomCondition(object):

    def __init__(self, threshold):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold in RandomCondition must be between 0.0 and 1.0")
        self.threshold = threshold

    def __call__(self, *args, **kwargs):
        return random.random() < self.threshold


class MarkovMachine(StateMachine):

    def __init__(self, matrix, **kwargs):
        super(MarkovMachine, self).__init__(**kwargs)
        if len(self.transitions):
            raise MachineError("parameter 'transitions' not allowed; MarkovMachine auto-generates transitions")
        if not all(isinstance(state, State) for state in self.sub_states):
            raise MachineError("MarkovMachine cannot have nested states")
        self._check_matrix(matrix)
        self._apply_matrix(matrix)

    def _check_matrix(self, matrix):
        if len(matrix) != len(self.sub_states):
            raise ValueError("markov matrix does not have same number of rows as there are states")
        for row in matrix:
            if len(row) != len(row):
                raise ValueError("row in markov matrix does not have same number of calls as there are states")
            if not all(0.0 <= c <= 1.0 for c in row):
                raise ValueError("all values in markov matrix must be between 0.0 and 1.0")
            if sum(row) != 1.0:
                raise ValueError("sum of reach row in the markov matrix must be 1.0")
        return matrix

    def _apply_matrix(self, matrix):
        for row, old_state in zip(matrix, self.sub_states):
            remaining = 1.0
            for prob, new_state in zip(row, self.sub_states):
                if remaining == 0.0:
                    break
                if prob != 0.0:
                    condition = RandomCondition(threshold=prob / remaining)
                    self.transitions[old_state.path, new_state.path] = Transition(machine=self,
                                                                                  old_state=old_state.name,
                                                                                  new_state=new_state.name,
                                                                                  condition = condition,
                                                                                  triggers="trigger")
                    remaining -= prob




