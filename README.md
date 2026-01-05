# 🍐Pearmut &nbsp; &nbsp; [![PyPi version](https://badgen.net/pypi/v/pearmut/)](https://pypi.org/project/pearmut) [![PyPI download/month](https://img.shields.io/pypi/dm/pearmut.svg)](https://pypi.python.org/pypi/pearmut/) [![PyPi license](https://badgen.net/pypi/license/pearmut/)](https://pypi.org/project/pearmut/) [![build status](https://github.com/zouharvi/pearmut/actions/workflows/test.yml/badge.svg)](https://github.com/zouharvi/pearmut/actions/workflows/test.yml)

**Platform for Evaluation and Reviewing of Multilingual Tasks**: Evaluate model outputs for translation and NLP tasks with support for multimodal data (text, video, audio, images) and multiple annotation protocols ([DA](https://aclanthology.org/N15-1124/), [ESA](https://aclanthology.org/2024.wmt-1.131/), [ESA<sup>AI</sup>](https://aclanthology.org/2025.naacl-long.255/), [MQM](https://doi.org/10.1162/tacl_a_00437), and more!).


<img width="1000" alt="Screenshot of ESA/MQM interface" src="https://github.com/user-attachments/assets/71334238-300b-4ffc-b777-7f3c242b1630" />


## Table of Contents

- [Quick Start](#quick-start)
- [Campaign Configuration](#campaign-configuration)
  - [Basic Structure](#basic-structure)
  - [Assignment Types](#assignment-types)
- [Advanced Features](#advanced-features)
  - [Pre-filled Error Spans (ESA<sup>AI</sup>)](#pre-filled-error-spans-esaai)
  - [Tutorial and Attention Checks](#tutorial-and-attention-checks)
  - [Pre-defined User IDs and Tokens](#pre-defined-user-ids-and-tokens)
  - [Multimodal Annotations](#multimodal-annotations)
  - [Hosting Assets](#hosting-assets)
- [Campaign Management](#campaign-management)
  - [Custom Completion Messages](#custom-completion-messages)
- [CLI Commands](#cli-commands)
- [Terminology](#terminology)
- [Development](#development)
- [Citation](#citation)
- [Changelog](#changelog)


## Quick Start

Install and run locally without cloning:
```bash
pip install pearmut
# Download example campaigns
wget https://raw.githubusercontent.com/zouharvi/pearmut/refs/heads/main/examples/esa.json
wget https://raw.githubusercontent.com/zouharvi/pearmut/refs/heads/main/examples/da.json
# Load and start
pearmut add esa.json da.json
pearmut run
```

## Campaign Configuration

### Basic Structure

Campaigns are defined in JSON files (see [examples/](examples/)). The simplest configuration uses `task-based` assignment where each user has pre-defined tasks:
```python
{
  "info": {
    "assignment": "task-based",
    # DA: scores
    # ESA: error spans and scores
    # MQM: error spans, categories, and scores
    "protocol": "ESA", 
  },
  "campaign_id": "wmt25_#_en-cs_CZ",
  "data": [
    # data for first task/user
    [
      [
        # each evaluation item is a document
        {
          "instructions": "Evaluate translation from en to cs_CZ",  # message to show to users above the first item
          "src": "This will be the year that Guinness loses its cool. Cheers to that!",
          "tgt": {"modelA": "Nevím přesně, kdy jsem to poprvé zaznamenal. Možná to bylo ve chvíli, ..."},
          "item_id": "first item in first document"
        },
        {
          "src": "I'm not sure I can remember exactly when I sensed it. Maybe it was when some...",
          "tgt": {"modelA": "Tohle bude rok, kdy Guinness přijde o svůj „cool“ faktor. Na zdraví!"},
          "item_id": "second item in first document"
        }
        ...
      ],
      # more document
      ...
    ],
    # data for second task/user
    [
        ...
    ],
    # arbitrary number of users (each corresponds to a single URL to be shared)
  ]
}
```

Each item has to have `tgt` (dictionary from model names to strings, even for a single model evaluation).
Optionally, you can also include `src` (source string) and/or `ref` (reference string).
If neither `src` nor `ref` is provided, only the model outputs will be displayed.
For full Pearmut functionality (e.g. automatic statistical analysis), add `item_id` as well.
Any other keys that you add will simply be stored in the logs.

Load campaigns and start the server:
```bash
pearmut add my_campaign.json  # Use -o/--overwrite to replace existing
pearmut run
```

### Assignment Types

- **`task-based`**: Each user has predefined items
- **`single-stream`**: All users draw from a shared pool (random assignment)
- **`dynamic`**: Items are dynamically assigned based on current model performance (see [Dynamic Assignment](#dynamic-assignment))

## Advanced Features

### Shuffling Model Translations

By default, Pearmut randomly shuffles the order in which models are shown per each item in order to avoid positional bias.
The `shuffle` parameter in campaign `info` controls this behavior:
```python
{
  "info": {
    "assignment": "task-based",
    "protocol": "ESA",
    "shuffle": true  # Default: true. Set to false to disable shuffling.
  },
  "campaign_id": "my_campaign",
  "data": [...]
}
```

### Custom Score Sliders

For multi-dimensional evaluation tasks (e.g., assessing fluency on a Likert scale), you can define custom sliders with specific ranges and steps:

```python
{
  "info": {
    "assignment": "task-based",
    "protocol": "ESA",
    "sliders": [
      {"name": "Fluency", "min": 0, "max": 5, "step": 1},
      {"name": "Adequacy", "min": 0, "max": 100, "step": 1}
    ]
  },
  "campaign_id": "my_campaign",
  "data": [...]
}
```

When `sliders` is specified, only the custom sliders are shown. Each slider must have `name`, `min`, `max`, and `step` properties. All sliders must be answered before proceeding.

### Custom Instructions

Set campaign-level instructions using the `instructions` field in `info` (supports HTML).
Instructions default to protocol-specific ones (DA: scoring, ESA: error spans + scoring, MQM: error spans + categories + scoring).
```python
{
  "info": {
    "protocol": "DA",
    "instructions": "Rate translation quality on a 0-100 scale.<br>Pay special attention to document-level phenomena."
  }
}
```

### Pre-filled Error Spans (ESA<sup>AI</sup>)

Include `error_spans` to pre-fill annotations that users can review, modify, or delete:

```python
{
  "src": "The quick brown fox jumps over the lazy dog.",
  "tgt": {"modelA": "Rychlá hnědá liška skáče přes líného psa."},
  "error_spans": {
    "modelA": [
      {
        "start_i": 0,         # character index start (inclusive)
        "end_i": 5,           # character index end (inclusive)
        "severity": "minor",  # "minor", "major", "neutral", or null
        "category": null      # MQM category string or null
      },
      {
        "start_i": 27,
        "end_i": 32,
        "severity": "major",
        "category": null
      }
    ]
  }
}
```

The `error_spans` field is a 2D array (one per candidate). See [examples/esaai_prefilled.json](examples/esaai_prefilled.json).

### Tutorial and Attention Checks

Add `validation` rules for tutorials or attention checks:

```python
{
  "src": "The quick brown fox jumps.",
  "tgt": {"modelA": "Rychlá hnědá liška skáče."},
  "validation": {
    "modelA": [
      {
        "warning": "Please set score between 70-80.",  # shown on failure (omit for silent logging)
        "score": [70, 80],                             # required score range [min, max]
        "error_spans": [{"start_i": [0, 2], "end_i": [4, 8], "severity": "minor"}],  # expected spans
        "allow_skip": true                             # show "skip tutorial" button
      }
    ]
  }
}
```

**Types:**
- **Tutorial**: Include `allow_skip: true` and `warning` to let users skip after feedback
- **Loud attention checks**: Include `warning` without `allow_skip` to force retry
- **Silent attention checks**: Omit `warning` to log failures without notification (quality control)

The `validation` field is an array (one per candidate). Dashboard shows ✅/❌ based on `validation_threshold` in `info` (integer for max failed count, float \[0,1\) for max proportion, default 0).

**Score comparison:** Use `score_greaterthan` to ensure one candidate scores higher than another:
```python
{
  "src": "AI transforms industries.",
  "tgt": {"A": "UI transformuje průmysly.", "B": "Umělá inteligence mění obory."},
  "validation": {
    "A": [
      {"warning": "A has error, score 20-40.", "score": [20, 40]}
    ],
    "B": [
      {"warning": "B is correct and must score higher than A.", "score": [70, 90], "score_greaterthan": "A"}
    ]
  }
}
```
The `score_greaterthan` field specifies the index of the candidate that must have a lower score than the current candidate.
See [examples/tutorial/esa_deen.json](examples/tutorial/esa_deen.json) for a mock campaign with a fully prepared ESA tutorial.
To use it, simply extract the `data` attribute and prefix it to each task in your campaign.

### Single-stream Assignment

All annotators draw from a shared pool with random assignment:
```python
{
    "campaign_id": "my campaign 6",
    "info": {
        "assignment": "single-stream",
        # DA: scores
        # MQM: error spans and categories
        # ESA: error spans and scores
        "protocol": "ESA",
        "users": 50,                           # number of annotators (can also be a list, see below)
    },
    "data": [...], # list of all items (shared among all annotators)
}
```

### Dynamic Assignment

The `dynamic` assignment type intelligently selects items based on current model performance to focus annotation effort on top-performing models using contrastive comparisons.
All items must contain outputs from all models for this assignment type to work properly.

```python
{
    "campaign_id": "my dynamic campaign",
    "info": {
        "assignment": "dynamic",
        "protocol": "ESA",
        "users": 10,                           # number of annotators
        "dynamic_top": 3,                      # how many top models to consider (required)
        "dynamic_contrastive_models": 2,       # how many models to compare per item (optional, default: 1)
        "dynamic_first": 5,                    # annotations per model before dynamic kicks in (optional, default: 5)
        "dynamic_backoff": 0.1,                # probability of uniform sampling (optional, default: 0)
    },
    "data": [...], # list of all items (shared among all annotators)
}
```

**How it works:**
1. Initial phase: Each model gets `dynamic_first` annotations with fully random contrastive evaluation
2. Dynamic phase: After the initial phase, top `dynamic_top` models (by average score) are identified
3. Contrastive evaluation: From the top N models, `dynamic_contrastive_models` models are randomly selected for each item
4. Item prioritization: Items with the least annotations for the selected models are prioritized
5. Backoff: With probability `dynamic_backoff`, uniform random selection is used instead to maintain exploration

This approach efficiently focuses annotation resources on distinguishing between the best-performing models while ensuring all models get adequate baseline coverage. The contrastive evaluation allows for direct comparison of multiple models simultaneously.
For an example, see [examples/dynamic.json](examples/dynamic.json).

### Pre-defined User IDs and Tokens

The `users` field accepts:
- **Number** (e.g., `50`): Generate random user IDs
- **List of strings** (e.g., `["alice", "bob"]`): Use specific user IDs
- **List of dictionaries**: Specify custom tokens:
```python
{
    "info": {
        ...
        "users": [
            {"user_id": "alice", "token_pass": "alice_done", "token_fail": "alice_fail"},
            {"user_id": "bob", "token_pass": "bob_done"}  # missing tokens are auto-generated
        ],
    },
    ...
}
```


### Multimodal Annotations

Support for HTML-compatible elements (YouTube embeds, `<video>` tags, images). Ensure elements are pre-styled. See [examples/multimodal.json](examples/multimodal.json).

<img width="1000" alt="Preview of multimodal elements in Pearmut" src="https://github.com/user-attachments/assets/77c4fa96-ee62-4e46-8e78-fd16e9007956" />

### Hosting Assets

Host local assets (audio, images, videos) using the `assets` key:

```python
{
    "campaign_id": "my_campaign",
    "info": { 
      "assets": {
        "source": "videos",                    # Source directory
        "destination": "assets/my_videos"      # Mount path (must start with "assets/")
      }
    },
    "data": [ ... ]
}
```

Files from `videos/` become accessible at `localhost:8001/assets/my_videos/`. Creates a symlink, so source directory must exist throughout annotation. Destination paths must be unique across campaigns.

## CLI Commands

- **`pearmut add <file(s)>`**: Add campaign JSON files (supports wildcards)
  - `-o/--overwrite`: Replace existing campaigns with same ID
  - `--server <url>`: Server URL prefix (default: `http://localhost:8001`)
- **`pearmut run`**: Start server
  - `--port <port>`: Server port (default: 8001)
  - `--server <url>`: Server URL prefix
- **`pearmut purge [campaign]`**: Remove campaign data
  - Without args: Purge all campaigns
  - With campaign name: Purge specific campaign only

## Campaign Management

Management link (shown when adding campaigns or running server) provides:
- Annotator progress overview
- Access to annotation links
- Task progress reset (data preserved)
- Download progress and annotations

<img width="1000" alt="Management dashboard" src="https://github.com/user-attachments/assets/5a27271c-1e80-4e54-b242-c361265df86e" />

Completion tokens are shown at annotation end for verification (download correct tokens from dashboard). Incorrect tokens can be shown if quality control fails.

<img width="500" alt="Token on completion" src="https://github.com/user-attachments/assets/40eb904c-f47a-4011-aa63-9a4f1c501549" />

When tokens are supplied, the dashboard will try to show model rankings based on the names in the dictionaries.

### Custom Completion Messages

Customize the goodbye message shown to users when they complete all annotations using the `instructions_goodbye` field in campaign info. Supports arbitrary HTML for styling and formatting with variable replacement: `${TOKEN}` (completion token) and `${USER_ID}` (user ID). Default: `"If someone asks you for a token of completion, show them: ${TOKEN}"`.

## Terminology

- **Campaign**: An annotation project that contains configuration, data, and user assignments. Each campaign has a unique identifier and is defined in a JSON file.
  - **Campaign File**: A JSON file that defines the campaign configuration, including the campaign ID, assignment type, protocol settings, and annotation data.
  - **Campaign ID**: A unique identifier for a campaign (e.g., `"wmt25_#_en-cs_CZ"`). Used to reference and manage specific campaigns. Typically a campaign is created for a specific language and domain.
- **Task**: A unit of work assigned to a user. In task-based assignment, each task consists of a predefined set of items for a specific user.
- **Item**: A single annotation unit within a task. For translation evaluation, an item typically represents a document (source text and target translation). Items can contain text, images, audio, or video.
- **Document**: A collection of one or more segments (sentence pairs or text units) that are evaluated together as a single item.
- **User** / **Annotator**: A person who performs annotations in a campaign. Each user is identified by a unique user ID and accesses the campaign through a unique URL.
- **Attention Check**: A validation item with known correct answers used to ensure annotator quality. Can be:
  - **Loud**: Shows warning message and forces retry on failure
  - **Silent**: Logs failures without notifying the user (for quality control analysis)
  - **Token**: A completion code shown to users when they finish their annotations. Tokens verify the completion and whether the user passed quality control checks:
    - **Pass Token** (`token_pass`): Shown when user meets validation thresholds
    - **Fail Token** (`token_fail`): Shown when user fails to meet validation requirements
- **Tutorial**: An instructional validation item that teaches users how to annotate. Includes `allow_skip: true` to let users skip if they have seen it before.
- **Validation**: Quality control rules attached to items that check if annotations match expected criteria (score ranges, error span locations, etc.). Used for tutorials and attention checks.
- **Model**: The system or model that generated the output being evaluated (e.g., `"GPT-4"`, `"Claude"`). Used for tracking and ranking model performance.
- **Dashboard**: The management interface that shows campaign progress, annotator statistics, access links, and allows downloading annotations. Accessed via a special management URL with token authentication.
- **Protocol**: The annotation scheme defining what data is collected:
  - **Score**: Numeric quality rating (0-100)
  - **Error Spans**: Text highlights marking errors with severity (`minor`, `major`)
  - **Error Categories**: MQM taxonomy labels for errors
- **Template**: The annotation interface type. The `basic` template supports comparing multiple outputs simultaneously.
- **Assignment**: The method for distributing items to users:
  - **Task-based**: Each user has predefined items
  - **Single-stream**: Users draw from a shared pool with random assignment
  - **Dynamic**: Items are intelligently assigned based on model performance to focus on top models

## Development

Server responds to data-only requests from frontend (no template coupling). Frontend served from pre-built `static/` on install.

### Local development:
```bash
cd pearmut
# Frontend (separate terminal, recompiles on change)
npm install web/ --prefix web/
npm run build --prefix web/
# optionally keep running indefinitely to auto-rebuild
npm run watch --prefix web/

# Install as editable
pip3 install -e .
# Load examples
pearmut add examples/wmt25_#_en-cs_CZ.json examples/wmt25_#_cs-de_DE.json
pearmut run
```

### Creating new protocols:
1. Add HTML and TS files to `web/src`
2. Add build rule to `webpack.config.js`
3. Reference as `info->template` in campaign JSON

See [web/src/basic.ts](web/src/basic.ts) for example.

### Deployment

Run on public server or tunnel local port to public IP/domain and run locally.

## Citation

If you use this work in your paper, please cite as following.
```bibtex
@misc{zouhar2026pearmut,
  author = {Zouhar, Vilém},
  title = {Pearmut: Human Evaluation of Translation Made Trivial},
  year = {2026}
}
```

Contributions are welcome! Please reach out to [Vilém Zouhar](mailto:vilem.zouhar@gmail.com).

# Changelog

- v1.0.1
  - Support RTL languages
  - Add boxes for references
  - Add custom score sliders for multi-dimensional evaluation
  - Make instructions customizable and protocol-dependent
  - Support custom sliders
  - Purge/reset whole tasks from dashboard
  - Fix resetting individual users in single-stream/dynamic
  - Fix notification stacking
  - Add campaigns from dashboard
- v0.3.3
  - Rename `doc_id` to `item_id`
  - Add Typst, LaTeX, and PDF export for model ranking tables. Hide them by default.
  - Add dynamic assignment type with contrastive model comparison
  - Add `instructions_goodbye` field with variable substitution
  - Add visual anchors at 33% and 66% on sliders
  - Add German→English ESA tutorial with attention checks
  - Validate document model consistency before shuffle
  - Fix UI block on any interaction
- v0.3.2
  - Revert seeding of user IDs
  - Set ESA (Error Span Annotation) as default
  - Update server IP address configuration
  - Show approximate alignment by default
  - Unify pointwise and listwise interfaces into `basic`
  - Refactor protocol configuration (breaking change)
- v0.2.11
  - Add comment field in settings panel
  - Add `score_gt` validation for listwise comparisons
  - Add Content-Disposition headers for proper download filenames
  - Add model results display to dashboard with rankings
  - Add campaign file structure validation
  - Purge command now unlinks assets
- v0.2.6
  - Add frozen annotation links feature for view-only mode
  - Add word-level annotation mode toggle for error spans
  - Add `[missing]` token support
  - Improve frontend speed and cleanup toolboxes on item load
  - Host assets via symlinks
  - Add validation threshold for success/fail tokens
  - Implement reset masking for annotations
  - Allow pre-defined user IDs and tokens in campaign data
- v0.1.1
  - Set server defaults and add VM launch scripts
  - Add warning dialog when navigating away with unsaved work
  - Add tutorial validation support for pointwise and listwise
  - Add ability to preview existing annotations via progress bar
  - Add support for ESA<sup>AI</sup> pre-filled error_spans
  - Rename pairwise to listwise and update layout
  - Implement single-stream assignment type
- v0.0.3
  - Support multimodal inputs and outputs
  - Add dashboard
  - Implement ESA (Error Span Annotation) and MQM support

