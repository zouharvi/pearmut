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
      <li><strong>Task:</strong> Read the source text and competing translations. Highlight all errors. Rate each translation (each column is an output from a single model/translator). At the end, click <b>Next</b> in top-right corner.</li><br>
      <li><strong>Highlighting errors:</strong>
        <ul>
          <li><strong>Mark errors</strong> by clicking the beginning and then clicking at the end of the erroneous text span.</li>
          <li>Use <span class="error_minor">minor severity</span> for imperfections or stylistic issues that do not impact the core message (e.g., awkward phrasing).</li>
          <li>Use <span class="error_major">major severity</span> for errors that confuse meaning, misrepresent the source, or violate the message (e.g., incorrect information, confusing wording).</li>
          <li><strong>Missing text:</strong> Highlight the <code style="font-family: monospace">[MISSING]</code> tag if the translation omits important source text.</li>
        </ul>
      </li>
      <br>
      <li><strong>Important rules:</strong>
        <ul>
          <li><strong>Multiple errors:</strong> Use separate highlights for each error.</li>
          <li><strong>Hallucinations:</strong> Highlight unsupported extra text; mark as Major.</li>
          <li><strong>Wrong language:</strong> Highlight the entire text, mark as Major, and assign a score of 0.</li>
          <li><strong>Consistency:</strong> Check translation consistency (e.g., technical terms) across the document.</li>
        </ul>
      </li>
      <br>
      <li><strong>Rating scale (0-100%):</strong>
        <ul>
          <li><strong>85-100% (Very Good):</strong> Complete meaning transfer; perfectly natural; no or minimal proofreading.</li>
          <li><strong>65-80% (Good):</strong> Near-complete transfer, minor inaccuracies; mostly natural, minor awkwardness; needs light proofreading.</li>
          <li><strong>45-60% (Acceptable):</strong> Main ideas conveyed, noticeable inaccuracies or omissions; uneven naturalness, awkward phrasing; usable only after substantial revision.</li>
          <li><strong>25-40% (Borderline):</strong> Partial transfer; frequent misinterpretation or omission confusing the message; often unnatural; requires major rewrite.</li>
          <li><strong>0-20% (Not acceptable):</strong> Violation of meaning; large portions mistranslated, missing, or incoherent; unusable without complete retranslation.</li>
        </ul>
      </li>
      <br>
      <li>For unexpected problems and remarks, use comment box in ⚙️ (top right).</li>
    </ul>
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
    # XSTS+R+P instructions adapted from the Omnilingual MT paper (https://arxiv.org/abs/2603.16309), Appendix B.1.
    "XSTSRP": """
        <ul>
          <li><strong>The goal</strong> is to assess the degree of correspondence/equivalence of meaning and register 
          (style) between a source paragraph and its translation. You will need to read the source and the translation, 
          compare them sentence by sentence, and assign a score to each sentence.</li>
          <li>Notes:
            <ul>
              <li>The examples below are phrase or sentence-based for simplicity purposes. You will work with longer 
                paragraphs and will need to take the whole paragraph context into account.</li>
              <li>Please ignore minor typos and grammatical errors if they do not affect your understanding of the
                texts.</li>
              <li>Please ignore capitalization and punctuation differences if they do not affect your
                understanding.</li>
            </ul>
          </li>
          <li>Score each sentence pair using the following scale from 1 to 5:
            <ul>
              <li><strong>[1]</strong> The source paragraph and its translation are not semantically equivalent,
                share very little detail, and may be about different topics.
                <details>
                  <summary>Examples</summary>
                  <ul>
                    <li><em>Example A (different topics)</em><br>
                      Text 1 (English): Train station<br>
                      Text 2 (Spanish): Restaurante vegano (Vegan restaurant)</li>
                    <li><em>Example B (false equivalents)</em><br>
                      Text 1: When I get home, I always lock the door. It gives me peace of mind.<br>
                      Text 2: Cuando llego a casa siempre loqueo la puerta. Me da tranquilidad.</li>
                    <li><em>Example C (very little overlap and unrelated entities)</em><br>
                      Text 1: Open museums<br>
                      Text 2: Centros comerciales abiertos (Open malls)</li>
                    <li><em>Example D (indecipherable on one side or the other)</em><br>
                      Text 1: lorbo lorbo lorl room<br>
                      Text 2: Habitación doble (double room)</li>
                    <li><em>Example E (untranslated text)</em><br>
                      Text 1: Should you have any questions, please let me know.<br>
                      Text 2: Si tiene cualquier duda, please let me know.</li>
                    <li><em>Example F (hallucinations)</em><br>
                      Text 1: Thank you for joining us today. We're so happy you're here.<br>
                      Text 2: Gracias por acompañarnos hoy. Nos alegra mucho que estéis aquí. Esta noche la vamos a
                      recordar toda la vida. (We will remember this night for the rest of our lives).</li>
                  </ul>
                </details>
              </li>
              <li><strong>[2]</strong> The source paragraph and its translation share some details, but are not
                equivalent. Some important information related to the primary subject/verb/object differs or is
                missing, which alters the intent or meaning of the paragraph. Alternatively, the register differs so
                much that this translation will be a big mistake. A significant change in register will always score
                no more than 2 points.
                <details>
                  <summary>Examples</summary>
                  <ul>
                    <li><em>Example A (opposite polarity)</em><br>
                      Text 1: Flight to London<br>
                      Text 2: Vuelo desde Londres (Flight from London)</li>
                    <li><em>Example B (non-equivalent numbers)</em><br>
                      Text 1: Two rooms for three people<br>
                      Text 2: Tres habitaciones para dos personas (Three rooms for two people)</li>
                    <li><em>Example C (substitution/change in named entity)</em><br>
                      Text 1: Flight to Valencia<br>
                      Text 2: Vuelo a Valladolid (Flight to Valladolid)</li>
                    <li><em>Example D (different meaning due to word order)</em><br>
                      Text 1: I like pizza<br>
                      Text 2: Yo gusto a la pizza (Pizza likes me)</li>
                    <li><em>Example E (equivalent constructions with different meanings)</em><br>
                      Text 1: The bus is arriving at 2.<br>
                      Text 2: El autobús está llegando a las 2.<br>
                      <span style="font-style: italic">Explanation: Spanish present progressive cannot be used to
                        refer to the future.</span></li>
                    <li><em>Example F (missing salient information)</em><br>
                      Text 1: Vegan Italian restaurant<br>
                      Text 2: Restaurante italiano (Italian restaurant)</li>
                    <li><em>Example G (omitted relevant chunks)</em><br>
                      Text 1: The company's new product (a flask with temperature regulation) is expected to be a
                      success.<br>
                      Text 2: Se espera que el nuevo producto de la empresa sea un éxito.</li>
                    <li><em>Example H (register difference)</em><br>
                      Text 1: What's up, dude?<br>
                      Text 2: ¿Cómo se encuentra, señor? (How are you, sir?)</li>
                  </ul>
                </details>
              </li>
              <li><strong>[3]</strong> The two paragraphs are mostly equivalent, but some unimportant details can
                differ. There cannot be any significant conflicts in intent, meaning or register between the
                sentences, no matter how long the sentences are.
                <details>
                  <summary>Examples</summary>
                  <ul>
                    <li><em>Example A (omitted non-critical information, but no contradictory info introduced)</em><br>
                      Text 1: Table for 3 adults<br>
                      Text 2: Mesa para 3 (Table for 3)</li>
                    <li><em>Example B (unit of measurement differences)</em><br>
                      Text 1: I want 2 pounds of cheese.<br>
                      Text 2: Quería 1 kg de queso. (I wanted 1kg of cheese.)</li>
                    <li><em>Example C (minor verb tense differences)</em><br>
                      Text 1: When he arrived at the station, the train had already left.<br>
                      Text 2: Cuando llegue a la estación, el tren ya se habrá ido. (When he arrives at the station,
                      the train will have already left.)</li>
                    <li><em>Example D (small, non-conflicting differences in meaning)</em><br>
                      Text 1: I love running.<br>
                      Text 2: Me gusta correr. (I like running.)</li>
                    <li><em>Example E (non-critical information added)</em><br>
                      Text 1: Photos of the trip<br>
                      Text 2: Fotos de mi viaje (Photos of my trip)</li>
                    <li><em>Example F (non-equivalent constructions)</em><br>
                      Text 1: The president finally signed the new education bill yesterday at noon.<br>
                      Text 2: La nueva ley de educación finalmente fue firmada por el presidente ayer al mediodía.
                      (The new education bill was finally signed by the president yesterday at noon.)</li>
                    <li><em>Example G (inconsistent register)</em><br>
                      Text 1: First, you will need to purchase all the painting supplies you need. Then, film and
                      tape everything that is not to be painted.<br>
                      Text 2: Primero, tendrás que comprar todo lo que necesitas para pintar. Luego proteja con film
                      y cinta de pintor todo lo que no deba ser pintado.<br>
                      <span style="font-style: italic">Explanation: "proteja" is a formal second person imperative
                        form ("usted"), but the verb in the previous sentence ("tendrás") uses an informal second
                        person form ("tú").</span></li>
                    <li><em>Example H (inconsistent target)</em><br>
                      Text 1: It's pretty flashy, but remember that you have to wash it often.<br>
                      Text 2: Es bien chido, pero acordate que tienes que lavarlo frecuentemente.<br>
                      <span style="font-style: italic">Explanation: The translation mixes lexical and/or grammatical
                        forms from different varieties/dialects ("bien chido" is broadly Mexican, "acordate" is
                        broadly Rioplatense and "tienes" is from a non-voseo variety like European Spanish).</span></li>
                  </ul>
                </details>
              </li>
              <li><strong>[4]</strong> The two paragraphs are paraphrases of each other. Their meanings are
                near-equivalent, with no major differences or information missing. There can only be minor
                differences in meaning due to differences in expression (e.g., formality level, style, emphasis,
                potential implication, idioms, common metaphors). For single word texts, there might be multiple
                meanings depending on the context they would be used in, but the one presented is still correct.
                <details>
                  <summary>Examples</summary>
                  <ul>
                    <li><em>Example A</em><br>
                      Text 1: This is great<br>
                      Text 2: Esto es la leche (Lit: This is the milk)<br>
                      <span style="font-style: italic">Explanation: "Esto es la leche" is an idiom, "this is great"
                        is not.</span></li>
                    <li><em>Example B</em><br>
                      Text 1: The day that comes after the day of today<br>
                      Text 2: Mañana (Tomorrow)<br>
                      <span style="font-style: italic">Explanation: Differences in phrasing, text 1 is oddly phrased
                        and more verbose than text 2.</span></li>
                    <li><em>Example C</em><br>
                      Text 1: Bird<br>
                      Text 2: Pajarito (birdie)<br>
                      <span style="font-style: italic">Explanation: Different level of formality ("Birdie" vs
                        "bird").</span></li>
                  </ul>
                </details>
              </li>
              <li><strong>[5]</strong> The two paragraphs are exactly and completely equivalent in meaning and usage
                expression (e.g., formality level, style, emphasis, potential implication, idioms, common
                metaphors). In other words, nuance is completely preserved and there is a faithful correspondence.
                Fidelity is also preserved.
                <details>
                  <summary>Examples</summary>
                  <ul>
                    <li><em>Example A</em><br>
                      Text 1: I am so happy.<br>
                      Text 2: Estoy lleno de felicidad (I am filled with happiness).</li>
                    <li><em>Example B</em><br>
                      Text 1: Hi friends<br>
                      Text 2: Hola chicos (Hello guys)</li>
                    <li><em>Example C</em><br>
                      Text 1: Hello, how are you<br>
                      Text 2: Hola cómo estás (Hello how are you)</li>
                  </ul>
                </details>
              </li>
            </ul>
          </li>
        </ul>
    """,
}
