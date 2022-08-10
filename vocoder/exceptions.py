class CompileException(Exception):
    ...


class CircularLexiconDefinitionError(CompileException):
    ...


class CircularAttributeDefinitionError(CompileException):
    ...


class UndefinedLexiconError(CompileException):
    ...


class InvalidGrammarArgument(CompileException):
    ...


class SyntaxError(CompileException):
    ...


class UndefinedAttributeError(CompileException):
    ...


class CircularNonterminalError(CompileException):
    ...


class UndefinedNonterminalError(CompileException):
    ...


class InvalidLexiconError(CompileException):
    ...


class ConfigError(CompileException):
    ...


class InvalidWordTransition(Exception):
    ...


class AttributeFailedError(Exception):
    ...
