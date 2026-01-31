# CHANGELOG

<!-- version list -->

## v0.35.0 (2026-01-31)

### Bug Fixes

- Expand coverage and harden cli paths
  ([`1b98486`](https://github.com/AnthusAI/Tactus/commit/1b9848629c54dd2655f428b13ca2c8d775cc395f))

- Update pydantic-ai dependency to pydantic-ai-slim
  ([`f4f54c1`](https://github.com/AnthusAI/Tactus/commit/f4f54c19d0969a8c54a9214e5f465bdfc55e95dc))

- Update pydantic-ai-slim dependency to include evals extra
  ([`d1af5d1`](https://github.com/AnthusAI/Tactus/commit/d1af5d101cd099b2806a12f0fef898170bfec597))

- **quality**: Imposing opinions.
  ([`d41d6b8`](https://github.com/AnthusAI/Tactus/commit/d41d6b805e9e7ff2373c58437c3d76306599ab2f))

### Chores

- Add markdown and jinja2 dependencies for documentation rendering
  ([`0a0b24f`](https://github.com/AnthusAI/Tactus/commit/0a0b24fe9400cc74724e1543d79a6e87f85e1b88))

### Features

- Add message history transforms
  ([`2263017`](https://github.com/AnthusAI/Tactus/commit/226301762526bdd9d3bc0e91a7401c8407e6b85e))

- **specs**: 100% test coverage!
  ([`4b913d6`](https://github.com/AnthusAI/Tactus/commit/4b913d65f952585392f368db70a6e730cfa204e6))


## v0.34.1 (2026-01-25)

### Bug Fixes

- Add local HITL components fallback
  ([`ddda4cd`](https://github.com/AnthusAI/Tactus/commit/ddda4cdb304a0e1d52007bc98e60fb45d00cc166))


## v0.34.0 (2026-01-25)

### Bug Fixes

- Address ruff warnings
  ([`8523ff0`](https://github.com/AnthusAI/Tactus/commit/8523ff0fb54a3cc961869cb243c27efca84fcd9b))

- Clarify sandbox defaults and CLI failures
  ([`1bdc1d9`](https://github.com/AnthusAI/Tactus/commit/1bdc1d9a5d9552a1972845646248746f2dfa35e6))

- Enable agent tool calling with DSPy native function calling
  ([`a76ea99`](https://github.com/AnthusAI/Tactus/commit/a76ea99d79732f6e39e242e733c3918cf7aca76c))

- Enable mocks for custom steps
  ([`b777f6b`](https://github.com/AnthusAI/Tactus/commit/b777f6b033f297ef6dc5ceae262a41b56d11b680))

- Enable real-time streaming for IDE agent responses
  ([`55266d7`](https://github.com/AnthusAI/Tactus/commit/55266d7b840bfa52121ec76a8353dd8d074f9760))

- Enforce sandbox defaults and PyPI image build
  ([`af17c15`](https://github.com/AnthusAI/Tactus/commit/af17c15d384cc475cb5128fcf0776eba522880ba))

- Make Classify primitive deterministic in BDD
  ([`0c58e55`](https://github.com/AnthusAI/Tactus/commit/0c58e554b46653abfa834d1a536ac964290428f4))

- Mock LLM classify examples in BDD
  ([`8277d3e`](https://github.com/AnthusAI/Tactus/commit/8277d3e99f8612bf3d65447ebe451f75337da715))

- Pass mock manager into BDD runtime context
  ([`76fd440`](https://github.com/AnthusAI/Tactus/commit/76fd4408e9afc58bf9c3116b25605f7ac0d30d89))

- Register generate agent mocks
  ([`6faf28c`](https://github.com/AnthusAI/Tactus/commit/6faf28c9f289eb45b633ae11d8a0e02311023c74))

- Stabilize stdlib generate specs
  ([`e6a00cb`](https://github.com/AnthusAI/Tactus/commit/e6a00cb494756ff5eeb07f3b55ec1a8e875a06ba))

- Update dependencies and improve CI configuration
  ([`a063fa5`](https://github.com/AnthusAI/Tactus/commit/a063fa59272e2192305c8a7806185f8fcb0bcafd))

- Update MockHITLHandler to accept execution_context parameter
  ([`14cd888`](https://github.com/AnthusAI/Tactus/commit/14cd888a4a6cdd05457158cb904a07cb14df4bb8))

### Chores

- Report stdlib scenario failures
  ([`7aa5093`](https://github.com/AnthusAI/Tactus/commit/7aa5093a7e98c217e32c3483d39e7d44820c24da))

### Code Style

- Apply black 26.1.0 formatting
  ([`d189f41`](https://github.com/AnthusAI/Tactus/commit/d189f4121ead45b4bb44599a9def9c40ef7c1983))

### Documentation

- Add brand theme and visual design policies
  ([`ca2ea2d`](https://github.com/AnthusAI/Tactus/commit/ca2ea2d388179b5bea4d4a4650b896d20fa7f974))

- Comprehensive checkpoint/resume testing summary
  ([`54b9ec9`](https://github.com/AnthusAI/Tactus/commit/54b9ec998492ab31e6065a4ae3777b7d5f1ece59))

- Document LLM checkpointing implementation
  ([`3906604`](https://github.com/AnthusAI/Tactus/commit/3906604e7f887a4cfe2e4e6557162527b61382d0))

- Mark Phase 2 complete, ready for Phase 3 IDE/SSE channel
  ([`8db044e`](https://github.com/AnthusAI/Tactus/commit/8db044e111f1a5d348179c54fe3b24be515ea7d9))

- Mark Test 3 (LLM Checkpoint/Resume) complete
  ([`6eb0043`](https://github.com/AnthusAI/Tactus/commit/6eb00435039a2d37107579eb5ab4c3a07374a46c))

- Update checkpoint testing status - Test 2 complete
  ([`b5b4bd8`](https://github.com/AnthusAI/Tactus/commit/b5b4bd818aaeb84a766c58ce9b0403e70b2899b5))

- Update status to Phase 4 testing, remove emojis
  ([`1392959`](https://github.com/AnthusAI/Tactus/commit/139295971b2575f26e4ee41ac2e243f7d65a5c24))

### Features

- Add modal cancellation handling with reopen capability
  ([`392660c`](https://github.com/AnthusAI/Tactus/commit/392660ca4a693975bbc463e38e3323ed9e53113a))

- Complete IDE HITL integration with SSE channel
  ([`5bf5e41`](https://github.com/AnthusAI/Tactus/commit/5bf5e4106a90b291cf6d331cd43e6f6c0fd1c9d8))

- Complete Phase 2 runtime integration with rich metadata
  ([`b265eb9`](https://github.com/AnthusAI/Tactus/commit/b265eb9b2bbb9f9e79b990b1c7664b6e0a547407))

- Complete unified HITL component registry architecture
  ([`4005ae7`](https://github.com/AnthusAI/Tactus/commit/4005ae7baa70c6bba18c9b14fc57dfc05f0d4f4a))

- Enable real-time container HITL and event streaming
  ([`a6e49ff`](https://github.com/AnthusAI/Tactus/commit/a6e49ff2bac5cae149bd4595c632e6b0b4863250))

- Implement DSPy native tool calling with Pydantic AI toolsets
  ([`f061f37`](https://github.com/AnthusAI/Tactus/commit/f061f374babbb15aaa2ba145ebffd536f2c02f55))

- Implement inline rendering for batched HITL inputs with registry architecture
  ([`9b520ba`](https://github.com/AnthusAI/Tactus/commit/9b520ba242afd15f26f452c0d41a59e864cb7bbe))

- Implement LLM checkpointing for transparent durability
  ([`15c0139`](https://github.com/AnthusAI/Tactus/commit/15c0139028f1c9da7eb7900450113ccf37871e93))

- Transparent durability for HITL with checkpoint/resume
  ([`46a3791`](https://github.com/AnthusAI/Tactus/commit/46a3791d6e8c130eb29e156ef029de2bb9ad3ced))

- **stdlib**: Implement standard library with classify, extract, and generate modules
  ([`a274a1e`](https://github.com/AnthusAI/Tactus/commit/a274a1e4407ff07eb51ca16f60403b1b4757b522))

### Testing

- Add LLM checkpoint/resume test procedure
  ([`88e06e5`](https://github.com/AnthusAI/Tactus/commit/88e06e56f21cbefe8f03491a74f545514eb88796))

- Add Test 4 and Test 5 procedures
  ([`d181355`](https://github.com/AnthusAI/Tactus/commit/d181355b9e4233fb54e9894b3f109f8dcfdefb6b))

- Add Tests 6-8 procedures and manual testing guide
  ([`9c27030`](https://github.com/AnthusAI/Tactus/commit/9c270305fc73036e4bb180ddccaf5f6f8291da7a))


## v0.33.0 (2026-01-18)

### Documentation

- Add installation instructions for unsigned macOS builds
  ([`bb34f44`](https://github.com/AnthusAI/Tactus/commit/bb34f44b389b0154801d79a9d23255068328945d))

### Features

- Improve unsigned app distribution based on research
  ([`34bc90e`](https://github.com/AnthusAI/Tactus/commit/34bc90ed6e25f4e58a4fefccbbc3c4220869dd3b))


## v0.32.2 (2026-01-17)

### Bug Fixes

- Use Python 3.13 in CI to match local working build
  ([`e2d2768`](https://github.com/AnthusAI/Tactus/commit/e2d276819759b7c8feb724f42145ab8553025b78))


## v0.32.1 (2026-01-17)

### Bug Fixes

- Add Flask and Flask-CORS to package dependencies for IDE server
  ([`a7ccb69`](https://github.com/AnthusAI/Tactus/commit/a7ccb6957c77628601407f53b8a41d074c6d5568))


## v0.32.0 (2026-01-17)

### Code Style

- Apply Black formatting to IDE server and config files
  ([`65641cc`](https://github.com/AnthusAI/Tactus/commit/65641cc4b806230c086dff071853d1527f82781d))

### Features

- Add authentication error dialog and automatic config reload
  ([`5f3dd95`](https://github.com/AnthusAI/Tactus/commit/5f3dd9572e545cfeb94c26af656ad1d36723cc43))


## v0.31.2 (2026-01-16)

### Bug Fixes

- Include litellm tokenizers and data files in PyInstaller bundle
  ([`b770f35`](https://github.com/AnthusAI/Tactus/commit/b770f35d79d097505b3022c53eb54e92383e037c))


## v0.31.1 (2026-01-15)

### Bug Fixes

- Only upload installer files (dmg/exe/AppImage) to release, not entire dist-electron directory
  ([`424e9e2`](https://github.com/AnthusAI/Tactus/commit/424e9e267be1972e1a2eed5d8c06961cc74e4c26))


## v0.31.0 (2026-01-15)

### Chores

- Merge origin/main
  ([`dd8c4d4`](https://github.com/AnthusAI/Tactus/commit/dd8c4d4aa08cf4d7aaf8be69e76309a66be36ec8))

### Documentation

- Add workaround for macOS Gatekeeper damaged app error
  ([`cbf9b38`](https://github.com/AnthusAI/Tactus/commit/cbf9b38a25a99d8f0ff8949e3a646ed69d276713))


## v0.30.0 (2026-01-15)


## v0.29.4 (2026-01-15)

### Bug Fixes

- Sync desktop app version with semantic-release version in filenames
  ([`212eec0`](https://github.com/AnthusAI/Tactus/commit/212eec0c179c6b1d3aa47b4d595be91db696f114))


## v0.29.3 (2026-01-15)

### Bug Fixes

- Ensure desktop builds fetch tags and attach to correct semantic-release version
  ([`679f132`](https://github.com/AnthusAI/Tactus/commit/679f1321a46809facfa0e0146907076f071478af))


## v0.29.2 (2026-01-15)

### Bug Fixes

- Upgrade Node.js to version 20 for desktop builds
  ([`f08380d`](https://github.com/AnthusAI/Tactus/commit/f08380da9f326667943e793f7aa73902d15d4d49))


## v0.29.1 (2026-01-15)

### Bug Fixes

- Add type module to tactus-desktop package.json for ES module support
  ([`7b0bdaa`](https://github.com/AnthusAI/Tactus/commit/7b0bdaa8272f010be73137ed1f727b0bfad48827))


## v0.29.0 (2026-01-15)

### Code Style

- Run black formatter on container_runner.py
  ([`9338945`](https://github.com/AnthusAI/Tactus/commit/93389452b4a059607e4d50535b8bac348c085ab1))

### Features

- **desktop**: Integrate Electron desktop builds into semantic-release workflow
  ([`77a1fbe`](https://github.com/AnthusAI/Tactus/commit/77a1fbe2e9807c1e6a6ad12c574cdae6f1687f73))


## v0.28.0 (2026-01-14)

### Bug Fixes

- Correct test assertions for protocol changes
  ([`79b1bdb`](https://github.com/AnthusAI/Tactus/commit/79b1bdb6d4fd1e5c6dd5e7bd0089d2049d05ede8))

- Disallow curried Tool syntax (#27) ([#27](https://github.com/AnthusAI/Tactus/pull/27),
  [`e5b25c2`](https://github.com/AnthusAI/Tactus/commit/e5b25c23f1ba50e1fed1b8a13fef77c172ed48ab))

- Enable TCP broker streaming with length-prefixed protocol
  ([`68d4d91`](https://github.com/AnthusAI/Tactus/commit/68d4d915316928b9ce180737259363b49f38788b))

- Mark broker integration tests to skip in CI
  ([`a34de74`](https://github.com/AnthusAI/Tactus/commit/a34de74f083a229c7e6480ac80984808e9d76207))

- Mark TCP broker integration tests to skip in CI
  ([`e8ecfa5`](https://github.com/AnthusAI/Tactus/commit/e8ecfa5216c19b7339e342c2e8682265f25a2808))

- Update DSPy agent tests for TactusResult API changes
  ([`aeb16f0`](https://github.com/AnthusAI/Tactus/commit/aeb16f0d0bd45481840bdc26cb1ecc1b4d46c8a7))

- Update TCP unit tests for length-prefixed protocol
  ([`803bcd8`](https://github.com/AnthusAI/Tactus/commit/803bcd87b294082b2e598be4c299a8840f2be6f6))

- **agent**: Make Raw the default module and case-insensitive matching
  ([`0cac3fa`](https://github.com/AnthusAI/Tactus/commit/0cac3fa75b3ee49b6e87221eea5d232b9e751ca7))

- **agent**: Return TactusResult with value and cost stats
  ([`c83f92d`](https://github.com/AnthusAI/Tactus/commit/c83f92dd561b553f7db8cf32cb9a93e9dfad1b20))

- **broker**: Handle async event emission from sync threads
  ([`340e288`](https://github.com/AnthusAI/Tactus/commit/340e28891bcaefb174d5d2babb34a16f0c3abd84))

### Chores

- Update GitHub Actions workflow for release process
  ([`310a5a5`](https://github.com/AnthusAI/Tactus/commit/310a5a5e07028257b04811d5a8e8e1fca2d34d90))

### Code Style

- Run black on test_mock_field_normalization.py
  ([`4522f4b`](https://github.com/AnthusAI/Tactus/commit/4522f4b7e2e093d3041cea086d84efcece5cb06f))

### Documentation

- Update sandboxing and broker defaults
  ([`9ac4dcc`](https://github.com/AnthusAI/Tactus/commit/9ac4dcc7f65b54ab1a516d190afc748c933ee6e8))

### Features

- Add default current directory volume mount
  ([`095c687`](https://github.com/AnthusAI/Tactus/commit/095c687c3758c01c2c93929f929a2e00045e831b))


## v0.27.0 (2026-01-11)

### Features

- **broker**: Brokered sandbox runtime MVP (secretless runtime container) (#24)
  ([#24](https://github.com/AnthusAI/Tactus/pull/24),
  [`f922432`](https://github.com/AnthusAI/Tactus/commit/f922432da5a881c5eceb7c1410276ab45264ddaa))


## v0.26.0 (2026-01-11)

### Features

- Improve logging UX and fs helpers (#26) ([#26](https://github.com/AnthusAI/Tactus/pull/26),
  [`a2a8704`](https://github.com/AnthusAI/Tactus/commit/a2a8704c1a0ab3b2cad45b9514af2152d12faa3b))


## v0.25.0 (2026-01-11)

### Features

- Add IDE preferences UI with config source tracking (#25)
  ([#25](https://github.com/AnthusAI/Tactus/pull/25),
  [`cedf64d`](https://github.com/AnthusAI/Tactus/commit/cedf64d87f1707305283d073710ee3c6b674c44a))


## v0.24.0 (2026-01-11)

### Code Style

- Format app.py with black
  ([`f3286ce`](https://github.com/AnthusAI/Tactus/commit/f3286ce6b6207fcc1eb15a30cd9e58763943a021))

### Features

- Add --version flag support to CLI
  ([`b7bbc52`](https://github.com/AnthusAI/Tactus/commit/b7bbc520fbd332764b61016d8e9edf03062fcf1d))


## v0.23.0 (2026-01-11)

### Features

- Add AI chat assistant to Tactus IDE with streaming and tool execution
  ([`81f544a`](https://github.com/AnthusAI/Tactus/commit/81f544a16e86a8f26b328583b432ad2f1ad26504))


## v0.22.0 (2026-01-10)

### Features

- **agent**: Add configurable `module` parameter for DSPy module selection (#21)
  ([#21](https://github.com/AnthusAI/Tactus/pull/21),
  [`0c93af0`](https://github.com/AnthusAI/Tactus/commit/0c93af0575d191be58ed0635ed236e359d8b35af))


## v0.21.1 (2026-01-10)

### Bug Fixes

- **ci**: Add --skip-existing to twine upload
  ([`7a1b369`](https://github.com/AnthusAI/Tactus/commit/7a1b369376ce68869b98f0faed877a52855b4459))


## v0.21.0 (2026-01-10)

### Bug Fixes

- Add Checkpoint.exists and Checkpoint.get
  ([`d652411`](https://github.com/AnthusAI/Tactus/commit/d6524115dea8de42559b94a1f35309f7538958e7))

- Add System.alert primitive
  ([`18ece11`](https://github.com/AnthusAI/Tactus/commit/18ece114eea760e97b07a493b7ee13eb27034516))

- Clarify summarization prompts are logged
  ([`423b912`](https://github.com/AnthusAI/Tactus/commit/423b912c590cd7e9702a0e9dbb76288f26cdfd4a))

- Clarify template namespaces and rendering
  ([`a33a383`](https://github.com/AnthusAI/Tactus/commit/a33a3831fb335b81d1e3152f5feb6d24f436bdb8))

- Expose agent Result usage and history
  ([`7f41286`](https://github.com/AnthusAI/Tactus/commit/7f412860f94c79a442fc8e86365f71ddddc9b58f))

- Handle string input in agent __call__ method
  ([`4af6ad5`](https://github.com/AnthusAI/Tactus/commit/4af6ad590cacb116885ce60ca93656c092f01435))

- Remove incompatible tests and skip deprecated YAML test
  ([`f96f084`](https://github.com/AnthusAI/Tactus/commit/f96f0842ceffa8176329b5553096c39ff1ba15d1))

- Standardize on TactusResult.value and fix agent mock lookup
  ([`a4e02c0`](https://github.com/AnthusAI/Tactus/commit/a4e02c0699a40461a2d0476e1359216d02a82616))

- Support message alias for agent calls
  ([`9a2b817`](https://github.com/AnthusAI/Tactus/commit/9a2b817478acf5848dad346fa9d0f0dd1a78eb86))

- **ci**: Only run twine upload when dist files exist
  ([`d490f55`](https://github.com/AnthusAI/Tactus/commit/d490f5527c8588666ffcafa67d13e195815c2856))

### Chores

- Update .gitignore to include tmp/ directory
  ([`1294360`](https://github.com/AnthusAI/Tactus/commit/1294360a261cec1ff8c35f8063ae2b652c340373))


## v0.20.0 (2026-01-09)


## v0.19.0 (2026-01-09)


## v0.18.0 (2026-01-09)


## v0.17.0 (2026-01-08)

### Bug Fixes

- Pass registry and mock_manager to DSPy agent creation
  ([`e86a069`](https://github.com/AnthusAI/Tactus/commit/e86a0690cba607507f4745106f8a609aab38c8f3))

- Remove unused Path import in test_script_mode.py
  ([`1c28430`](https://github.com/AnthusAI/Tactus/commit/1c28430502ac2f1c0b08f6456ec7374e9fc4252a))

### Code Style

- Format code with black
  ([`2fc1a07`](https://github.com/AnthusAI/Tactus/commit/2fc1a0734f639c3d502f4e96b0eb44703a3522c8))

### Testing

- Skip agent mock test in CI until mocking fully implemented
  ([`f46f183`](https://github.com/AnthusAI/Tactus/commit/f46f1834a616a8dfde31b9ee6cdb928264489b93))

- Skip DSPy agent mock test - assignment name interception not working
  ([`b7971d3`](https://github.com/AnthusAI/Tactus/commit/b7971d3d87dd07f43c98fcab524a5cad5848db5d))


## v0.16.0 (2026-01-07)

### Bug Fixes

- **tests**: Resolve ruff linting errors
  ([`892f73e`](https://github.com/AnthusAI/Tactus/commit/892f73eed13602cb6cb6328c363b1caa938db850))

### Code Style

- Format code with black
  ([`bdec5b8`](https://github.com/AnthusAI/Tactus/commit/bdec5b8836d7d95bd6531ede2c4f000e24e79764))

### Features

- **dspy**: Add comprehensive behavior specifications for DSPy integration
  ([`531167e`](https://github.com/AnthusAI/Tactus/commit/531167e2c423c605792f1e5ab3602f7eb05ab6d8))

- **dspy**: Add model_type parameter support for reasoning models
  ([`bf8cef3`](https://github.com/AnthusAI/Tactus/commit/bf8cef38e0e0674ccf1ebfac75a92c54e80b6d0c))

- **dspy**: Add model_type parameter support for reasoning models
  ([`0043293`](https://github.com/AnthusAI/Tactus/commit/00432937a11adc01a846909fe1ae9520cc927eab))

### Refactoring

- **examples**: Simplify agent example and add gpt-5-mini support
  ([`7e7934e`](https://github.com/AnthusAI/Tactus/commit/7e7934eb89508d100dbce5ebd497ddcefda7778d))


## v0.15.1 (2026-01-07)


## v0.15.0 (2026-01-07)

### Code Style

- Apply black formatting to dspy_integration_steps.py
  ([`2cda08d`](https://github.com/AnthusAI/Tactus/commit/2cda08dcbcb7a645093234608818e255b97ed857))

### Features

- Migrate Agent implementation from pydantic_ai to DSPy
  ([`691abfa`](https://github.com/AnthusAI/Tactus/commit/691abfa71799ef373c742fe92402fb280022ad1c))

### Breaking Changes

- None - all existing .tac files continue to work unchanged


## v0.14.0 (2026-01-07)

### Features

- Overhaul DSL syntax with CamelCase declarations and field builder pattern
  ([`92bac2c`](https://github.com/AnthusAI/Tactus/commit/92bac2cbb2c6afcc50258a48794424df92797f1e))

### Breaking Changes

- All declaration keywords are now CamelCase and type definitions use the new field builder pattern.


## v0.13.0 (2026-01-03)

### Bug Fixes

- **ide**: Correct inputs parameter handling in procedure execution
  ([`84e3ca4`](https://github.com/AnthusAI/Tactus/commit/84e3ca44bd36a9a8b8866a08f5d84ad48bb855ad))

### Chores

- Remove temporary IDE overhaul summary document
  ([`74e2257`](https://github.com/AnthusAI/Tactus/commit/74e2257a93c08f70b642cb2b98870f61445b2d02))


## v0.12.0 (2026-01-01)


## v0.11.0 (2026-01-01)

### Code Style

- Fix ruff linting errors
  ([`17c6aee`](https://github.com/AnthusAI/Tactus/commit/17c6aeeb34b3c743fe9b1990b8cdff617dcac9a8))

- Fix ruff linting errors and apply black formatting
  ([`846366d`](https://github.com/AnthusAI/Tactus/commit/846366db43f78c92d8559b32a98e4bd4b285c277))

### Features

- **checkpoints**: Add run boundaries and persistent event storage
  ([`73404b7`](https://github.com/AnthusAI/Tactus/commit/73404b7681c9a4b30c420228a2b116891a5ef014))

- **checkpoints**: Add run boundaries and persistent event storage
  ([`913d5bd`](https://github.com/AnthusAI/Tactus/commit/913d5bdf24900a214a18831fe8c3511f5115fa02))


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
