# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

For visual categorization of changes emojis are used in accordance with [gitmoji](https://gitmoji.dev).

## [1.3.0] - 2026-11-10

### 🎨 Changed
- Parser now distributes as Python package.

## [1.2.0] - 2026-11-04

### ✨ Added
- Compatibility with `melon>=1.0.0-rc.7`.

### 🎨 Changed
- Parent parser required version is upped to `remanga>=2.7`.
- Use `HyperTextParser` for content processing.
- Save only best cover option.
- Support **ID_Checker** and **Slugger** extension from parent parser.
- Stubs reworked as images signatures.

### 🔥 Removed
- Dependency from `lxml`.
