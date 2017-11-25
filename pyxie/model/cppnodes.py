#
# Copyright 2016 Michael Sparks
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from __future__ import print_function
from __future__ import absolute_import

import pyxie.codegen.simple_cpp
from pyxie.codegen.profiles import cpp_templates

from pyxie.model.functions import builtins

import pprint

unique_id = 0 # FIXME: Naming - Used to generate unique ids within for statements. 
              # FIXME: Implies there should be a better way of doing this.

def todo(*args):
    print("TODO", " ".join([repr(x) for x in args]))

def get_blank_line():
    return pyxie.codegen.simple_cpp.get_blank_line()

def Print(*args):
    return pyxie.codegen.simple_cpp.Print(*args)

class CppNode(object):
    pass


def mkStatement(statement_spec):
    ss = statement_spec
    if ss[0] == "assignment":
        return CppAssignment( ss[1], ss[3], ss[2])

    elif ss[0] == "print_statement":
        return CppPrintStatement(*statement_spec[1:])

    elif ss[0] == "expression_statement":
        return CppExpressionStatement(*statement_spec[1:])

    elif ss[0] == "while_statement":
        return CppWhileStatement(*statement_spec[1:])

    elif ss[0] == "for_statement":
        return CppForStatement(*statement_spec[1:])

    elif ss[0] == "if_statement":
        if len(ss) == 3:
            return CppIfStatement(ss[1], ss[2])
        if len(ss) == 4:
            return CppIfStatement(ss[1], ss[2], ss[3])
        raise NotImplementedError("Have not yet implemented else clauses...")

    elif ss[0] == "pass_statement":
        return CppEmptyStatement()

    elif ss[0] == "break_statement":
        return CppBreakStatement()

    elif ss[0] == "continue_statement":
        return CppContinueStatement()

    else:
        print("Unknown statement type", ss[0], ss)



class CppProgram(CppNode):
    def __init__(self):
        self.includes = []
        self.main_cframe = CppFrame()
        self.name = ""

    @classmethod
    def fromiinodes(klass, iiprogram):
        program = klass()
        program.name = iiprogram.name
        program.includes = iiprogram.includes

        for identifier in iiprogram.global_identifiers:
            program.main_cframe.identifiers.append(CppIdentifier(identifier[1], identifier[2]))

        for statement in iiprogram.statements:
            conc_statement = mkStatement(statement)
            program.main_cframe.statements.append(conc_statement)

        return program

    def generate(self, profile = "default"):
        print("BUILDING FOR PROFILE", profile)
        frame_lines = self.main_cframe.concrete()
        seen = {}
        for include in self.includes:
            if not seen.get(include, False):
                # Only output each include once
                Print( "#include "+ include )
                seen[include] = True

        print_def = cpp_templates.get(profile, cpp_templates.get("default"))
        frame_text = "\n".join(["   "+line for line in frame_lines])

        Print(print_def % { "FRAME_TEXT": frame_text } )

    def json(self):
        return { "PROGRAM": {"name": self.name,
                             "includes" : self.includes,
                             "main": self.main_cframe.json()}
               }


class CppFrame(CppNode):
    def __init__(self):
        self.identifiers = []
        self.statements = []

    def json(self):
        for y in self.statements:
            Print(y)
        return {"c_frame": {"identifiers" : [ x.json() for x in self.identifiers ],
                            "statements" : [y.json() for y in self.statements ] }
               }

    def concrete(self):
        block = []
        for identifier in self.identifiers:
            decl_code = identifier.decl_code()
            block.append(decl_code + ";")

        block.append(get_blank_line() )
        for statement in self.statements:
            if statement:
                code = statement.code()
                if code is None:
                    print("STATEMENT IS None, WHY?", statement)
                block.append(code + ";")
        return block


class CppIdentifier(CppNode):
    def __init__(self, ctype, name):
        self.ctype = ctype
        self.name = name

    def json(self):
        return ["identifier", self.ctype, self.name ]

    def decl_code(self):
        return self.ctype + " " + self.name


class CppAssignment(CppNode):
    def __init__(self, lvalue, rvalue, assigntype="="):
        self.lvalue = lvalue
        self.rvalue = rvalue
        self.assigntype = assigntype

    def json(self):
        return ["assignment", self.lvalue, self.assigntype, self.rvalue ]

    def code(self):
        print(self.rvalue)
        if type(self.rvalue) == list:
            print("Aha!",self.rvalue)
            crvalue = CppArgumentList(self.rvalue)
            crvalue = crvalue.code()
            print("AHA!", crvalue)
        else:
            crvalue = self.rvalue
        return self.lvalue + " "+self.assigntype+" " + crvalue


