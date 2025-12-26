# CHANGELOG

<!-- version list -->

## v0.10.0 (2025-12-26)

### Code Style

- Apply black formatting to determinism safety feature
  ([`1a88e88`](https://github.com/AnthusAI/Tactus/commit/1a88e88e975c70dee53305b6bf803bb354a43476))


## v0.9.0 (2025-12-26)


## v0.8.0 (2025-12-25)

### Chores

- Apply black and ruff linter fixes to Lua tools feature
  ([`67c5e9d`](https://github.com/AnthusAI/Tactus/commit/67c5e9d0b1ac554e90d85124b5a3bcf113e8d2c7))

### Code Style

- Apply black formatting to entire codebase
  ([`28e25dd`](https://github.com/AnthusAI/Tactus/commit/28e25dd42248a96e01d8331d9da17d1ec5d9d9e0))

### Features

- Implement comprehensive durable execution system
  ([`ff924e9`](https://github.com/AnthusAI/Tactus/commit/ff924e994073bcc71004d2fcde7bab60b38dcee9))

- Implement comprehensive durable execution system
  ([`672cb50`](https://github.com/AnthusAI/Tactus/commit/672cb50550c745117e99f4cc832c81d40a76e294))

### Breaking Changes

- Replace params/outputs syntax with input/output/state


## v0.7.0 (2025-12-16)


## v0.6.2 (2025-12-16)

### Bug Fixes

- Align tool implementation with Pydantic AI and numerous frontend improvements
  ([`4fa5649`](https://github.com/AnthusAI/Tactus/commit/4fa5649e7bd569b99ed2bff5504f145678b9ddfa))

- Skip MCP integration test when OpenAI API key not available
  ([`7b6894f`](https://github.com/AnthusAI/Tactus/commit/7b6894f577a62eb5ad0f2db8d8d7353209aaae83))


## v0.6.1 (2025-12-15)

### Bug Fixes

- Resolve Behave registry conflicts in e2e tests
  ([`ced4160`](https://github.com/AnthusAI/Tactus/commit/ced41603883ecba465008edf6a216d4d5e61000d))

### Code Style

- Format code with black
  ([`3f97cc1`](https://github.com/AnthusAI/Tactus/commit/3f97cc1dad1f3d3c01cb9e6c30e08da08e7409bb))


## v0.6.0 (2025-12-15)

### Bug Fixes

- Add pytest-xdist to dev dependencies for parallel test execution
  ([`d43be74`](https://github.com/AnthusAI/Tactus/commit/d43be740730479bd9f3e2eeefc8b9a96b14d4489))

- Clear Behave registry before AND after e2e tests
  ([`a430682`](https://github.com/AnthusAI/Tactus/commit/a4306825cb4322f7462b00c8d8e15137cb4affeb))

- Clear Behave registry before AND after each test
  ([`c83d1eb`](https://github.com/AnthusAI/Tactus/commit/c83d1eb532e306b71b31c2d4b821db7b10f1bd27))

- Disable pytest-xdist parallel execution due to Behave global state conflicts
  ([`612875e`](https://github.com/AnthusAI/Tactus/commit/612875e83e02e9bff8c6b74b52fc346f94504d2b))

- Enable streaming responses in CLI and add direct file execution
  ([`e53ee22`](https://github.com/AnthusAI/Tactus/commit/e53ee22b4c683b91774b484c19b6115f1e663f7b))

- Enable streaming responses in CLI and add direct file execution
  ([`47aab07`](https://github.com/AnthusAI/Tactus/commit/47aab07339c96cd8030c3a03bf22e4648b86f49c))

- Only clear Behave registry for tests that use it
  ([`67987aa`](https://github.com/AnthusAI/Tactus/commit/67987aadad1339c3ebb05d10c071a04ddb010d8f))

- Remove debug logging code from run_procedure_stream()
  ([`7a783b5`](https://github.com/AnthusAI/Tactus/commit/7a783b50f4881efb2eede7756613cf38d40dca21))

- Skip problematic Behave tests due to global registry conflicts
  ([`7f47c38`](https://github.com/AnthusAI/Tactus/commit/7f47c38fd9cbda63517b8e560bc7219c85942975))

- Update example file names in feature tests
  ([`e6bc0ae`](https://github.com/AnthusAI/Tactus/commit/e6bc0aeea6d26b30019146d7765ec3e36d0dd384))

- Use multiprocessing 'spawn' context to avoid Behave global registry conflicts
  ([`442816e`](https://github.com/AnthusAI/Tactus/commit/442816e7f8dc3ab4c95c53279e336a39d72eb01c))

- Use spawn context in evaluation_runner and fix iterations method call
  ([`83d8853`](https://github.com/AnthusAI/Tactus/commit/83d885341b31d4a6c25980a5c567ae652c7bddef))

- **tests**: Add simple per-turn tool control test and dynamic tool availability example
  ([`11c63c4`](https://github.com/AnthusAI/Tactus/commit/11c63c4190d78851b0ac462e6afa2368e1b62685))

### Code Style

- Format test_runner.py with black
  ([`96a177f`](https://github.com/AnthusAI/Tactus/commit/96a177fa8207d3bb5c4bdfc42fa1d9ba58e7de52))

### Features

- Add real-time LLM response streaming to Tactus IDE
  ([`3c45f29`](https://github.com/AnthusAI/Tactus/commit/3c45f29da47d1e8c7de26dfe9901ef5e37fb81d0))

- **streaming**: Support for streaming responses into the IDE.
  ([`2b5dac9`](https://github.com/AnthusAI/Tactus/commit/2b5dac9748d47071aceec61b1aa1d72fd7ea8032))


## v0.5.0 (2025-12-13)


## v0.4.0 (2025-12-13)


## v0.3.0 (2025-12-12)

### Bug Fixes

- Add missing fallback logging in LogPrimitive.debug()
  ([`26fc8d7`](https://github.com/AnthusAI/Tactus/commit/26fc8d74794afd38f9b421b4cffcf090f5b74340))

- Resolve ruff and black linter issues
  ([`4091d41`](https://github.com/AnthusAI/Tactus/commit/4091d416b00293f8f60d0a2a3997ab4a7c055172))

### Chores

- Add .tactus/config.yml to gitignore
  ([`bcc75f6`](https://github.com/AnthusAI/Tactus/commit/bcc75f66fb901c3845807663d816bcc5194c6026))

### Code Style

- Apply black formatting to all files
  ([`7f76e75`](https://github.com/AnthusAI/Tactus/commit/7f76e757a59687a12397032ba089f3eb40d1e99a))

### Features

- **BDD**: Tactus is BDD at the core. 🤘
  ([`66e8fb7`](https://github.com/AnthusAI/Tactus/commit/66e8fb7786a30e1a494d7339c4e473d95767288f))

### Refactoring

- Remove deprecated description() construct from DSL
  ([`380ac5f`](https://github.com/AnthusAI/Tactus/commit/380ac5f164d71ba48bd6462644a8f958a50a4053))


## v0.2.1 (2025-12-12)

### Bug Fixes

- Add PyPI upload step to release workflow
  ([`1849407`](https://github.com/AnthusAI/Tactus/commit/1849407c1b14683bc137390bab08173118664557))


## v0.2.0 (2025-12-11)

### Documentation

- Add AI agent guidelines for semantic release
  ([`daa1736`](https://github.com/AnthusAI/Tactus/commit/daa173665f888dce5de423e72f6dab909b95b632))

### Features

- Migrate to pure Lua DSL and add Electron-based IDE
  ([`5d91807`](https://github.com/AnthusAI/Tactus/commit/5d91807e770bbb5f6203407239eb9da8ee44aac8))

### Breaking Changes

- Workflow format changed from YAML+Lua (.tyml) to pure Lua DSL (.tac.lua)


## v0.1.0 (2025-12-11)

- Initial Release

## v0.0.0 (2025-12-11)

- Initial Release
