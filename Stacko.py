#!/usr/bin/env python3
import sys
import re
import time
import random
import pygame

### Error reporting
def reportError(msg, emoji="😭"):
    print(f"\33[31mError\33[0m: \33[32m{msg}\33[0m {emoji}", file=sys.stderr)

ARGS = sys.argv

if len(ARGS) != 2:
    reportError("No file given")
    exit(1)

Path = ARGS[1]

Imports = []

def collectImports(FilePath):
    # Make sure file uses the '.stko' or '.stacko' extension
    if not (FilePath.endswith(".stko") or FilePath.endswith(".stacko")):
        reportError("Extension was not '.stko' or '.stacko'")
        exit(1)

    try:
        File = open(FilePath, "r")
        Words = File.read().split()
        File.close()
    except:
        reportError(f"Failed to open '{FilePath}'. No such file exists", "😐🔍")
        exit(1)
    
    for I, Word in enumerate(Words):
        # import <file path>
        if Word == "file":
            ImportPath = Words[I + 1]

            if ImportPath in Imports:
                continue

            Imports.append(ImportPath)
            collectImports(ImportPath)

def collectTokensFromFile(FilePath):
    # Make sure file uses the '.stko' or '.stacko' extension
    if not (FilePath.endswith(".stko") or FilePath.endswith(".stacko")):
        reportError("Extension was not '.stko' or '.stacko'")
        exit(1)

    try:
        File = open(FilePath, "r")
        ContentLines = File.readlines()
        File.close()
    except:
        reportError(f"Failed to open '{FilePath}'. No such file exists", "😐🔍")
        exit(1)

    Tokens = []

    # Collect tokens, discarding tokens after the '#' symbol (comments)
    for Line in ContentLines:
        LineTokens = re.findall("(?:\".*?\"|\S)+", Line)

        if len(LineTokens) > 0 and LineTokens[0] == "file":
            continue

        for Token in LineTokens:
            if Token.startswith("#"):
                break

            Tokens.append(Token)
    
    return Tokens

### Collect imports
collectImports(Path)
Imports.reverse()

Tokens = []

for ImportPath in Imports:
    Tokens += collectTokensFromFile(ImportPath)

Tokens += collectTokensFromFile(Path)
Tokens.reverse()

def isLiteral(Token):
    # String
    if Token.startswith('"') and Token.endswith('"'):
        return True
    # Number
    elif Token.lstrip("-+").replace(".", "", 1).isdigit():
        return True
    # Boolean
    elif Token == "Yes" or Token == "No":
        return True
    # Array
    elif Token == "[":
        return True

    return False

def parseLiteral(Token, Expr):
    # String
    if Token.startswith('"') and Token.endswith('"'):
        STR = Token[1:-1]
        STR = STR.replace("\\e", "\033")
        STR = STR.replace("\\n", "\n")
        STR = STR.replace("\\r", "\r")
        STR = STR.replace("\\t", "\t")
        return STR

    # Number
    elif Token.lstrip("-+").replace(".", "", 1).isdigit():
        NUMBER = float(Token)

        if not "." in Token:
            NUMBER = int(Token)

        return NUMBER

    # Yes
    elif Token == "Yes":
        return True

    # No
    elif Token == "No":
        return False

    # Array
    elif Token == "[":
        ARRAY = []
        for element in Expr:
            ARRAY.append(parseLiteral(element[0], element[1]))

        return ARRAY

    reportError(f"Failed to parse token '{Token}' as a literal")
    exit(1)

class Expression:
    name = ""
    bodies = []

    def __init__(self, b, n = ""):
        self.name = n
        self.bodies = b

def expectToken(Val):
    if len(Tokens) == 0:
        reportError(f"Expected '{Val}', found nothing instead", "😐🔍")
        exit(1)
    
    TOKEN = Tokens.pop()
    if TOKEN != Val:
        reportError(f"Expected '{Val}', found {TOKEN} instead", "😐🔍")
        exit(1)

