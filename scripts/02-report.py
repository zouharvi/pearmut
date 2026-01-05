"""
This script creates small annotation campaigns, speed test, and bibliography study used in the Pearmut report.
"""

# %%
import random
import json
import collections
import numpy as np
import statistics

LANG2_TO_LANG3 = {
    "cs": "ces",
    "hi": "hin",
    "ko": "kor",
    "pl": "plk",
    "es": "spa",
    "en": "eng",
    "de": "deu",
    "sk": "slk",
    "it": "ita",
    "fa": "fas",
    # Finnish & Norwegian = Czech just so each langauge is its own user
    "fi": "fin",
    "no": "nob",
}


# %%

"""
###################
1. Annotation study
###################
"""

# get English source data

import subset2evaluate.utils

data_raw = subset2evaluate.utils.load_data_wmt(
    "wmt25", "en-cs_CZ", normalize=False, include_human=True, include_ref=True
)
data_doc = collections.defaultdict(list)

for item in data_raw:
    data_doc[item["doc"]].append(item["src"])

# exactly 3 segments per document
data_doc = {k: v[:3] for k, v in data_doc.items() if len(v) >= 3}
# sort by shortest
data_doc = list(data_doc.items())
data_doc.sort(key=lambda x: sum(len(s) for s in x[1]))
data_doc = [
    [
        {
            "doc_id": f"doc_{i:02d}_#_{j}",
            "src": vj,
        }
        for j, vj in enumerate(v)
    ]
    for i, (k, v) in enumerate(data_doc)
]


print(len(data_doc))
print(json.dumps(data_doc, indent=2, ensure_ascii=False))

"""
Translate the following JSON data into Czech. For each source, output 3 translations: (A) a perfect translation, (B) a poor translation with minor mistakes, and (C) a translation with major mistakes.
Output the data in the same JSON format, just adding the translations into the "tgt" key as:
"tgt": {
    "A": "perfect translation",
    "B": "translation with slight mistakes",
    "C": "translation with noticeable mistakes"
}
"""

# %%


def shuffled(lst, rng=random.Random()):
    lst = list(lst)
    rng.shuffle(lst)
    return lst


for langs in [
    "encs",
    "enhi",
    "enko",
    "enpl",
    "enes",
    "ensk",
    "ende",
    "enit",
    "enfa",
    "enfi",
    "enno",
]:
    lang1, lang2 = langs[:2], langs[2:]
    with open(f"abc_data/translations/{langs}.json", "r") as f:
        data = json.load(f)
    rng = random.Random(langs)
    data_flat = [
        [
            {
                "doc_id": segment["doc_id"],
                "src": segment["src"].replace("\\n", "\n"),
                "tgt": {model: segment["tgt"][model].replace("\\n", "\n")},
            }
            for segment in doc
        ]
        for doc in data
        # shuffle order of good and bad models
        for model in shuffled(["A", "B", "C"], rng)
    ]

    data_1st = []
    data_2nd = []
    for doc in data_flat:
        doc_id = int(doc[0]["doc_id"].split("_#_")[0].removeprefix("doc_"))
        if doc_id % 2 == 0:
            data_1st.append(doc)
        else:
            data_2nd.append(doc)
    data_pearmut = data_1st + data_2nd
    data_appraise = data_2nd + data_1st
    assert len(data_pearmut) == len(data_appraise)
    assert len(data_pearmut) + len(data_appraise) == len(data_flat) * 2

    # create campaign for pearmut, how easy!
    campaign = {
        "campaign_id": f"abc_{langs}",
        "info": {
            "protocol": "ESA",
            "assignment": "task-based",
            "users": [f"{langs}{i}" for i in range(1, 6)],
        },
        "data": [data_pearmut] * 5,
    }
    with open(f"abc_data/pearmut/{langs}.json", "w") as f:
        json.dump(campaign, f, indent=2, ensure_ascii=False)

    # create campaign for appraise, more complex
    campaign = [
        {
            "items": [
                {
                    "mqm": [],
                    "documentID": item["doc_id"].split("_#_")[0],
                    "sourceID": "abc",
                    "targetID": "abc.ref" + list(item["tgt"].keys())[0],
                    "sourceText": item["src"],
                    "targetText": list(item["tgt"].values())[0],
                    "itemType": "TGT",
                    "_item": item["doc_id"] + " | " + list(item["tgt"].keys())[0],
                    "itemID": item_i + doc_i * 3 + 1,
                    "isCompleteDocument": False,
                }
                for doc_i, doc in enumerate(data_appraise)
                for item_i, item in enumerate(doc)
            ],
            "task": {
                "batchNo": 1,
                "randomSeed": 123456,
                "requiredAnnotations": 1,
                "sourceLanguage": "eng",
                "targetLanguage": LANG2_TO_LANG3[lang2],
            },
        }
    ]

    with open(f"abc_data/appraise/{langs}.json", "w") as f:
        json.dump(campaign, f, indent=2, ensure_ascii=False)


