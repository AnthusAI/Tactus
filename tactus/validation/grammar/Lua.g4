grammar Lua;

chunk : block EOF ;

block : stat* retstat? ;

stat : ';'
     | varlist '=' explist
     | functioncall
     | label
     | 'break'
     | 'goto' NAME
     | 'do' block 'end'
     | 'while' exp 'do' block 'end'
     | 'repeat' block 'until' exp
     | 'if' exp 'then' block ('elseif' exp 'then' block)* ('else' block)? 'end'
     | 'for' NAME '=' exp ',' exp (',' exp)? 'do' block 'end'
     | 'for' namelist 'in' explist 'do' block 'end'
     | 'function' funcname funcbody
     | 'local' 'function' NAME funcbody
     | 'local' attnamelist ('=' explist)?
     ;

attnamelist : NAME attrib? (',' NAME attrib?)* ;

attrib : '<' NAME '>' ;

retstat : 'return' explist? ';'? ;

label : '::' NAME '::' ;

funcname : NAME ('.' NAME)* (':' NAME)? ;

varlist : var (',' var)* ;

var : NAME | prefixexp '[' exp ']' | prefixexp '.' NAME ;

namelist : NAME (',' NAME)* ;

explist : exp (',' exp)* ;

exp : 'nil' | 'false' | 'true' | number | string | '...' | functiondef 
    | prefixexp | tableconstructor | exp binop exp | unop exp 
    ;

prefixexp : var | functioncall | '(' exp ')' ;

functioncall : prefixexp args | prefixexp ':' NAME args ;

args : '(' explist? ')' | tableconstructor | string ;

functiondef : 'function' funcbody ;

funcbody : '(' parlist? ')' block 'end' ;

parlist : namelist (',' '...')? | '...' ;

tableconstructor : '{' fieldlist? '}' ;

fieldlist : field (fieldsep field)* fieldsep? ;

field : '[' exp ']' '=' exp | NAME '=' exp | exp ;

fieldsep : ',' | ';' ;

binop : '+' | '-' | '*' | '/' | '//' | '^' | '%' 
      | '&' | '~' | '|' | '>>' | '<<' | '..' 
      | '<' | '<=' | '>' | '>=' | '==' | '~=' 
      | 'and' | 'or' ;

unop : '-' | 'not' | '#' | '~' ;

number : INT | HEX | FLOAT | HEX_FLOAT ;

string : NORMALSTRING | CHARSTRING | LONGSTRING ;

NAME : [a-zA-Z_] [a-zA-Z_0-9]* ;

NORMALSTRING : '"' ( EscapeSequence | ~('\\'|'"'|'\r'|'\n') )* '"' 
             | '\'' ( EscapeSequence | ~('\\'|'\''|'\r'|'\n') )* '\'' 
             ;

fragment
EscapeSequence : '\\' [abfnrtv\\"']
               | '\\' 'z' WHITESPACE*
               | '\\' [0-9] [0-9]? [0-9]?
               | '\\' 'x' [0-9a-fA-F] [0-9a-fA-F]
               | '\\' 'u' '{' [0-9a-fA-F]+ '}'
               ;

CHARSTRING : '\'' ( EscapeSequence | ~('\\'|'\''|'\r'|'\n') )* '\'' ;

LONGSTRING : '[' '='* '[' .*? ']' '='* ']' ;

INT : [0-9]+ ;
HEX : '0' [xX] [0-9a-fA-F]+ ;
FLOAT : [0-9]+ '.' [0-9]* ([eE] [+-]? [0-9]+)?
      | '.' [0-9]+ ([eE] [+-]? [0-9]+)?
      | [0-9]+ [eE] [+-]? [0-9]+
      ;
HEX_FLOAT : '0' [xX] [0-9a-fA-F]+ ('.' [0-9a-fA-F]*)? ([pP] [+-]? [0-9]+)? ;

COMMENT : '--' ('[' '='* '[' .*? ']' '='* ']' | ~[\r\n]* ) -> skip ;

WHITESPACE : [ \t\r\n]+ -> skip ;