def generateBlocksFromTokens():
    Block = []

    while len(Tokens) > 0 and Tokens[-1] != "}" and Tokens[-1] != "]":
        Token = Tokens.pop()

        # If expressions
        if Token == "if":
            # if { ... } else { ... }

            expectToken("{")
            IfBlock = (Token, Expression([generateBlocksFromTokens()]))
            expectToken("}")

            if len(Tokens) > 0 and Tokens[-1] == "else":
                Tokens.pop()    # Skip 'else' keyword

                expectToken("{")
                IfBlock[1].bodies.append(generateBlocksFromTokens())
                expectToken("}")
            
            Block.append(IfBlock)

        # While expressions
        elif Token == "while":
            # while { ... }

            expectToken("{")
            Block.append((Token, Expression([generateBlocksFromTokens()])))
            expectToken("}")
        
        # Functions
        elif Token == "fnn":
            # fnn <name> { ... }
            
            NAME = Tokens.pop()
            expectToken("{")
            Block.append((Token, Expression([generateBlocksFromTokens()], NAME)))
            expectToken("}")

        # Array
        elif Token == "[":
            # [ ... ]

            Block.append(("[", generateBlocksFromTokens()))
            expectToken("]")

        # Constants
        elif Token == "const":
            # const <name>

            NAME = Tokens.pop()
            Block.append((Token, Expression(None, NAME)))

        # Variable declaration
        elif Token == "var": 
            # var <name>

            NAME = Tokens.pop()
            Block.append((Token, Expression(None, NAME)))
        
        # Set variable
        elif Token == "set":
            # set <name>

            NAME = Tokens.pop()
            Block.append((Token, Expression(None, NAME)))

        # Normal tokens
        else:
            Block.append((Token, None))
    
    return Block

Blocks = generateBlocksFromTokens()

### Interpreting
def printValue(val, end="\r\n"):
    if type(val) is bool:
        if val == True:
            print("Yes", end=end)
        elif val == False:
            print("No", end=end)
    elif type(val) is list:
        print("[ ", end="")
        for elem in val:
            printValue(elem[0] + " ", end="")
        print("]")
    else:
        print(val, end=end)

def assertIdenticalTypes(a, b):
    if not (type(a) is type(b)):
        reportError(f"Type '{type(a).__name__}' and '{type(b).__name__}' cannot be used together in an operation.")
        exit(1)

def assertType(a, t):
    if not (type(a) is t):
        reportError(f"Type '{type(a).__name__}' and '{t.__name__}' cannot be used together in an operation.")
        exit(1)

Stack = []

def assertMinStackSize(minSize):
    if len(Stack) < minSize:
        reportError(f"Expected at least {minSize} item(s) on stack to perform operation. Found {len(Stack)} instead.")
        exit(1)

Functions = []

def doesFunctionExist(name):
    for Func in Functions:
        if Func[0] == name:
            return True
    
    return False

def getFunctionWithName(name):
    for Func in Functions:
        if Func[0] == name:
            return Func
    
    return None

Constants = []

def doesConstantExist(name):
    for Const in Constants:
        if Const[0] == name:
            return True
    
    return False

def getConstantWithName(name):
    for Const in Constants:
        if Const[0] == name:
            return Const
    
    return None

Variables = []
Window = None

def doesVariableExist(name):
    for Var in Variables:
        if Var[0] == name:
            return True
    
    return False

def getVariableWithName(name):
    for Var in Variables:
        if Var[0] == name:
            return Var
    
    return None

def setVariableWithName(name, val):
    for I, Var in enumerate(Variables):
        if Var[0] == name:
            Variables[I] = (name, val)

def doesNameExist(name):
    if getFunctionWithName(name) != None:
        return True
    if getConstantWithName(name) != None:
        return True
    if getVariableWithName(name) != None:
        return True
    
    return False