"""
python3 manage.py StartNewCampaign ~/pearmut/scripts/abc_data/appraise/manifest.json \
    --batches-json ~/pearmut/scripts/abc_data/appraise/en{cs,hi,ko,pl,es,sk,de,it,fi,no}.json \
    --csv-output ~/pearmut/scripts/abc_data/appraise/accounts.csv

APPRAISE_ALLOWED_HOSTS=alani-unpleadable-vindicatedly.ngrok-free.dev,localhost APPRAISE_CSRF_TRUSTED_ORIGINS=https://alani-unpleadable-vindicatedly.ngrok-free.dev python3 manage.py runserver 

ngrok http 8000 --url https://alani-unpleadable-vindicatedly.ngrok-free.dev

pearmut purge
pearmut add scripts/abc_data/pearmut/en*.json
pearmut run --port 8001 --server https://pearmut.ngrok.io

ngrok http --url=pearmut.ngrok.io 8001
"""

# %%

# gather Appraise data and convert them to Pearmut annotation data format
"""
python3 manage.py ExportSystemScoresToCSV abc24 > ~/pearmut/scripts/abc_data/results/appraise_raw.csv

mv ~/Downloads/annotations.json ./scripts/abc_data/results/pearmut_raw.json
"""

import csv
import glob
import copy

data_pearmut = {}
for fname in glob.glob("abc_data/pearmut/*.json"):
    with open(fname, "r") as f:
        data = json.load(f)["data"][0]
    langs = fname.split("/")[-1].removesuffix(".json")
    data_new = []
    for doc in data:
        for item in doc:
            item |= {"score": {}, "error_spans": {}}
            # try to find the document in data_by_doc and update the TGT there
            found_doc = False
            for doc2 in data_new:
                for item2 in doc2:
                    if item["doc_id"] == item2["doc_id"]:
                        item2["tgt"] |= item["tgt"]
                        found_doc = True
                        break
                if found_doc:
                    break

        if not found_doc:
            data_new.append(doc)

    data_pearmut[langs] = data_new

LANG3_TO_LANG2 = {v: k for k, v in LANG2_TO_LANG3.items()}

header = [
    "user_id",
    "model",
    "campaign_id",
    "_",
    "lang1",
    "lang2",
    "score",
    "document_id",
    "_",
    "error_spans",
    "start_time",
    "end_time",
]
with open("abc_data/results/appraise_raw.csv", "r") as f:
    data = list(csv.DictReader(f.readlines(), fieldnames=header))

data_appraise = copy.deepcopy(data_pearmut)
for item in data:
    lang1, lang2 = item["lang1"], item["lang2"]
    langs2 = f"{LANG3_TO_LANG2[lang1]}{LANG3_TO_LANG2[lang2]}"

    item["model"] = item["model"].removeprefix("abc.ref")

    found_doc = False
    for doc in data_appraise[langs2]:
        for doc_item in doc:
            if (
                doc_item["doc_id"].split("_#_")[0] == item["document_id"]
                and item["model"] not in doc_item["score"]
                and item["model"] in doc_item["tgt"]
            ):
                doc_item["score"][item["model"]] = float(item["score"])
                doc_item["error_spans"][item["model"]] = json.loads(item["error_spans"])
                found_doc = True
                break
        if found_doc:
            break
    if not found_doc:
        print("WARNING: document not found:", item["document_id"])
        continue

