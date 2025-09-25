# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HanLP is a multilingual NLP library built on PyTorch and TensorFlow 2.x for state-of-the-art deep learning techniques in natural language processing. It supports 10 joint tasks on 130+ languages including tokenization, lemmatization, part-of-speech tagging, dependency parsing, constituency parsing, semantic role labeling, semantic dependency parsing, and abstract meaning representation parsing.

## Repository Structure

- `hanlp/` - Core HanLP package containing the main Python code
- `plugins/` - Shared code across packages and non-core APIs
- `docs/` - Documentation in markdown format
- `tests/` - Test suite using unittest
- `.github/` - CI workflows and configurations

## Development Setup

```bash
git clone https://github.com/hankcs/HanLP --branch master
cd HanLP
pip install -e plugins/hanlp_trie
pip install -e plugins/hanlp_common
pip install -e plugins/hanlp_restful
pip install -e .
```

## Common Development Commands

### Running Tests
```bash
# Run all tests
python -m unittest discover ./tests

# Alternative test command used in CI
pytest tests
```

### Building and Packaging
```bash
# Build distribution packages
python setup.py sdist bdist_wheel

# Install in development mode
pip install -e .
```

## Code Architecture

The codebase follows a modular architecture:

1. **Core Package (`hanlp/`)**:
   - `hanlp/components/` - Individual NLP components (tokenizers, parsers, etc.)
   - `hanlp/pretrained/` - Pre-trained models organized by task
   - `hanlp/common/` - Common utilities and base classes
   - `hanlp/utils/` - Utility functions

2. **Multi-Task Learning**:
   - Main implementation in `hanlp/components/mtl/`
   - Pre-trained MTL models defined in `hanlp/pretrained/mtl.py`

3. **Model Loading**:
   - Main entry point through `hanlp.load()` function
   - Model identifiers mapped in `hanlp/pretrained/ALL`

## Key Implementation Patterns

1. **Component-based Design**:
   - Each NLP task is implemented as a component
   - Components can be chained in pipelines
   - Multi-task learning combines multiple components

2. **Pre-trained Models**:
   - Models are referenced by identifiers in `hanlp.pretrained`
   - Automatic downloading and caching of models
   - Meta files define component configurations

3. **Transforms**:
   - Data preprocessing defined in `hanlp/transform/`
   - Convert raw text to model inputs
   - Handle batching and padding

When working with this codebase, focus on understanding the component architecture and how pre-trained models are organized and loaded. Most development work will involve either creating new components or modifying existing ones in the `hanlp/components/` directory.