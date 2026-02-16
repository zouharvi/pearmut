# Mock Annotation Data

This directory contains example campaign configurations with pre-generated mock annotation data for demonstration purposes.

## Campaigns

### 1. ESA Campaign (`campaign_esa.json`)
- **Protocol**: ESA (Error Span Annotation)
- **Language Pair**: English → German
- **Models**: GPT-4, Claude
- **Users**: 
  - alice: 2 documents completed
  - bob: 1 document completed
- **Features**: Error span annotations with severity levels

### 2. DA Campaign (`campaign_da.json`)
- **Protocol**: DA (Direct Assessment)
- **Language Pair**: English → Spanish
- **Models**: Gemini, Llama
- **Users**:
  - carol: 1 document completed
  - david: 1 document completed
- **Features**: Simple quality scores

### 3. MQM Campaign (`campaign_mqm.json`)
- **Protocol**: MQM (Multidimensional Quality Metrics)
- **Language Pair**: English → French
- **Models**: DeepL, Reverso
- **Users**:
  - eve: 1 document completed
  - frank: 1 document completed
- **Features**: Error categorization with MQM taxonomy

## Usage

### Load the campaigns

```bash
# From the repository root
pearmut add examples/annotation/*.json
```

### Start the server

```bash
pearmut run
```

### View the dashboard

The server will print a dashboard URL that looks like:
```
http://localhost:8001/dashboard?token_main=...&campaign_id=annotation_demo_esa&token=...
```

## Mock Data Structure

The mock data includes:

- **Campaign configurations** in this directory (`campaign_*.json`)
- **Progress tracking** in `data/progress.json` (when campaigns are loaded)
- **Task definitions** in `data/tasks/` (when campaigns are loaded)
- **Annotation data** in `data/outputs/*.jsonl` (when campaigns are loaded)

Each annotation includes:
- Translation quality scores (75-95 range)
- Error span annotations (for ESA/MQM)
- Error categories and severity levels (for MQM)
- User comments explaining decisions
- Timing information for annotation sessions

## Screenshots

Use this data to generate screenshots demonstrating:
- The annotation dashboard with multiple campaigns
- User progress tracking
- Completed annotations with scores and error spans
- Different annotation protocols (ESA, DA, MQM)

## Note

This data is for demonstration purposes only. The annotations are synthetic and designed to showcase the platform's capabilities.