# load pearmut, so easy!
with open("abc_data/results/pearmut_raw.json", "r") as f:
    data = json.load(f)

tmp_counter = collections.Counter()
for campaign_id, data in data.items():
    if not campaign_id.startswith("abc_"):
        continue
    langs = campaign_id.removeprefix("abc_")
    for line in data:
        if (
            "item" not in line
            or line["user_id"].endswith("2")
            or line["user_id"].startswith("enko")
        ):
            continue

        for item, annotation in zip(line["item"], line["annotation"]):
            found_doc = False
            # try to find the document in data_pearmut
            for doc in data_pearmut[langs]:
                for doc_item in doc:
                    if doc_item["doc_id"] == item["doc_id"]:
                        for model, annotation in annotation.items():
                            tmp_counter[line["user_id"], model] += 1
                            doc_item["score"][model] = annotation["score"]
                            doc_item["error_spans"][model] = annotation["error_spans"]
                        found_doc = True
                        break
                if found_doc:
                    break
            if not found_doc:
                print("WARNING: document not found in pearmut results:", item)
                continue

# %%

# Render results

with open("abc_data/responses.json", "r") as f:
    responses_data = json.load(f)


def str_to_seconds(s):
    if ":" not in s:
        return int(s)
    m, s = s.split(":")
    return int(m) * 60 + int(s)


times_by_user = {
    user: {
        tool: [str_to_seconds(t) for t in times.split(",")]
        for tool, times in times.items()
    }
    for user, times in responses_data["times"].items()
}

annotations_tool = {
    "pearmut": data_pearmut,
    "appraise": data_appraise,
}

results = collections.defaultdict(lambda: collections.defaultdict(list))
for user in responses_data["times"].keys():
    for tool in ["appraise", "pearmut"]:
        results["Time/item (s)"][tool] += times_by_user[user][tool]
        results["Time/char (ms)"][tool] += [
            t
            / sum(
                len(item["src"]) for doc in annotations_tool[tool][user] for item in doc
            )
            * 1000
            for t in times_by_user[user][tool]
        ]

        results["Time/error (s)"][tool].append(
            statistics.mean(times_by_user[user][tool])
            / statistics.mean(
                [
                    len(item["error_spans"].get(model, []))
                    for item in doc
                    for model in item["error_spans"]
                    for doc in annotations_tool[tool][user]
                ]
            )
        )

        for model in ["A", "B", "C"]:
            results[f"Model {model} score"][tool] += [
                item["score"][model]
                for doc in annotations_tool[tool][user]
                for item in doc
                if model in item["score"]
            ]

        for model in ["A", "B", "C"]:
            results[f"Model {model} errors/item"][tool] += [
                len(item["error_spans"].get(model, []))
                for doc in annotations_tool[tool][user]
                for item in doc
                if model in item["error_spans"]
            ]

# store qualitative responses
for i, quality in enumerate(["Speed", "Clarity", "Effort"]):
    for user in responses_data["quality"]:
        for tool in ["appraise", "pearmut"]:
            results[quality + " (0 to 10)"][tool].append(
                float(responses_data["quality"][user][tool].split(",")[i])
            )