# A pass statement is not a commented out statement.
#
# By that this:
# while True: pass
#
# Is equivalent to while(true);
# As opposed to while(true);
#
# So that's why this returns ";" not ""
class CppEmptyStatement(CppNode):
    def json(self):
        return ["pass_statement"]

    def code(self):
        return ";"


class CppBreakStatement(CppNode):
    def json(self):
        return ["break_statement"]

    def code(self):
        return "break"


class CppContinueStatement(CppNode):
    def json(self):
        return ["continue_statement"]

    def code(self):
        return "continue"




class CppFunctionCall(CppNode):
    def __init__(self, identifier, args):
        self.args = args
        self.identifier = identifier
        self.arg_list = CppArgumentList(*args)

    def json(self):
        return ["function_call", self.identifier ] + self.arg_list.json()

    def code(self):
        identifier = self.identifier[1]

        if self.identifier[0] == "attributeaccess":
            expression = self.identifier[1]
            attribute = self.identifier[2]

            c_expression = "(" + expression[1] + ")"
            c_attribute = attribute[1]

            identifier = c_expression + "." + c_attribute

        else:
            identifier = self.identifier[1]

            # FUDGE: The following would need to be profile specific
            #
            # It probably also needs reviewing/revising later on
            if identifier == "print":
                X = CppPrintStatement(*self.args)
                return X.code()

        arglist = ", ".join(self.arg_list.code_list())
        return identifier + "(" + arglist + ")"


class CppArgumentList(CppNode):
    def __init__(self, *args):
        self.args = args

    def json(self):
        return list(self.args[:])

    def code_op_F(self, arg):
        if arg[1] == "plus": return "+"
        if arg[1] == "minus": return "-"
        if arg[1] == "times": return "*"
        if arg[1] == "divide": return "/"
        if arg[1] == "boolean_or": return " || "
        if arg[1] == "boolean_and": return " && "
        if arg[1] == "boolean_not": return " ! "

        if arg[1] in ["<", ">", "==", ">=", "<=", "!="]:
            return arg[1]

        if arg[1] == "<>": return "!="

        return None

    def code_op(self,arg):
        c_op = self.code_op_F(arg)
        if c_op:

            if len(arg) == 4:
                arg1 = arg[2]
                arg2 = arg[3]
                # We would like to try to assert here that the values on both sides
                # are integers, but at present we cannot do that, since we use too simplistic
                # a structure. If I remove that constraint, we can generate more code.
                # But we will need to revisit this.
                lit_arg1 = self.code_arg(arg1)
                lit_arg2 = self.code_arg(arg2)

                result = "(" + lit_arg1 + c_op + lit_arg2 + ")"
                return result
            if len(arg) == 3:
                arg1 = arg[2]
                # We would like to try to assert here that the values on both sides
                # are integers, but at present we cannot do that, since we use too simplistic
                # a structure. If I remove that constraint, we can generate more code.
                # But we will need to revisit this.
                lit_arg1 = self.code_arg(arg1)

                result = "(" + c_op + lit_arg1 + ")"
                return result

        todo("Handle code ops for anything other than plus/int,int")
        raise NotImplementedError("Handle code ops for anything other than plus/int,int" + repr(arg))


    def code_arg(self, arg):
        if arg[0] == "identifier":
            return arg[1]
        elif arg[0] == "integer":
            r = repr(arg[1])
            if arg[1]<0:
                r = "(" + r + ")"
            return r
        elif arg[0] == "string":
            carg = arg[1].replace('"', '\\"')
            return '"' + carg + '"' # Force double quotes
        elif arg[0] == "double":
            return repr(arg[1])
        elif arg[0] == "boolean":
            return arg[1]
        elif arg[0] == "op":
            return self.code_op(arg)
        elif arg[0] == "function_call":
            code_gen = CppFunctionCall(arg[1],arg[2])
            return code_gen.code()
            print("We don't know how to generate code for function calls yet", arg)
            return ""

        todo("Handle print value types that are more than the basic types", arg[0])
        raise NotImplementedError("Handle print value types that are more than the basic types" + repr(arg))

    def code_list(self):
        cargs = []
        for arg in self.args:
            c_str = self.code_arg(arg)
            cargs.append(c_str)

        return cargs

    def code(self):
        return ",".join(self.code_list())


