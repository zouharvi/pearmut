import collections
import json
import os
import statistics

from .utils import get_db_log


def comparison_significant(
    scores1: dict[str, float], scores2: dict[str, float]
) -> bool:
    """Check if the difference between two sets of scores is statistically significant.
    Assume scores1 > scores2.
    """

    import scipy.stats

    # compute intersection
    common_items = set(scores1.keys()).intersection(set(scores2.keys()))
    if len(common_items) < 2:
        return False

    scores1 = [scores1[k] for k in common_items]
    scores2 = [scores2[k] for k in common_items]

    return bool(
        scipy.stats.ttest_rel(scores1, scores2, alternative="two-sided").pvalue < 0.05
    )


def compute_model_scores(campaign_id):
    """
    Compute model scores from annotations for a campaign.

    Returns:
        List of dicts with keys: model, score, count
        Sorted by score in descending order
    """
    # Compute model scores from annotations
    model_scores = collections.defaultdict(dict)

    # Iterate through all tasks to find items with 'models' field (basic template)
    log = get_db_log(campaign_id)
    for entry in log:
        if "item" not in entry or "annotation" not in entry:
            continue
        for item, annotation in zip(entry["item"], entry["annotation"]):
            for model, annotation in annotation.items():
                if "score" in annotation and annotation["score"] is not None:
                    item_id = item.get("item_id") or json.dumps(item | {"tgt": None})
                    model_scores[model][item_id] = annotation["score"]

    model_scores = list(model_scores.items())
    model_scores.sort(key=lambda x: statistics.mean(x[1].values()), reverse=True)

    results = []
    for i, (model, scores) in enumerate(model_scores):
        avg_score = statistics.mean(scores.values())
        sig_better = False
        if i < len(model_scores) - 1:
            # Compare with next model
            scores_next = model_scores[i + 1][1]
            sig_better = comparison_significant(scores, scores_next)
        else:
            sig_better = False
        results.append(
            {
                "model": model,
                "score": avg_score,
                "count": len(scores),
                "sig_better_than_next": sig_better,
            }
        )
    return results


def escape_typst(s: str):
    return (
        s.replace("\\", "\\\\")
        .replace("#", "\\#")
        .replace("*", "\\*")
        .replace("_", "\\_")
        .replace("`", "\\`")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )


def generate_typst_table(results):
    """
    Generate Typst code for a two-column table with results.

    Args:
        results: List of dicts with keys: model, score, count

    Returns:
        String containing Typst table markup
    """
    if not results:
        return "// No results available"

    typst_code = """#table(
  columns: (auto, auto),
  align: (left, right),
  stroke: none,
  table.hline(),
  [*Model*], [*Score*],
  table.hline(),
"""

    for result in results:
        # Escape Typst special characters
        model = escape_typst(result["model"])
        score = f"{result['score']:.1f}"
        typst_code += f"  [{model}], [{score}],\n"
        if result["sig_better_than_next"]:
            typst_code += "  table.hline(end: 1),\n"

    typst_code += "  table.hline(),\n"
    typst_code += ")\n"
    return typst_code


def generate_latex_table(results):
    """
    Generate LaTeX code for a booktabs two-column table with results.

    Args:
        results: List of dicts with keys: model, score, count

    Returns:
        String containing LaTeX table markup
    """
    if not results:
        return "% No results available"

    latex_code = """\\begin{table}[h]
\\centering
\\begin{tabular}{lr}
\\toprule
\\textbf{Model} & \\textbf{Score} \\\\
\\midrule
"""

    for result in results:
        # Escape LaTeX special characters
        model = result["model"]
        model = model.replace("\\", "\\textbackslash ")
        model = model.replace("_", "\\_")
        model = model.replace("&", "\\&")
        model = model.replace("%", "\\%")
        model = model.replace("$", "\\$")
        model = model.replace("#", "\\#")
        model = model.replace("{", "\\{")
        model = model.replace("}", "\\}")
        model = model.replace("~", "\\textasciitilde ")
        model = model.replace("^", "\\textasciicircum ")

        score = f"{result['score']:.1f}"
        latex_code += f"{model} & {score} \\\\\n"
        if result["sig_better_than_next"]:
            latex_code += "\\cmidrule{1-1}\n"

    latex_code += """\\bottomrule
\\end{tabular}
\\caption{Model ranking results}
\\label{tab:results}
\\end{table}
"""
    return latex_code


def generate_pdf(results, campaign_id):
    """
    Generate PDF from Typst code using typst-py.

    Args:
        results: List of dicts with keys: model, score, count

    Returns:
        bytes containing the PDF
    """

    import tempfile

    import typst

    if not results:
        # Return empty PDF with message
        typst_code = "[No results available]"
    else:
        typst_code = f"""
        #set page(width: auto, height: auto, margin: 1.5pt)
        == {escape_typst(campaign_id)}
        """ + generate_typst_table(
            results
        )

    # Create a temporary file for the typst source
    with tempfile.NamedTemporaryFile(mode="w", suffix=".typ", delete=False) as f:
        f.write(typst_code)
        typst_file = f.name

    try:
        # Compile to PDF
        pdf_bytes = typst.compile(typst_file)
        return pdf_bytes
    finally:
        # Clean up
        os.unlink(typst_file)