for quantity in results:
    print(f"[{quantity:<20}]", end=", ")
    for tool in ["appraise", "pearmut"]:
        avg = statistics.mean(results[quantity][tool])
        ci = scipy.stats.t.interval(
            0.95,
            len(results[quantity][tool]) - 1,
            loc=avg,
            scale=scipy.stats.sem(results[quantity][tool]),
        )
        ci = (ci[1] - ci[0]) / 2

        if "errors" in quantity:
            print(f"[{avg:>6.1f}]+ci[{ci:.2f}]", end=", ")
        elif "0 to 10" in quantity:
            avg_count = collections.Counter([x // 2 for x in results[quantity][tool]])
            print(
                f"point11({avg:.1f}) + bar5(({",".join(str(avg_count[i]) for i in range(6))}))",
                end=", ",
            )
        else:
            print(f"[{avg:>6.2f}]+ci[{ci:.2f}]", end=", ")
    print()
    if quantity in {
        "Model C errors/item",
        "Model C score",
        "Time/error (s)",
    }:
        print(r"v(-1mm), v(-5mm), v(-10mm),")


# %%
import scipy.stats
import itertools
import numpy as np

# inter-annotator agreement for English->Czech
users = ["encs", "enfi", "enno"]

for tool in ["pearmut", "appraise"]:
    user_scores = [
        [
            item["score"][model]
            for doc in annotations_tool[tool][user]
            for item in doc
            for model in "ABC"
            if model in item["score"]
        ]
        for user in users
    ]
    cap = min([len(user_scores[i]) for i in range(len(users))])
    corr = statistics.mean(
        [
            scipy.stats.pearsonr(user_scores[a][:cap], user_scores[b][:cap]).correlation
            for a, b in itertools.combinations(range(len(users)), 2)
        ]
    )

    print(f"{tool} global {corr:.3f}")

    corrs = []
    for model in "ABC":
        user_scores = [
            [
                item["score"][model]
                for doc in annotations_tool[tool][user]
                for item in doc
                if model in item["score"]
            ]
            for user in users
        ]
        cap = min([len(user_scores[i]) for i in range(len(users))])
        corr = statistics.mean(
            [
                scipy.stats.pearsonr(
                    user_scores[a][:cap], user_scores[b][:cap]
                ).correlation
                for a, b in itertools.combinations(range(len(users)), 2)
            ]
        )
        corrs.append(corr)
    print(f"{tool} group by model {statistics.mean(corrs):.3f}")

    corrs = []
    user_items = collections.defaultdict(lambda: collections.defaultdict(list))
    user2_items = collections.defaultdict(list)
    for user in users:
        for doc in annotations_tool[tool][user]:
            for item in doc:
                for model in "ABC":
                    if model in item["score"]:
                        user_items[user][item["doc_id"]].append(item["score"][model])
    for user1, user2 in itertools.combinations(users, 2):
        common_items = set(user_items[user1].keys()) & set(user_items[user2].keys())
        for doc_id in common_items:
            user_scores = [user_items[user][doc_id] for user in [user1, user2]]
            corr = scipy.stats.kendalltau(user_scores[0], user_scores[1]).correlation
            if np.isnan(corr):
                corr = 1
            corrs.append(corr)
    print(f"{tool} group by item {statistics.mean(corrs):.3f}")


# %%

"""
###################
4. Annotator activity plot
###################
"""

import json
import matplotlib.pyplot as plt
import numpy as np

# load pearmut, so easy!
with open("abc_data/results/pearmut_raw.json", "r") as f:
    data = json.load(f)

data = [
    x | {"user_id": k.removeprefix("abc_")}
    for k, l in data.items()
    if k.startswith("abc_") and k != "abc_enko"
    for x in l
    if "actions" in x
]

fig, axs = plt.subplots(len(data), 1, figsize=(9.2, 0.15 * len(data)))
XLIM = 420

prev_user_id = None
for i, (ax, line) in enumerate(zip(axs, data)):
    trace = []
    assert line["actions"][0]["action"] == "load"
    assert line["actions"][-1]["action"] == "submit"
    time_start = line["actions"][0]["time"]
    last = time_start
    time_end = line["actions"][-1]["time"]
    line["actions"] = line["actions"][1:-1]
    time_total = 2

    # userid on the right side
    if line["user_id"] != prev_user_id:
        ax.text(
            XLIM + 1,
            1,
            line["user_id"].replace("enfi", "encs").replace("enno", "encs"),
            verticalalignment="center",
            fontsize=8,
        )
        prev_user_id = line["user_id"]
    ax.text(
        XLIM - 5,
        1,
        line["actions"][0]["model"],
        verticalalignment="center",
        fontsize=8,
    )

    for action in line["actions"]:
        if action["time"] - last <= 60:
            time_total += action["time"] - last
        style = {
            "create_span": {"color": "#208f20"},
            "delete_span": {"color": "#d34434"},
            "score": {"color": "#2d64c6"},
        }[action["action"]]

        ax.scatter(
            [time_total],
            [2 - action["index"]],
            **style,
            marker=".",
            s=70,
        )
        last = action["time"]

    ax.set_xlim(0, XLIM)
    ax.set_ylim(-0.8, 2.8)
    # turn off axes
    # ax.axis("off")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines[["top", "right", "left", "bottom"]].set_visible(False)

    if i % 2 == 0:
        ax.set_facecolor("#ccc")

plt.tight_layout(pad=0)
# plt.subplots_adjust(hspace=0.2)
plt.savefig("../Downloads/annotator_actions.svg")
plt.show()


# %%

"""
###################
3. Researcher study
###################
"""

"""
Average the columns in this table (that are not commented out).
For the time, take only the Total time. Still use the same macro.

```
XXX
```

Fill this in this other table, with #failcount number of times a user has failed.
Keep the numbers in the macros (#pointM for the first column and #point11 for the rest).

```
XXX
```
"""


# %%


"""
#############
4. Speed test
#############

This tests Pearmut and Appraise speeds, used in the Pearmut report.
"""

# pearmut

import requests
import time
import statistics
import scipy.stats


def measure_average_response(
    url,
    payload=None,
    method="post",
    iterations=1,
    cookies=None,
):
    response_times = []

    # Use a Session to persist the TCP connection (keep-alive)
    with requests.Session() as session:
        if cookies:
            session.cookies.update(cookies)

        for i in range(iterations):
            start_time = time.perf_counter()

            # Perform the POST request
            if method.lower() == "get":
                response = session.get(url, params=payload)
            elif method.lower() == "post":
                response = session.post(url, json=payload)
            else:
                raise ValueError(f"Unsupported method: {method}")

            assert (
                response.status_code == 200
            ), f"Request failed with status code {response.status_code}"
            response_times.append(time.perf_counter() - start_time)

    # Calculate results
    print(url)
    mean = statistics.mean(response_times)
    print(f"{mean*1000:.1f}ms")
    # compute 95% confidence interval
    ci = scipy.stats.t.interval(
        0.99,
        len(response_times) - 1,
        loc=mean,
        scale=scipy.stats.sem(response_times),
    )
    print(f"  ±{(ci[1]-ci[0])/2*1000:.1f}ms (99% CI)")

appraise_csrf_cookie = input()
pearmut_token_ensk = input()

measure_average_response(
    url="http://localhost:8001/basic.html",
    method="get",
    iterations=100,
)

measure_average_response(
    url="http://localhost:8001/get-next-item",
    payload={"campaign_id": "abc_ensk", "user_id": "ensk1"},
    iterations=100,
)


measure_average_response(
    url="http://localhost:8001/dashboard.html",
    method="get",
    iterations=100,
)

measure_average_response(
    url="http://localhost:8001/dashboard-data",
    method="post",
    payload={"campaign_id": "abc_ensk", "token": pearmut_token_ensk},
    iterations=100,
)

measure_average_response(
    url="http://localhost:8001/dashboard-results",
    method="post",
    payload={"campaign_id": "abc_ensk", "token": pearmut_token_ensk},
    iterations=100,
)

measure_average_response(
    url="http://localhost:8001/download-annotations",
    method="get",
    payload={"campaign_id": "abc_ensk", "token": pearmut_token_ensk},
    iterations=100,
)

measure_average_response(
    url="http://localhost:8000/direct-assessment-document/",
    method="get",
    iterations=100,
    cookies={"csrftoken": appraise_csrf_cookie},
)


measure_average_response(
    url="http://localhost:8000/campaign-status/abc24/",
    method="get",
    iterations=100,
)


def measure_average_response_chill(*args, **kwargs):
    time.sleep(10)  # wait for server/connector to chill
    return measure_average_response(*args, **kwargs)


measure_average_response_chill(
    url="https://pearmut.ngrok.io/basic.html",
    method="get",
    iterations=100,
)

measure_average_response_chill(
    url="https://pearmut.ngrok.io/get-next-item",
    payload={"campaign_id": "abc_ensk", "user_id": "ensk1"},
    iterations=100,
)

measure_average_response_chill(
    url="https://pearmut.ngrok.io/dashboard.html",
    method="get",
    iterations=100,
)

measure_average_response_chill(
    url="https://pearmut.ngrok.io/dashboard-data",
    method="post",
    payload={"campaign_id": "abc_ensk", "token": pearmut_token_ensk},
    iterations=100,
)

measure_average_response_chill(
    url="https://pearmut.ngrok.io/dashboard-results",
    method="post",
    payload={"campaign_id": "abc_ensk", "token": pearmut_token_ensk},
    iterations=100,
)

measure_average_response_chill(
    url="https://pearmut.ngrok.io/download-annotations",
    method="get",
    payload={"campaign_id": "abc_ensk", "token": pearmut_token_ensk},
    iterations=100,
)

measure_average_response_chill(
    url="https://alani-unpleadable-vindicatedly.ngrok-free.dev/direct-assessment-document/",
    cookies={"csrftoken": appraise_csrf_cookie},
    method="get",
    iterations=100,
)

measure_average_response_chill(
    url="https://alani-unpleadable-vindicatedly.ngrok-free.dev/campaign-status/abc24/",
    method="get",
    iterations=100,
)

with open("abc_data/pearmut/ende.json", "r") as f:
    campaign_data = json.load(f)

measure_average_response_chill(
    url="https://pearmut.ngrok.io/add-campaign",
    method="post",
    payload={"campaign_data": campaign_data},
    iterations=100,
)

# run bash command 100 times

import subprocess

time_start = time.perf_counter()
subprocess.run(
    "cd ~/Appraise; for _ in {1..100}; do python3 manage.py ExportSystemScoresToCSV abc24 > /dev/null; done",
    shell=True,
    check=True,
)
print(
    "Appraise export",
    f"{(time.perf_counter() - time_start)/100*1000:.1f}ms",
    "",
    sep="\n",
)

# run bash command 100 times

import subprocess
import time
import scipy.stats
import statistics

times = []
for _ in range(100):
    time_start = time.perf_counter()
    subprocess.run(
        "cd ~/Appraise; python3 manage.py StartNewCampaign ~/pearmut/scripts/abc_data/appraise/manifest_speedtest.json --batches-json ~/pearmut/scripts/abc_data/appraise/enno.json --csv-output /tmp/tmp.csv > /dev/null",
        shell=True,
        check=True,
    )
    times.append((time.perf_counter() - time_start) * 1000)

# compute 95% confidence interval
total_avg_time = statistics.mean(times)
ci = scipy.stats.t.interval(
    0.99,
    len(times) - 1,
    loc=total_avg_time,
    scale=scipy.stats.sem(times),
)


print(
    "Appraise import",
    f"{total_avg_time:.1f}ms",
    f"  ±{(ci[1] - ci[0]) / 2:.1f}ms (99% CI)",
    sep="\n",
)

# run bash command 100 times

import subprocess
import time
import scipy.stats
import statistics

times = []
for _ in range(100):
    time_start = time.perf_counter()
    subprocess.run(
        "cd ~/pearmut; pearmut add scripts/abc_data/pearmut/speedtest.json -o > /dev/null",
        shell=True,
        check=True,
    )
    times.append((time.perf_counter() - time_start) * 1000)

# compute 95% confidence interval
total_avg_time = statistics.mean(times)
ci = scipy.stats.t.interval(
    0.99,
    len(times) - 1,
    loc=total_avg_time,
    scale=scipy.stats.sem(times),
)


print(
    "Pearmut import",
    f"{total_avg_time:.1f}ms",
    f"  ±{(ci[1] - ci[0]) / 2:.1f}ms (99% CI)",
    sep="\n",
)


# %%

"""
######################
5. Bibiliography study
######################

Download bibliographies from https://aclanthology.org/
"""

# cat ~/Downloads/*.bib > ~/Downloads/all.bib

import bibtexparser

library = bibtexparser.parse_file("../Downloads/all.bib")

papers = []
for entry in library.entries:
    title = entry["title"].replace("{", "").replace("}", "")
    if "translation" in title.lower():
        papers.append((title, entry["url"].removesuffix("/") + ".pdf"))

print(len(papers))
print(papers)
