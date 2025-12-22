.PHONY: help generate-parsers generate-python-parser generate-typescript-parser test-parsers clean-generated dev-ide

help:
	@echo "Tactus Parser Generation"
	@echo ""
	@echo "Available targets:"
	@echo "  generate-parsers        - Generate both Python and TypeScript parsers"
	@echo "  generate-python-parser  - Generate Python parser only"
	@echo "  generate-typescript-parser - Generate TypeScript parser only"
	@echo "  test-parsers            - Run parser tests"
	@echo "  clean-generated         - Remove generated parser files"
	@echo "  dev-ide                 - Start IDE in dev mode (auto-restart backend + rebuild frontend)"
	@echo ""
	@echo "Requirements:"
	@echo "  - Docker must be running (for parser generation)"
	@echo "  - Python 3.11+ with dependencies installed"
	@echo "  - Node.js 20+ (for IDE frontend)"

generate-parsers: generate-python-parser generate-typescript-parser

generate-python-parser:
	@echo "Generating Python parser from Lua grammar..."
	@echo "Using Docker with eclipse-temurin:17-jre..."
	docker run --rm \
		-v "$$(pwd)":/work \
		-v /tmp:/tmp \
		-w /work \
		eclipse-temurin:17-jre \
		java -jar /tmp/antlr-4.13.1-complete.jar \
		-Dlanguage=Python3 \
		-visitor \
		-no-listener \
		-o /work/tactus/validation/generated \
		/work/tactus/validation/grammar/LuaLexer.g4 \
		/work/tactus/validation/grammar/LuaParser.g4
	@echo "Copying base classes..."
	cp tactus/validation/LuaLexerBase.py tactus/validation/generated/
	cp tactus/validation/LuaParserBase.py tactus/validation/generated/
	@echo "Fixing 'this' references in generated code..."
	sed -i.bak 's/this\./self./g' tactus/validation/generated/LuaParser.py
	sed -i.bak 's/this\./self./g' tactus/validation/generated/LuaLexer.py
	rm -f tactus/validation/generated/*.bak
	@echo "✓ Python parser generated successfully"

generate-typescript-parser:
	@echo "Generating TypeScript parser from Lua grammar..."
	@echo "Using Docker with Node.js and Java..."
	docker run --rm \
		-v "$$(pwd)":/work \
		-w /work/tactus-web \
		eclipse-temurin:17-jre \
		bash -c " \
		curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
		apt-get install -y nodejs && \
		npm install && \
		npx antlr4ts -visitor -no-listener \
			-o src/validation/generated \
			/work/tactus/validation/grammar/LuaLexer.g4 \
			/work/tactus/validation/grammar/LuaParser.g4 \
		"
	@echo "Copying base classes..."
	cp /tmp/grammars-v4/lua/TypeScript/LuaLexerBase.ts tactus-web/src/validation/generated/ || true
	cp /tmp/grammars-v4/lua/TypeScript/LuaParserBase.ts tactus-web/src/validation/generated/ || true
	@echo "✓ TypeScript parser generated"
	@echo "⚠️  Note: Manual fixes may be needed for antlr4ts compatibility"

test-parsers:
	@echo "Running Python parser tests..."
	pytest tests/validation/test_antlr_parser.py -v
	@echo ""
	@echo "Running TypeScript parser tests..."
	cd tactus-web && npm test

clean-generated:
	@echo "Cleaning generated parser files..."
	rm -rf tactus/validation/generated/*.py
	rm -rf tactus/validation/generated/*.interp
	rm -rf tactus/validation/generated/*.tokens
	rm -rf tactus-web/src/validation/generated/*.ts
	rm -rf tactus-web/src/validation/generated/*.interp
	rm -rf tactus-web/src/validation/generated/*.tokens
	@echo "✓ Generated files removed"

# IDE dev mode (no Vite dev server)
dev-ide:
	@chmod +x tactus-ide/dev.sh
	@cd tactus-ide && ./dev.sh








