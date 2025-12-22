/**
 * TypeScript implementation of Tactus DSL validator.
 * 
 * Provides client-side syntax validation for instant feedback.
 * This is a simplified version that focuses on syntax checking.
 * For full semantic validation, use the Python LSP backend.
 */

import { ValidationResult, ValidationMessage, ValidationMode } from './types';

export class TactusValidator {
  /**
   * Validate Tactus DSL source code.
   * 
   * @param source - The Lua DSL source code to validate
   * @param mode - Validation mode ('quick' for syntax only, 'full' for semantic)
   * @returns ValidationResult with errors, warnings, and registry
   */
  validate(source: string, mode: ValidationMode = 'full'): ValidationResult {
    const errors: ValidationMessage[] = [];
    const warnings: ValidationMessage[] = [];
    
    try {
      // Phase 1: Basic syntax validation
      // For now, we'll do simple checks until ANTLR parser is generated
      
      // Check for empty source
      if (!source.trim()) {
        return {
          valid: true,
          errors: [],
          warnings: [],
          registry: null
        };
      }
      
      // Basic Lua syntax checks
      this.checkBasicSyntax(source, errors);
      
      // Quick mode: just syntax check
      if (mode === 'quick') {
        return {
          valid: errors.length === 0,
          errors,
          warnings,
          registry: null
        };
      }
      
      // Phase 2: Semantic validation (simplified)
      // Full semantic validation requires the LSP backend
      this.checkSemanticBasics(source, errors, warnings);
      
      return {
        valid: errors.length === 0,
        errors,
        warnings,
        registry: null
      };
      
    } catch (error) {
      errors.push({
        level: 'error',
        message: `Validation error: ${error instanceof Error ? error.message : String(error)}`,
        location: [1, 1]
      });
      
      return {
        valid: false,
        errors,
        warnings,
        registry: null
      };
    }
  }
  
  /**
   * Perform basic syntax checks on Lua code.
   */
  private checkBasicSyntax(source: string, errors: ValidationMessage[]): void {
    const lines = source.split('\n');
    
    // Check for unmatched delimiters
    const stack: Array<{ char: string; line: number; col: number }> = [];
    const pairs: Record<string, string> = {
      '(': ')',
      '[': ']',
      '{': '}'
    };
    const closers: Record<string, string> = {
      ')': '(',
      ']': '[',
      '}': '{'
    };
    
    let inMultiLineString = false;
    let multiLineStringLevel = 0;
    
    for (let lineNum = 0; lineNum < lines.length; lineNum++) {
      const line = lines[lineNum];
      let inString = false;
      let stringChar = '';
      let inComment = false;
      
      for (let col = 0; col < line.length; col++) {
        const char = line[col];
        const nextChar = line[col + 1];
        
        // Handle multi-line strings [[...]]
        if (!inString && !inComment && char === '[' && nextChar === '[') {
          inMultiLineString = true;
          multiLineStringLevel++;
          col++; // Skip next [
          continue;
        }
        if (inMultiLineString && char === ']' && nextChar === ']') {
          multiLineStringLevel--;
          if (multiLineStringLevel === 0) {
            inMultiLineString = false;
          }
          col++; // Skip next ]
          continue;
        }
        
        if (inMultiLineString) continue;
        
        // Handle comments
        if (!inString && char === '-' && nextChar === '-') {
          inComment = true;
          break;
        }
        
        // Handle strings
        if ((char === '"' || char === "'") && !inComment) {
          if (!inString) {
            inString = true;
            stringChar = char;
          } else if (char === stringChar && line[col - 1] !== '\\') {
            inString = false;
          }
          continue;
        }
        
        if (inString || inComment) continue;
        
        // Check delimiters
        if (char in pairs) {
          stack.push({ char, line: lineNum + 1, col: col + 1 });
        } else if (char in closers) {
          if (stack.length === 0) {
            errors.push({
              level: 'error',
              message: `Unexpected closing delimiter '${char}'`,
              location: [lineNum + 1, col + 1]
            });
          } else {
            const last = stack.pop()!;
            if (pairs[last.char] !== char) {
              errors.push({
                level: 'error',
                message: `Mismatched delimiter: expected '${pairs[last.char]}' but found '${char}'`,
                location: [lineNum + 1, col + 1]
              });
            }
          }
        }
      }
    }
    
    // Check for unclosed multi-line string
    if (inMultiLineString || multiLineStringLevel > 0) {
      errors.push({
        level: 'error',
        message: 'Unclosed multi-line string literal [[...]]',
        location: [1, 1]
      });
    }
    
    // Check for unclosed delimiters
    for (const item of stack) {
      errors.push({
        level: 'error',
        message: `Unclosed delimiter '${item.char}'`,
        location: [item.line, item.col]
      });
    }
    
    // Check for basic Lua keywords and structure
    const hasFunction = /\bfunction\b/.test(source);
    const hasEnd = /\bend\b/.test(source);
    
    if (hasFunction && !hasEnd) {
      errors.push({
        level: 'error',
        message: "Function declaration missing 'end' keyword",
        location: [1, 1]
      });
    }
  }
  
  /**
   * Perform basic semantic checks for Tactus DSL constructs.
   */
  private checkSemanticBasics(
    source: string,
    _errors: ValidationMessage[],
    warnings: ValidationMessage[]
  ): void {
    // Check for required Tactus constructs
    const hasAgents = /agents\s*\{/.test(source);
    const hasProcedure = /function\s+procedure\s*\(/.test(source);
    
    if (!hasProcedure) {
      warnings.push({
        level: 'warning',
        message: "No 'procedure' function found. Tactus files should define a procedure() function.",
        location: [1, 1]
      });
    }
    
    // Check for common mistakes
    if (source.includes('agent(') && !hasAgents) {
      warnings.push({
        level: 'warning',
        message: "Using agent() but no agents block found. Define agents in the agents {} block.",
        location: [1, 1]
      });
    }
    
    // Check for undefined references (basic check)
    const agentCalls = source.match(/agent\s*\(\s*["']([^"']+)["']/g);
    if (agentCalls && hasAgents) {
      const agentsBlock = source.match(/agents\s*\{([^}]+)\}/s);
      if (agentsBlock) {
        const definedAgents = agentsBlock[1].match(/(\w+)\s*=/g)?.map(m => m.replace(/\s*=/, '')) || [];
        
        for (const call of agentCalls) {
          const agentName = call.match(/["']([^"']+)["']/)?.[1];
          if (agentName && !definedAgents.includes(agentName)) {
            warnings.push({
              level: 'warning',
              message: `Agent '${agentName}' is called but not defined in agents block`,
              location: [1, 1]
            });
          }
        }
      }
    }
  }
}











