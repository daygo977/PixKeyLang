import sys
import math
import os
from os.path import dirname, join, splitext
from textx import metamodel_from_file
from textx.export import model_export
from PIL import Image

# Load grammar from metamodel from file
# Parse the input file into model object
PixKey_mm = metamodel_from_file('PixKeyLang.tx')

# RBG values for pixels when keywords are in source code
TOKEN_COLOR_MAP = {
    "let":(200,50,50), "print":(200,100,50), "if":(200,150,50),
    "then":(200,200,50), "else":(200,250,50), "while":(150,250,75),
    "for":(100,250,100), "do":(100,200,200), "end":(50,250,150),
    "to":(150,200,120), "in":(120,200,150),
    "+":(255,0,0), "-":(255,65,0), "*":(255,130,0), "//":(255,200,0),
    "/":(255,255,0), "%":(200,255,0), "^":(130,255,0), '(':(65,255,0),
    ')':(0,255,0), "<=":(0,255,65), ">=":(0,255,130), "<":(0,255,190),
    ">":(0,255,255), "==":(0,190,255), "!=":(0,130,255), "=":(50,65,255),
    '"':(255,195,255), ':':(123,222,45), ',':(45,123,222), ';':(222,45,123),
    '.':(100,100,100), '[':(200,50,200), ']':(200,77,50), '{':(50,200,200),
    '}':(200,87,100)
}

# RGB values for a-z and A-Z characters
for i, ch in enumerate("abcdefghijklmnopqrstuvwxyz"):
    TOKEN_COLOR_MAP[ch] = (i*4,100,200)
for i, CH in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    TOKEN_COLOR_MAP[CH] = (150,100,i*4)
#RGB values for 0-9 int
for i, j in enumerate("0123456789"):
    TOKEN_COLOR_MAP[j] = (200, i*24, 0)
#For spaces and line skips
TOKEN_COLOR_MAP[" "] = (199,199,199)
TOKEN_COLOR_MAP["\n"] = (198,198,255)

# Interpreter class
class PixKeyLang:
    # Initialize dictionary for variables
    def __init__(self):
        self.variables = {}
    
    #Goes through each command and passes it to second interprter.
    def interpret(self, model):
        for cmd in model.commands:
            self.interpret_indv(cmd)

    # based on the command type it gets handled
    def interpret_indv(self, model):
        name = model.__class__.__name__
        # Gets variable name and value and stores it in dict
        if name == "VarDeclare":
            varname = model.name
            val = self.eval_expr(model.value)
            self.variables[varname] = val

        # Reassignes variables with new values, has to be defined
        elif name == 'Assignment':
            varname = model.var
            if varname not in self.variables:
                raise NameError(f"Variable '{varname}' is not defined.")
            self.variables[varname] = self.eval_expr(model.value)

        # Passes command to expr_eval to determine if its a variable, str, or int
        # Then prints it
        elif name == "Print":
            val = self.eval_expr(model.value)
            print(val)

        # Checks condition first by using eval_cond function.
        # If true then do statements that are nested
        # else do statements nested in else
        elif name == 'IfStmt':
            if self.eval_cond(model.cond):
                for c in model.commands:
                    self.interpret_indv(c)
            else:
                for c in model.elseCommands:
                    self.interpret_indv(c)
        
        # Checks if while cond is true, if it is, loop the nested staments
        elif name == 'WhileStmt':
            while self.eval_cond(model.cond):
                for c in model.commands:
                    self.interpret_indv(c)
        
        # Evaluates the start and finish, then it does the nested statements a 
        # n times. Also keeps counter for loop number.
        elif name == 'ForStmt':
            start, end = self.eval_expr(model.start), self.eval_expr(model.end)
            for i in range(start, end+1):
                self.variables[model.var] = i
                for c in model.commands:
                    self.interpret_indv(c)
        
        # If no commands where recognised, handle exception
        else:
            raise RuntimeError(f"Unknown command: '{name}'")

    # Checks to see if the conditions from left and right, based on operand
    # are true or false. Returns result.
    def eval_cond(self, cond):
        lhs = self.eval_expr(cond.left)
        rhs = self.eval_expr(cond.right)
        return{
            '==' : lhs == rhs,
            '!=' : lhs != rhs,
            '<' : lhs < rhs,
            '<=' : lhs <= rhs,
            '>' : lhs > rhs,
            '>=' : lhs >= rhs

        }[cond.op]
    
    # Evaluates expr, to see if its a str, int, expr or variable.
    # Also has a math parser, which does order of operation
    # checking primary operands all the way to addition and subtraction
    # Recursie function for math parsing
    def eval_expr(self, expr):
        node = expr.__class__.__name__
        if node == 'Str':
            return expr.value
        if node == 'Int':
            return expr.value
        if node == 'Var':
            name = expr.name
            if name not in self.variables:
                raise NameError(f"Variable '{name}' is not defined.")
            return self.variables[name]
        # For parenthesis or expr
        if node == 'Primary' and hasattr(expr, 'expr'):
            return self.eval_expr(expr.expr)
        # For exponents
        if node == 'Factor':
            base = self.eval_expr(expr.base)
            if expr.exponent:
                return base ** self.eval_expr(expr.exponent)
            return base
        # For multiplication, division, and modulo
        if node == 'Term':
            total = self.eval_expr(expr.left)
            # assignes variables, with operand and value to the right of operand.
            for op, right in zip(expr.op, expr.right):
                rhs = self.eval_expr(right)
                if op == '*': total *= rhs
                elif op == '/': total /= rhs
                elif op == '//': total //= rhs
                # For modulo
                else: total %= rhs
            return total
        # For addition and subtraction
        if node == 'Expr':
            total = self.eval_expr(expr.left)
            # assignes variables, with operand and value to the right of operand.
            for op, right in zip(expr.op, expr.right):
                rhs = self.eval_expr(right)
                total = total + rhs if op == '+' else total - rhs
            return total
        raise RuntimeError(f"Cannot evaluate node type: {node}")

