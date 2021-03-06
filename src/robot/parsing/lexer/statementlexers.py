#  Copyright 2008-2015 Nokia Networks
#  Copyright 2016-     Robot Framework Foundation
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from robot.variables import is_dict_var, is_var, search_variable
from robot.utils import normalize_whitespace, split_from_equals

from .tokens import Token


class Lexer(object):
    """Base class for lexers."""

    @classmethod
    def handles(cls, statement):
        return True

    def accepts_more(self, statement):
        raise NotImplementedError

    def input(self, statement):
        raise NotImplementedError

    def lex(self, ctx):
        raise NotImplementedError


class StatementLexer(Lexer):
    token_type = None

    def __init__(self, statement=None):
        self.statement = statement

    def accepts_more(self, statement):
        return False

    def input(self, statement):
        self.statement = statement

    def lex(self, ctx):
        for token in self.statement:
            token.type = self.token_type


class SectionHeaderLexer(StatementLexer):

    @classmethod
    def handles(cls, statement):
        return statement[0].value.startswith('*')


class SettingSectionHeaderLexer(SectionHeaderLexer):
    token_type = Token.SETTING_HEADER


class VariableSectionHeaderLexer(SectionHeaderLexer):
    token_type = Token.VARIABLE_HEADER


class TestCaseSectionHeaderLexer(SectionHeaderLexer):
    token_type = Token.TESTCASE_HEADER


class KeywordSectionHeaderLexer(SectionHeaderLexer):
    token_type = Token.KEYWORD_HEADER


class CommentSectionHeaderLexer(SectionHeaderLexer):
    token_type = Token.COMMENT_HEADER


class ErrorSectionHeaderLexer(SectionHeaderLexer):

    def lex(self, ctx):
        header = self.statement[0]
        header.set_error(
            "Unrecognized section header '%s'. Available headers for data: "
            "'Setting(s)', 'Variable(s)', 'Test Case(s)', 'Task(s)' and "
            "'Keyword(s)'. Use 'Comment(s)' to embedded additional data."
            % header.value.strip('* ').strip()
        )
        for token in self.statement[1:]:
            token.type = Token.COMMENT


class CommentLexer(StatementLexer):
    token_type = Token.COMMENT


class SettingLexer(StatementLexer):

    def lex(self, ctx):
        ctx.lex_setting(self.statement)


class TestOrKeywordSettingLexer(SettingLexer):

    @classmethod
    def handles(cls, statement):
        marker = statement[0].value
        return marker and marker[0] == '[' and marker[-1] == ']'


class VariableLexer(StatementLexer):

    def lex(self, ctx):
        name = self.statement[0]
        values = self.statement[1:]
        if is_var(name.value, allow_assign_mark=True):
            self._valid_variable(name, values)
        else:
            self._invalid_variable(name, values)
        if is_dict_var(name.value, allow_assign_mark=True):
            self._validate_dict_items(values)

    def _valid_variable(self, name, values):
        name.type = Token.VARIABLE
        for token in values:
            token.type = Token.ARGUMENT

    def _invalid_variable(self, name, values):
        name.set_error("Invalid variable name '%s'." % name.value)
        for token in values:
            token.type = Token.COMMENT

    def _validate_dict_items(self, values):
        for token in values:
            if not self._is_valid_dict_item(token.value):
                token.set_error(
                    "Invalid dictionary variable item '%s'. "
                    "Items must use 'name=value' syntax or be dictionary "
                    "variables themselves." % token.value
                )

    def _is_valid_dict_item(self, item):
        name, value = split_from_equals(item)
        return value is not None or search_variable(item).is_dict_variable


class KeywordCallLexer(StatementLexer):

    def lex(self, ctx):
        if ctx.template_set:
            self._lex_as_template()
        else:
            self._lex_as_keyword_call()

    def _lex_as_template(self):
        for token in self.statement:
            token.type = Token.ARGUMENT

    def _lex_as_keyword_call(self):
        keyword_seen = False
        for token in self.statement:
            if keyword_seen:
                token.type = Token.ARGUMENT
            elif is_var(token.value, allow_assign_mark=True):
                token.type = Token.ASSIGN
            else:
                token.type = Token.KEYWORD
                keyword_seen = True


class ForLoopHeaderLexer(StatementLexer):
    separators = ('IN', 'IN RANGE', 'IN ENUMERATE', 'IN ZIP')

    @classmethod
    def handles(cls, statement):
        marker = statement[0].value
        return (marker == 'FOR' or
                marker.startswith(':') and
                marker.replace(':', '').replace(' ', '').upper() == 'FOR')

    def lex(self, ctx):
        separator_seen = False
        variable_seen = False
        self.statement[0].type = Token.FOR
        for token in self.statement[1:]:
            if separator_seen:
                token.type = Token.ARGUMENT
            elif variable_seen and self._is_separator(token.value):
                token.type = Token.FOR_SEPARATOR
                separator_seen = True
            else:
                token.type = Token.VARIABLE
                variable_seen = True

    def _is_separator(self, value):
        return normalize_whitespace(value) in self.separators


class EndLexer(StatementLexer):

    @classmethod
    def handles(cls, statement):
        return len(statement) == 1 and statement[0].value == 'END'

    def lex(self, ctx):
        self.statement[0].type = Token.END