class CppExpressionStatement(CppNode):
    def __init__(self, expression):
        self.expression = expression

    def json(self):
        return ["expression_statement", self.expression ]

    def code(self):
        print(self.expression)
        if type(self.expression) == list:
            cvalue = CppArgumentList(self.expression)
            cvalue = cvalue.code()
        else:
            raise Exception("Fail to understand how to generate code for %s" % repr(self.expression) )

        return cvalue


class CppPrintStatement(CppNode):
    def __init__(self, *args):
        self.args = args
        self.arg_list = CppArgumentList(*args)

    def json(self):
        return ["print_statement" ] + self.arg_list.json()

    def code(self):
        return "( cout << " + " << \" \" << ".join(self.arg_list.code_list()) + " << endl )"


class CppWhileStatement(CppNode):
    def __init__(self, condition, *statements):
        self.raw_condition = condition
        self.raw_statements = list(statements)
        self.block_cframe = CppFrame()

        for statement in self.raw_statements:
            conc_statement = mkStatement(statement)
            self.block_cframe.statements.append(conc_statement)

    def json(self):
        return ["while_statement", self.raw_condition] + self.raw_statements

    def code(self):
        code = "while"
        code += "("
        code += CppArgumentList(self.raw_condition).code()
        code += ") {"
        code += "\n".join( self.block_cframe.concrete() )
        code += "}"
        return code


class CppForStatement(CppNode):
    def __init__(self, identifier, iterable, statements, for_statement_pynode):
        self.raw_identifier = identifier
        self.raw_iterable = iterable
        self.raw_statements = list(statements)
        self.block_cframe = CppFrame()
        self.for_statement_pynode = for_statement_pynode

        for statement in self.raw_statements:
            conc_statement = mkStatement(statement)
            self.block_cframe.statements.append(conc_statement)

    def json(self):
        return ["for_statement", self.raw_condition, self.raw_iterable, self.raw_statements ]

    def code(self):
        #
        # The following is the sort of code we want to generate inline.
        # This actually implements what we're after.
        # However it requires some declarations to be in place really of the the find variables kind
        # That said, C++ allows inline delcarations like this (for good or ill), so maybe just do
        # this in the first instance, and leave improvements for refactoring???
        #
        # Actually this discussion is useful, but it turns out to allow nested generator usage
        # ie for x in range(5): for y in range(x): print x,y
        # It requires this to be done closer to what could be viewed as "properly"
        #
#            %(ITERATOR_TYPE)s %(ITERATOR_NAME)s = %(ITERATOR_EXPRESSION)s;
        template = """
            %(ITERATOR_NAME)s = %(ITERATOR_EXPRESSION)s;
            while (true) {
                %(IDENTIFIER)s = %(ITERATOR_NAME)s.next();
                if (%(ITERATOR_NAME)s.completed())
                    break;

                %(BODY)s // Itself uses %(IDENTIFIER)s
            }
        """
        global unique_id
        unique_id = unique_id+1

        iterator_ctype = "range"
        iterator_expression = self.raw_iterable ## NOTE THIS RESULTS IN ['iterate_over', ['function_call', ['identifier', 'range'], [['integer', 5]]]]- so that needs work

        print("OK, USE THIS THEN", self.for_statement_pynode.expression.ivalue_name)
        iterator_name = self.for_statement_pynode.expression.ivalue_name

        if self.raw_iterable[0] == "iterator":
            iterable = self.raw_iterable[1]
            if iterable[0] == "function_call":
                assert iterable[1][0] == "identifier"
                identifier = iterable[1][1]
                if identifier in builtins:
                    print("YAY")
                    pprint.pprint( builtins[identifier] )
                    iterator_ctype = builtins[identifier]["iterator_ctype"]
                    print("iterator_name -- ", iterator_ctype)
                    print("YAY")

                print(iterable)
                fcall = CppFunctionCall(iterable[1],iterable[2])
                fcall_code = fcall.code()
                iterator_expression = fcall_code

        template_args =  { "ITERATOR_TYPE": iterator_ctype,
                           "ITERATOR_EXPRESSION": iterator_expression,
                           "ITERATOR_NAME": iterator_name,
                           "UNIQIFIER":repr(unique_id),
                           "IDENTIFIER": self.raw_identifier,
                           "BODY": "\n".join( self.block_cframe.concrete() )
                         }



        print("=== template args =================================================")
        pprint.pprint (template_args )
        print("--- template args -------------------------------------------------")
        if self.for_statement_pynode.expression.isiterator:
            identifier = self.for_statement_pynode.identifier
            print(identifier.get_type())
        print("=== end extractable template args =================================")
        print(template % template_args)

        print("----------------------------------------------------------")
        print(dir(self.for_statement_pynode))
        print(repr(self.for_statement_pynode))
        print("----------------------------------------------------------")
