"""Default instructions for different annotation protocols."""

# Default instructions for each protocol
# These are used when no custom instructions are provided
PROTOCOL_INSTRUCTIONS = {
    "DA": """
        <ul>
          <li>Score each translation using the slider based on meaning preservation and quality.
            <strong>Important:</strong> The relative order of scores matters; ensure better translations have higher
            scores than worse ones.
            <ul>
              <li>0: <strong>Broken</strong>/Nonsense</li>
              <li>33%: <strong>Flawed</strong>: substantial issues.</li>
              <li>66%: <strong>Good</strong>: small issues with grammar, fluency, or consistency.</li>
              <li>100%: <strong>Perfect</strong>: meaning and style align completely with the source.</li>
            </ul>
          </li>
        </ul>
    """,
    "ESA": """
        <ul>
          <li>Error spans:
            <ul>
              <li><strong>Click</strong> on the start of an error, then <strong>click</strong> on the end to mark an
                error span.</li>
              <li><strong>Hover</strong> over an existing highlight to change error severity (minor/major) or remove it.
              </li>
            </ul>
            Error severity:
            <ul>
              <li><span class="error_minor">Minor:</span> Style, grammar, or word choice
                could be better.</li>
              <li><span class="error_major">Major:</span> Meaning is significantly
                changed or is hard to understand.</li>
            </ul>
            <strong>Tip</strong>: Mark the general area of the error (doesn't need to be exact). Use separate highlights
            for different errors.
            Use <code style="font-family: monospace">[missing]</code> at the end of a sentence for omitted content.<br>
          </li>
          <li>Score each translation using the slider based on meaning preservation and quality.
            <strong>Important:</strong> The relative order of scores matters; ensure better translations have higher
            scores than worse ones.
            <ul>
              <li>0: <strong>Broken</strong>/Nonsense</li>
              <li>33%: <strong>Flawed</strong>: substantial issues.</li>
              <li>66%: <strong>Good</strong>: small issues with grammar, fluency, or consistency.</li>
              <li>100%: <strong>Perfect</strong>: meaning and style align completely with the source.</li>
            </ul>
          </li>
        </ul>
    """,
    "cESA": """
    <ul>
      <li><strong>Task:</strong> Read the source text and competing translations. Highlight all errors. Rate each translation.</li>
      <li><strong>Highlighting errors:</strong>
        <ul>
          <li><strong>Select text</strong> containing an error to mark it as <span class="error_minor">Minor</span>.</li>
          <li><strong>Click selected text</strong> to change the error to <span class="error_major">Major</span> or remove the highlight.</li>
          <li><strong>Missing text:</strong> Highlight the <code style="font-family: monospace">[MISSING]</code> tag if the translation omits important source text.</li>
        </ul>
      </li>
      <li><strong>Error severity:</strong>
        <ul>
          <li><span class="error_minor">Minor:</span> Imperfections or stylistic issues that do not impact the core message (e.g., awkward phrasing).</li>
          <li><span class="error_major">Major:</span> Confuses meaning, misrepresents the source, or violates the message (e.g., incorrect information, confusing wording).</li>
        </ul>
      </li>
      <li><strong>Important rules:</strong>
        <ul>
          <li><strong>Multiple errors:</strong> Use separate highlights for each error.</li>
          <li><strong>Hallucinations:</strong> Highlight unsupported extra text; mark as Major.</li>
          <li><strong>Wrong language:</strong> Highlight the entire text, mark as Major, and assign a score of 0.</li>
          <li><strong>Consistency:</strong> Check translation consistency (e.g., technical terms) across the document.</li>
        </ul>
      </li>
      <li><strong>Rating scale (0-100%):</strong>
        <ul>
          <li><strong>85-100% (Very Good):</strong> Complete meaning transfer; perfectly natural; no or minimal proofreading.</li>
          <li><strong>65-80% (Good):</strong> Near-complete transfer, minor inaccuracies; mostly natural, minor awkwardness; needs light proofreading.</li>
          <li><strong>45-60% (Acceptable):</strong> Main ideas conveyed, noticeable inaccuracies or omissions; uneven naturalness, awkward phrasing; usable only after substantial revision.</li>
          <li><strong>25-40% (Borderline):</strong> Partial transfer; frequent misinterpretation or omission confusing the message; often unnatural; requires major rewrite.</li>
          <li><strong>0-20% (Not acceptable):</strong> Violation of meaning; large portions mistranslated, missing, or incoherent; unusable without complete retranslation.</li>
        </ul>
      </li>
    </ul>
    <style>
    .output_candidate, .output_src {
        width: 345px !important;
        flex: unset;
    }
    .output_tgt, .output_src { 
      height: calc(100% - 50px);
    }
    </style>
    """,
    "MQM": """
        <ul>
          <li>Error spans:
            <ul>
              <li><strong>Click</strong> on the start of an error, then <strong>click</strong> on the end to mark an
                error span.</li>
              <li><strong>Hover</strong> over an existing highlight to change error severity (minor/major) or remove it.
              </li>
            </ul>
            Error severity:
            <ul>
              <li><span class="error_minor">Minor:</span> Style, grammar, or word choice
                could be better.</li>
              <li><span class="error_major">Major:</span> Meaning is significantly
                changed or is hard to understand.</li>
            </ul>
            <strong>Tip</strong>: Mark the general area of the error (doesn't need to be exact). Use separate highlights
            for different errors.
            Use <code style="font-family: monospace">[missing]</code> at the end of a sentence for omitted content.<br>
          </li>
          <li>Score each translation using the slider based on meaning preservation and quality.
            <strong>Important:</strong> The relative order of scores matters; ensure better translations have higher
            scores than worse ones.
            <ul>
              <li>0: <strong>Broken</strong>/Nonsense</li>
              <li>33%: <strong>Flawed</strong>: substantial issues.</li>
              <li>66%: <strong>Good</strong>: small issues with grammar, fluency, or consistency.</li>
              <li>100%: <strong>Perfect</strong>: meaning and style align completely with the source.</li>
            </ul>
          </li>
          <li>
            Error types:
            After highlighting an error fragment, you will be asked to select the specific error type (main category and
            subcategory).
            If you are unsure about which errors fall under which categories, please consult the <a
              href="https://themqm.org/the-mqm-typology/"
              style="font-weight: bold; text-decoration: none; color: black;">typology
              definitions</a>.
          </li>
        </ul>
    """,
}