# Breaks source code into tokens, and places them into an array, to 
# store for pixel image order.
def tokenize(source):
    tokens = []
    i = 0
    keys = sorted(TOKEN_COLOR_MAP.keys(), key=lambda k: -len(k))
    while i < len(source):
        for tok in keys:
            if source.startswith(tok, i):
                tokens.append(tok)
                i += len(tok)
                break
        else:
            tokens.append(source[i])
            i+=1
    return tokens

# Generates the pixel sqaured image, by using the tokens array, and set deafult values
# to create this image
def pixgen(tokens:dict, pixel_size:int, default_color=(0,0,0)):
    n = len(tokens)
    side = math.ceil(math.sqrt(n))
    w = h = side
    img = Image.new('RGB', (w*pixel_size, h*pixel_size), default_color)
    for i, tok in enumerate(tokens):
        x, y = i % w, i // w
        color = TOKEN_COLOR_MAP.get(tok, default_color)
        for pixel_x in range(x*pixel_size, (x+1)*pixel_size):
            for pixel_y in range(y*pixel_size, (y+1)*pixel_size):
                img.putpixel((pixel_x, pixel_y), color)
    return img

# Dict for converting the image back to functional code to run
reverse = {rgb: tok for tok, rgb in TOKEN_COLOR_MAP.items()}

# Will turn the pixels from the image back into its original source code,
# TL:DR interprets image back to PixKeyLang to run/execute
def depixelize(img: Image.Image, pixel_size: int, reverse_map: dict):
    width_pixels = img.width // pixel_size
    height_pixels = img.height // pixel_size
    pixels = img.load()
    tokens = []
    for y in range(height_pixels):
        for x in range(width_pixels):
            rgb = pixels[x * pixel_size, y * pixel_size]
            if  rgb in reverse_map:
                tokens.append(reverse_map[rgb])
    return tokens


def main(debug=False):
    this_folder = dirname(__file__)
    #Gets file name from command line (terminal)
    program_file = sys.argv[1]
    #Split file name by base name and extension
    base, ext = splitext(program_file)
    PixKey_mm = metamodel_from_file(join(this_folder, 'PixKeyLang.tx'), debug=False)
    #Creates interpreter instance
    PixKey = PixKeyLang()

    #If file extension is png, open image, convert image pixels to tokens, make tokens into source code,
    # parse the source code string into the tx model and run model.
    if ext.lower() == '.png':
        img = Image.open(join(this_folder, program_file))
        toks = depixelize(img, pixel_size=8, reverse_map=reverse)
        src = ''.join(toks)
        PixKey_model = PixKey_mm.model_from_str(src)
        PixKey.interpret(PixKey_model)
    #Else, file is pixkey.
    #Opens file and parses code to tx model, then tokenize the source code into pixels to make
    #pixel image, and save with base name and png extension.
    else:
        model_export(PixKey_mm, join(this_folder, 'PixKeyLang.dot'))
        model = PixKey_mm.model_from_file(join(this_folder, program_file))
        with open(join(this_folder, program_file), encoding='utf-8') as f:
            src = f.read()
        toks = tokenize(src)
        img = pixgen(toks, pixel_size=8)
        img.save(join(this_folder, base+'.png'))
        PixKey.interpret(model)

if __name__ == "__main__":
    main()