#        raise NotImplementedError("Haven't finished implementing CppForStatement yet...")
        code = template % template_args

        print("CODE", code)

        return code


class CppIfStatement(CppNode):
    def __init__(self, condition, statements, extended_clause=None):
        self.raw_condition = condition
        self.raw_statements = list(statements)
        self.extended_clause = extended_clause

        self.block_cframe = CppFrame()
        for statement in self.raw_statements:
            conc_statement = mkStatement(statement)
            self.block_cframe.statements.append(conc_statement)

    def json(self):
        result = ["if_statement", self.raw_condition, self.raw_statements ]
        if self.extended_clause is not None:
            result.append(extended_clauses.json())

    def code(self):
        extended_clauses_code = None
        condition_code = CppArgumentList(self.raw_condition).code()
        block_code = "\n".join( self.block_cframe.concrete() )
        if self.extended_clause:
            if self.extended_clause[0] == "elif_clause":
                print(self.extended_clause[0])
                condition = self.extended_clause[1]
                statements =  self.extended_clause[2]
                if len(self.extended_clause) == 4:
                    extended_sub_clause =  self.extended_clause[3]
                    extended_clauses_code = CppElseIfClause( condition, statements, extended_sub_clause ).code()
                else:
                    extended_clauses_code = CppElseIfClause( condition, statements ).code()

            if self.extended_clause[0] == "else_clause":
                print("***************************************************")
                print(self.extended_clause[0])
                statements =  self.extended_clause[1]
                extended_clauses_code = CppElseClause( statements ).code()

        code = "if ( %s ) { %s } " % (condition_code, block_code )
        if extended_clauses_code:
            code = code + extended_clauses_code
        return code


class CppElseIfClause(CppNode):
    def __init__(self, condition, statements, extended_clause=None):
        self.raw_condition = condition
        self.raw_statements = list(statements)
        self.extended_clause = extended_clause

        self.block_cframe = CppFrame()
        for statement in self.raw_statements:
            conc_statement = mkStatement(statement)
            self.block_cframe.statements.append(conc_statement)

    def json(self):
        result = ["elif_clause", self.raw_condition, self.raw_statements ]
        if self.extended_clause is not None:
            result.append(extended_clause.json())

    def code(self):
        extended_clauses_code = None
        condition_code = CppArgumentList(self.raw_condition).code()
        block_code = "\n".join( self.block_cframe.concrete() )
        if self.extended_clause:
            if self.extended_clause[0] == "elif_clause":
                print("***************************************************")
                print(self.extended_clause[0])
                condition = self.extended_clause[1]
                statements =  self.extended_clause[2]

                if len(self.extended_clause) == 4:
                    extended_sub_clause =  self.extended_clause[3]
                    extended_clauses_code = CppElseIfClause( condition, statements, extended_sub_clause ).code()
                else:
                    extended_clauses_code = CppElseIfClause( condition, statements ).code()


            if self.extended_clause[0] == "else_clause":
                print("***************************************************")
                print(self.extended_clause[0])
                statements =  self.extended_clause[1]
                extended_clauses_code = CppElseClause( statements ).code()

        code = "else if ( %s ) { %s } " % (condition_code, block_code )
        if extended_clauses_code:
            code = code + extended_clauses_code
        return code


class CppElseClause(CppNode):
    def __init__(self, statements):
        self.raw_statements = list(statements)

        self.block_cframe = CppFrame()
        for statement in self.raw_statements:
            conc_statement = mkStatement(statement)
            self.block_cframe.statements.append(conc_statement)

    def json(self):
        result = ["elif_clause", self.raw_statements ]

    def code(self):
        extended_clauses_code = None
        block_code = "\n".join( self.block_cframe.concrete() )

        code = "else { %s } " % (block_code, )

        return code


#__all__ = [ "CppNode", "CppProgram", "CppFrame", "CppIdentifier",
            #"CppAssignment", "CppEmptyStatement", "CppBreakStatement",
            #"CppFunctionCall", "CppArgumentList", "CppExpressionStatement",
            #"CppPrintStatement", "CppWhileStatement", "CppForStatement",
            #"CppIfStatement", "CppElseIfClause", "CppElseClause"
          #]

