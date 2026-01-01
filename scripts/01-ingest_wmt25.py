import os
import json
import collections
import random
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

with open("../wmt25-general-mt/data/wmt25-genmt-humeval.jsonl", "r") as f:
    data_wmt = [json.loads(line) for line in f.readlines()]

documents = collections.defaultdict(list)

for line in data_wmt:
    doc_id, seg_id = line["doc_id"].rsplit("_#_", 1)
    documents[doc_id].append((seg_id, line))

LANG_TO_NAME = {
    "en": "English",
    "cs_CZ": "Czech",
    "de_DE": "German",
}

data_out = collections.defaultdict(list)
for doc_id, segments in documents.items():
    if "_#_speech_#_" in doc_id or "_#_social_#_" in doc_id or "_#_literary_#_" in doc_id:
        continue
    langs = doc_id.split("_#_")[0]
    lang1, lang2 = langs.split("-")
    segments.sort(key=lambda x: x[0])
    # Get all models for this document
    models = list(segments[0][1]["tgt_text"].keys())
    
    # Create one document task per model for the basic template
    # Note: Each model gets its own task with a single-item array.
    # This maintains compatibility with the existing WMT25 data structure
    # where each model's output is evaluated separately.
    for model in models:
        document_task = []
        for seg_i, seg in segments:
            document_task.append({
                "item_id": f"{doc_id}_#_{seg_i}",
                "models": [model],
                "src": seg["src_text"],
                "tgt": [seg["tgt_text"][model]],
            } | (
                {} if seg_i != "0" else {
                    "instructions": f"Evaluate translation from {LANG_TO_NAME.get(lang1, lang1)} to {LANG_TO_NAME.get(lang2, lang2)}.",
                }
            ))
        data_out[langs].append(document_task)

r = random.Random(0)

LANGS_TO_CONFIG = {
    "cs-de_DE": ("mqm_csde", "MQM"),
    "en-cs_CZ": ("esa_encs", "ESA"),
    "en-uk_UA": ("da_enuk", "DA"),
}

for langs, data in data_out.items():
    # chunk to 10 documents per task
    data_new = []
    r.shuffle(data)
    for i in range(0, len(data), 10):
        chunk = data[i:i + 10]
        data_new.append(chunk)

    if langs not in LANGS_TO_CONFIG:
        continue

    fname, config = LANGS_TO_CONFIG[langs]

    with open(f"examples/{fname}.json", "w") as f:
        lang1, lang2 = langs.split("-")
        json.dump(
            {
                "info": {
                    "assignment": "task-based",
                    "protocol": config,
                },
                "campaign_id": fname,
                # just first 5 users to keep the size small
                "data": data_new[:5],
            },
            f,
            ensure_ascii=False,
            indent=2
        )
