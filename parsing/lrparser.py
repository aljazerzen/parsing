from __future__ import annotations

from parsing.ast import Symbol, Nonterm, Token
from parsing.automaton import Spec
from parsing import interfaces
from parsing.errors import UnexpectedToken
from parsing.grammar import (
    Production,
    TokenSpec,
    EndOfInput,
    Epsilon,
    ShiftAction,
    ReduceAction,
)


class Lr:
    """
    LR(1) parser.  The Lr class uses a Spec instance in order to parse
    input that is fed to it via the token() method, and terminated via the
    eoi() method.
    """

    _spec: Spec
    _start: list[Symbol] | None
    _stack: list[tuple[Symbol, int]]

    def __init__(self, spec: Spec) -> None:
        if __debug__:
            if type(self) == Lr:
                assert spec.pureLR
        assert spec._nConflicts == 0
        self._spec = spec
        self.reset()
        self._verbose = False

    def sym_spec(self, sym: Symbol) -> interfaces.SymbolSpec:
        return self._spec._sym2spec[type(sym)]

    @property
    def spec(self) -> Spec:
        return self._spec

    @property
    def start(self) -> list[Symbol] | None:
        """A list of parsing results.  For LR parsing, there is only ever one
        result, but for compatibility with the Glr interface, start is a
        list."""
        return self._start

    def __getVerbose(self) -> bool:
        return self._verbose

    def __setVerbose(self, verbose: bool) -> None:
        assert type(verbose) == bool
        self._verbose = verbose

    verbose = property(__getVerbose, __setVerbose)

    def reset(self) -> None:
        self._start = None
        self._stack = [(Epsilon(self), 0)]

    def token(self, token: Token) -> None:
        """Feed a token to the parser."""
        tokenSpec = self._spec._sym2spec[type(token)]
        self._act(token, tokenSpec)  # type: ignore

    def eoi(self) -> None:
        """Signal end-of-input to the parser."""
        token = EndOfInput(self)
        self.token(token)

        assert self._stack[-1][0] == token  # <$>.
        if self._verbose:
            self._printStack()
            print("   --> accept")
        self._stack.pop()

        self._start = [self._stack[1][0]]
        assert (
            self._spec._sym2spec[type(self._start[0])]
            == self._spec._userStartSym
        )

    def _act(self, sym: Token, symSpec: TokenSpec) -> None:
        if self._verbose:
            self._printStack()
            print("INPUT: %r" % sym)

        while True:
            top = self._stack[-1]
            if symSpec not in self._spec._action[top[1]]:
                raise UnexpectedToken("Unexpected token: %r" % sym)

            actions = self._spec._action[top[1]][symSpec]
            assert len(actions) == 1
            action = actions[0]

            if self._verbose:
                print("   --> %r" % action)
            if type(action) == ShiftAction:
                self._stack.append((sym, action.nextState))
                break
            else:
                assert type(action) == ReduceAction
                self._reduce(action.production)

            if self._verbose:
                self._printStack()

    def _printStack(self) -> None:
        print("STACK:", end=" ")
        for node in self._stack:
            print("%r" % node[0], end=" ")
        print()
        print("      ", end=" ")
        for node in self._stack:
            print(
                "%r%s"
                % (
                    node[1],
                    (" " * (len("%r" % node[0]) - len("%r" % node[1]))),
                ),
                end=" ",
            )
        print()

    def _reduce(self, production: Production) -> None:
        nRhs = len(production.rhs)
        rhs = []
        for i in range(len(self._stack) - nRhs, len(self._stack)):
            rhs.append(self._stack[i][0])

        r = self._production(production, rhs)

        for i in range(nRhs):
            self._stack.pop()

        top = self._stack[-1]
        self._stack.append((r, self._spec._goto[top[1]][production.lhs]))

    def _production(
        self, production: Production, rhs: list[Symbol]
    ) -> Nonterm:
        sym = production.lhs.nontermType(self)
        nRhs = len(rhs)
        assert nRhs == len(production.rhs)
        r = production.method(sym, *rhs)

        # Python's method definition syntax makes returning self from %reduce
        # methods cumbersome, so translate None here.
        if r is None:
            r = sym

        return r