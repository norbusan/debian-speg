import sys, re

class ParseError(Exception):
    def __init__(self, msg, text, offset, line, col):
        self.msg = msg
        self.text = text
        self.offset = offset
        self.line = line
        self.col = col
        super(ParseError, self).__init__(msg, offset, line, col)

if sys.version_info[0] == 2:
    _basestr = basestring
else:
    _basestr = str

def peg(s, r):
    p = _Peg(s)
    try:
        return p(r)
    except _UnexpectedError as e:
        offset = max(p._errors)
        err = p._errors[offset]
        raise ParseError(err.msg, s, offset, err.line, err.col)

class _UnexpectedError(RuntimeError):
    def __init__(self, state, expr):
        self.state = state
        self.expr = expr

class _PegState:
    def __init__(self, pos, line, col):
        self.pos = pos
        self.line = line
        self.col = col
        self.vars = {}
        self.commited = False

class _PegError:
    def __init__(self, msg, line, col):
        self.msg = msg
        self.line = line
        self.col = col

class _Peg:
    def __init__(self, s):
        self._s = s
        self._states = [_PegState(0, 1, 1)]
        self._errors = {}
        self._re_cache = {}

    def __call__(self, r, *args, **kw):
        if isinstance(r, _basestr):
            compiled = self._re_cache.get(r)
            if not compiled:
                compiled = re.compile(r)
                self._re_cache[r] = compiled
            st = self._states[-1]
            m = compiled.match(self._s[st.pos:])
            if not m:
                self.error(expr=r, err=kw.get('err'))

            ms = m.group(0)
            st.pos += len(ms)
            nl_pos = ms.rfind('\n')
            if nl_pos < 0:
                st.col += len(ms)
            else:
                st.col = len(ms) - nl_pos
                st.line += ms[:nl_pos].count('\n') + 1
            return ms
        else:
            kw.pop('err', None)
            return r(self, *args, **kw)

    def __repr__(self):
        pos = self._states[-1].pos
        vars = {}
        for st in self._states:
            vars.update(st.vars)
        return '_Peg(%r, %r)' % (self._s[:pos] + '*' + self._s[pos:], vars)

    @staticmethod
    def eof(p):
        if p._states[-1].pos != len(p._s):
            p.error()

    def error(self, err=None, expr=None):
        st = self._states[-1]
        if err is None:
            err = 'expected {!r}, found {!r}'.format(expr, self._s[st.pos:st.pos+4])
        self._errors[st.pos] = _PegError(err, st.line, st.col)
        raise _UnexpectedError(st, expr)

    def get(self, key, default=None):
        for state in self._states[::-1]:
            if key in state.vars:
                return state.vars[key][0]
        return default

    def set(self, key, value):
        self._states[-1].vars[key] = value, False

    def set_global(self, key, value):
        self._states[-1].vars[key] = value, True

    def opt(self, *args, **kw):
        with self:
            return self(*args, **kw)

    def not_(self, s, *args, **kw):
        with self:
            self(s)
            self.error()

    def __enter__(self):
        self._states[-1].committed = False
        self._states.append(_PegState(self._states[-1].pos, self._states[-1].line, self._states[-1].col))

    def __exit__(self, type, value, traceback):
        if type is None:
            self.commit()
        self._states.pop()
        return type == _UnexpectedError

    def commit(self):
        cur = self._states[-1]
        prev = self._states[-2]

        for key in cur.vars:
            val, g = cur.vars[key]
            if not g:
                continue
            if key in prev.vars:
                prev.vars[key] = val, prev.vars[key][1]
            else:
                prev.vars[key] = val, True

        prev.pos = cur.pos
        prev.line = cur.line
        prev.col = cur.col
        prev.committed = True

    def __nonzero__(self):
        return self._states[-1].committed

    __bool__ = __nonzero__
