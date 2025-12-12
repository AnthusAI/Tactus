#!/usr/bin/env ts-node
/**
 * Demo script showing the TypeScript ANTLR parser in action.
 * 
 * This demonstrates the same functionality as the Python demo:
 * 1. Valid file parsing
 * 2. Error detection
 * 3. Inline code parsing
 */

import { TactusValidator } from './src/validation/TactusValidator';
import * as fs from 'fs';
import * as path from 'path';

function demo1ValidFile() {
  console.log('='.repeat(70));
  console.log('DEMO 1: Valid Lua DSL File');
  console.log('='.repeat(70));
  
  const filePath = path.join(__dirname, '../examples/simple-agent.tac');
  console.log(`\nValidating: simple-agent.tac\n`);
  
  const source = fs.readFileSync(filePath, 'utf-8');
  const validator = new TactusValidator();
  const result = validator.validate(source, 'full');
  
  if (result.valid) {
    console.log('✓ Syntax is valid!');
    if (result.registry) {
      console.log('\nExtracted DSL information:');
      console.log(`  - Name: ${result.registry.procedureName || 'N/A'}`);
      console.log(`  - Version: ${result.registry.version || 'N/A'}`);
      console.log(`  - Description: ${result.registry.description || 'N/A'}`);
      
      console.log(`\n  Parameters (${Object.keys(result.registry.parameters).length}):`);
      if (Object.keys(result.registry.parameters).length > 0) {
        for (const [paramName, paramDecl] of Object.entries(result.registry.parameters)) {
          const defaultVal = paramDecl.default !== undefined ? `, default="${paramDecl.default}"` : '';
          console.log(`    • ${paramName}: ${paramDecl.parameterType}${defaultVal}`);
        }
      } else {
        console.log('    (none)');
      }
      
      console.log(`\n  Agents (${Object.keys(result.registry.agents).length}):`);
      for (const agentName of Object.keys(result.registry.agents)) {
        console.log(`    • ${agentName}`);
      }
      
      console.log(`\n  Outputs (${Object.keys(result.registry.outputs).length}):`);
      for (const [outputName, outputDecl] of Object.entries(result.registry.outputs)) {
        console.log(`    • ${outputName}: ${outputDecl.fieldType} (required=${outputDecl.required})`);
      }
    }
  } else {
    console.log('✗ Validation failed');
    for (const error of result.errors) {
      console.log(`  ${error.message}`);
    }
  }
  
  return result.valid;
}

function demo2InvalidFile() {
  console.log('\n' + '='.repeat(70));
  console.log('DEMO 2: Invalid Lua DSL File (Syntax Errors)');
  console.log('='.repeat(70));
  
  const source = `-- Test file with syntax errors

name("test_workflow")
version("1.0.0")

-- Missing closing brace on line 8
agent("worker", {
    provider = "openai"
-- Missing closing brace here!

procedure(function()
    Log.info("test")
    return { success = true }
end)`;
  
  console.log('\nValidating: test-invalid.tac\n');
  
  const validator = new TactusValidator();
  const result = validator.validate(source, 'full');
  
  if (result.valid) {
    console.log('✓ Syntax is valid!');
  } else {
    console.log('✗ Syntax errors detected:');
    for (const error of result.errors) {
      console.log(`  ${error.message}`);
    }
  }
  
  return !result.valid;
}

function demo3InlineCode() {
  console.log('\n' + '='.repeat(70));
  console.log('DEMO 3: Parsing Inline Lua DSL Code');
  console.log('='.repeat(70));
  
  const code = `
name("hello_world")
version("1.0.0")

agent("worker", {
    provider = "openai",
    system_prompt = "You are helpful"
})

procedure(function()
    Log.info("Hello from Lua DSL!")
    return { success = true }
end)
`;
  
  console.log('\nCode to parse:');
  console.log('-'.repeat(70));
  console.log(code);
  console.log('-'.repeat(70));
  
  const validator = new TactusValidator();
  const result = validator.validate(code, 'full');
  
  if (result.valid) {
    console.log('\n✓ Syntax is valid!');
    if (result.registry) {
      console.log('\nExtracted DSL information:');
      console.log(`  - Name: ${result.registry.procedureName}`);
      console.log(`  - Version: ${result.registry.version}`);
      console.log(`  - Agents: ${Object.keys(result.registry.agents).length}`);
      for (const [agentName, agentDecl] of Object.entries(result.registry.agents)) {
        console.log(`    • ${agentName}: provider=${agentDecl.provider}`);
      }
    }
  } else {
    console.log('\n✗ Validation failed');
    for (const error of result.errors) {
      console.log(`  ${error.message}`);
    }
  }
  
  return result.valid;
}

function main() {
  console.log('\n' + '='.repeat(70));
  console.log('ANTLR Parser Demo - Tactus Lua DSL (TypeScript)');
  console.log('='.repeat(70));
  console.log('\nThis demo shows the TypeScript ANTLR-generated parser validating Lua DSL syntax.');
  console.log('The parser is generated from tactus/validation/grammar/Lua.g4');
  console.log();
  
  const results: [string, boolean][] = [];
  
  // Demo 1: Valid file
  results.push(['Valid file parsing', demo1ValidFile()]);
  
  // Demo 2: Invalid file
  results.push(['Error detection', demo2InvalidFile()]);
  
  // Demo 3: Inline code
  results.push(['Inline code parsing', demo3InlineCode()]);
  
  // Summary
  console.log('\n' + '='.repeat(70));
  console.log('SUMMARY');
  console.log('='.repeat(70));
  for (const [name, passed] of results) {
    const status = passed ? '✓' : '✗';
    console.log(`${status} ${name}`);
  }
  
  console.log('\n' + '='.repeat(70));
  console.log('The TypeScript ANTLR parser successfully:');
  console.log('  1. Parses valid Lua DSL syntax');
  console.log('  2. Detects syntax errors');
  console.log('  3. Extracts DSL declarations (name, version, agent, etc.)');
  console.log('='.repeat(70));
}

main();