def interpretBlocks(Blocks):
    global Window

    for Token, Expr in Blocks:
        # Literals
        if isLiteral(Token):
            Stack.append(parseLiteral(Token, Expr))

        ### Type-casting

        # toNum
        elif Token == "toNum":
            assertMinStackSize(1)
            VAL = Stack.pop()
            Stack.append(float(VAL))

        # toString
        elif Token == "toString":
            assertMinStackSize(1)
            VAL = Stack.pop()

            if type(VAL) is bool:
                if VAL == True:
                    Stack.append("Yes")
                elif VAL == False:
                    Stack.append("No")
            else:
                Stack.append(str(VAL))
        
        # toBool
        elif Token == "toBool":
            assertMinStackSize(1)
            VAL = Stack.pop()

            if type(VAL) is str:
                if VAL == "Yes":
                    Stack.append(True)
                elif VAL == "No":
                    Stack.append(False)
            else:
                Stack.append(bool(VAL))

            Stack.append(bool(VAL))

        ### Arithmetic operations

        # Addition
        elif Token == "+":
            assertMinStackSize(2)
            A = Stack.pop()
            B = Stack.pop()
            assertIdenticalTypes(A, B)

            RESULT = B + A
            Stack.append(RESULT)

        # Subtraction
        elif Token == "-":
            assertMinStackSize(2)
            A = Stack.pop()
            B = Stack.pop()
            assertIdenticalTypes(A, B)

            RESULT = B - A
            Stack.append(RESULT)
        
        # Multiplication
        elif Token == "*":
            assertMinStackSize(2)
            A = Stack.pop()
            B = Stack.pop()
            assertIdenticalTypes(A, B)

            RESULT = B * A
            Stack.append(RESULT)

        # Division
        elif Token == "/":
            assertMinStackSize(2)
            A = Stack.pop()
            B = Stack.pop()
            assertIdenticalTypes(A, B)

            RESULT = B / A
            Stack.append(RESULT)

        # Modulo
        elif Token == "%":
            assertMinStackSize(2)
            A = Stack.pop()
            B = Stack.pop()
            assertIdenticalTypes(A, B)

            RESULT = B % A
            Stack.append(RESULT)

        # Equality
        elif Token == "=":
            assertMinStackSize(2)
            A = Stack.pop()
            B = Stack.pop()
            assertIdenticalTypes(A, B)

            RESULT = (B == A)
            Stack.append(RESULT)

        # Greater than
        elif Token == ">":
            assertMinStackSize(2)
            A = Stack.pop()
            assertType(A, float)
            B = Stack.pop()
            assertType(B, float)

            RESULT = B > A
            Stack.append(RESULT)

        # Less than
        elif Token == "<":
            assertMinStackSize(2)
            A = Stack.pop()
            assertType(A, float)
            B = Stack.pop()
            assertType(B, float)

            RESULT = B < A
            Stack.append(RESULT)

        # Greater than or equal to
        elif Token == ">=":
            assertMinStackSize(2)
            A = Stack.pop()
            assertType(A, float)
            B = Stack.pop()
            assertType(B, float)

            RESULT = B >= A
            Stack.append(RESULT)

        # Less than or equal to
        elif Token == "<=":
            assertMinStackSize(2)
            A = Stack.pop()
            assertType(A, float)
            B = Stack.pop()
            assertType(B, float)

            RESULT = B <= A
            Stack.append(RESULT)

        # Equality
        elif Token == "not":
            assertMinStackSize(1)
            COND = Stack.pop()
            assertType(COND, bool)

            Stack.append(not COND)
        
        # Duplicate
        elif Token == "dup":
            assertMinStackSize(1)
            VAL = Stack[-1]
            Stack.append(VAL)

        # Pop
        elif Token == "pop":
            assertMinStackSize(1)
            Stack.pop()

        # Keyword 'printLine'
        elif Token == "printLine":
            assertMinStackSize(1)
            printValue(Stack.pop())

        # Keyword 'print'
        elif Token == "print":
            assertMinStackSize(1)
            printValue(Stack.pop(), end="")

        # Keyword 'readLine'
        elif Token == "readLine":
            LINE = input()
            Stack.append(LINE)
        
        # Keyowrd 'exit'
        elif Token == "exit":
            assertMinStackSize(1)
            RETURN_CODE = Stack.pop()
            assertType(RETURN_CODE, int)
            exit(RETURN_CODE)

        # Keyword 'waitMore'
        elif Token == "waitMore":
            TIME = Stack.pop()
            assertType(TIME, float)
            time.sleep(TIME)

        ### Assertions
        
        # Keyword 'assert'
        elif Token == "assert":
            assertMinStackSize(1)
            VAL = Stack.pop()
            assertType(VAL, bool)
            
            if not VAL:
                reportError(f"Assertion failed.")
                exit(2)
        
        # Keyword 'assertEqual'
        elif Token == "assertEqual":
            assertMinStackSize(2)
            A = Stack.pop()
            B = Stack.pop()
            assertIdenticalTypes(A, B)
            
            if A != B:
                reportError(f"Assertion failed. Values were not equal.")
                exit(2)

        # Keyword 'assertNotEqual'
        elif Token == "assertNotEqual":
            assertMinStackSize(2)
            A = Stack.pop()
            B = Stack.pop()
            assertIdenticalTypes(A, B)
            
            if A == B:
                reportError(f"Assertion failed. Values were equal.")
                exit(2)

        # Keyword 'if'
        elif Token == "if":
            assertMinStackSize(1)
            COND = Stack.pop()
            assertType(COND, bool)

            if COND == True:
                interpretBlocks(Expr.bodies[0])
            elif len(Expr.bodies) == 2:
                interpretBlocks(Expr.bodies[1])

        # Keyword 'while'
        elif Token == "while":
            while True:
                assertMinStackSize(1)
                COND = Stack.pop()
                assertType(COND, bool)

                if not COND:
                    break
                
                interpretBlocks(Expr.bodies[0])
        
        # Keyword 'fnn'
        elif Token == "fnn":
            NAME = Expr.name
            BODY = Expr.bodies[0]
            if doesNameExist(NAME):
                reportError(f"Name '{NAME}' already exists elsewhere.")
                exit(1)
            
            Functions.append((NAME, BODY))

        # Keyword 'const'
        elif Token == "const":
            assertMinStackSize(1)
            NAME = Expr.name

            if doesNameExist(NAME):
                reportError(f"Name '{NAME}' already exists elsewhere.")
                exit(1)
            
            VAL = Stack.pop()
            Constants.append((NAME, VAL))
        
        # Keyword 'var'
        elif Token == "var":
            NAME = Expr.name

            if doesNameExist(NAME):
                reportError(f"The variable '{NAME}' already exists.")
                exit(1)
            
            Variables.append((NAME, None))
        
        # Keyword 'set'
        elif Token == "set":
            assertMinStackSize(1)
            NAME = Expr.name

            if not doesVariableExist(NAME):
                reportError(f"The variable '{NAME}' does not exist.", "😐🔍")
                exit(1)
            
            VAL = Stack.pop()
            setVariableWithName(NAME, VAL)
        
        # Keyword 'random'
        elif Token == "random":
            VAL = random.randint(0, sys.maxsize)
            Stack.append(VAL)
        
        # Keyword 'getElement'
        elif Token == "getElement":
            assertMinStackSize(2)

            INDEX = Stack.pop()
            assertType(INDEX, int)
            LIST = Stack.pop()
            assertType(LIST, list)

            ELEMENT = LIST[int(INDEX)]
            Stack.append(ELEMENT)

        #### PYGAME KEYWORDS ####

        # createWindow
        elif Token == "createWindow":
            pygame.init()
            Window = pygame.display.set_mode((640, 480))
        
        # closeWindow
        elif Token == "closeWindow":
            pygame.quit()
        
        elif Token == "windowRunning":
            RESULT = True

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    RESULT = (False)

            Stack.append(RESULT)
        
        elif Token == "setWindowColor":
            assertMinStackSize(1)
            COLOR = Stack.pop()
            assertType(COLOR, str)
            Window.fill(pygame.Color(COLOR))
        
        elif Token == "windowUpdate":
            pygame.display.flip()

        # Function
        elif doesFunctionExist(Token):
            FUNC = getFunctionWithName(Token)
            interpretBlocks(FUNC[1])
        
        # Constant
        elif doesConstantExist(Token):
            CONST = getConstantWithName(Token)
            Stack.append(CONST[1])

        # Variable
        elif doesVariableExist(Token):
            VAR = getVariableWithName(Token)
            Stack.append(VAR[1])

        # Unknown token
        else:
            reportError(f"Unknown token '{Token}' found in '{Path}'.")
            exit(1)

interpretBlocks(Blocks)
