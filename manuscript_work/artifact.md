# Template execution contract

- Reference: `C:\Users\koush\Documents\MIS Project Template.docx`; SHA-256 `185D7530FA0458B20D7D100F939CAE6D0D88C7F1124D96E2D886ABA5287329B9`.
- Reference is a 10-section, portrait report template. Its prose includes sample networking material and university form text; none of that sample research content is to be copied.
- User-requested paper subject: GraphRAG-Net cyber threat intelligence knowledge graph and retrieval/reasoning prototype found in the workspace.
- Output path: `C:\Users\koush\Downloads\graphrag-net\GraphRAG-Net_Journal_Style_Report.docx`.
- Style contract: report sequence adapted from the template (cover, title, declaration, certificate, abstract, acknowledgement, contents, lists, abbreviations, chapters, conclusion/future work, appendices, APA references); Times New Roman 12 pt body, 16 pt chapter headings, 14 pt section headings, 12 pt subsections; A4; left margin 3.81 cm and other margins 2.54 cm; Arabic page number at bottom center. Use the supplied template as the source for styles/theme, while consolidating the example's numerous section breaks into a clean manuscript structure.
- Fillable unknowns: author, registration number, guide, department approval, acknowledgement names, submission date. Never sign or assert a certification for the user.
- Content evidence: source files, code, and processed JSON in the project folder. Graph inventory counts must be described as entries loaded by the implemented pipeline; edge duplicates have not been deduplicated.
- Evaluation fidelity gate: calibration labels in `labeled_eval.jsonl` are generated from agreement/cosine features which are also model inputs; accuracy metrics are circular and are not independent validation. Link prediction script has no held-out test split and scores against training edges; do not claim link prediction performance. Clearly separate these development artifacts from defensible empirical findings.
- Literature comparison: compare task/data/method/evaluation scope with cited works; never place incomparable published results in a shared leaderboard or imply direct superiority.
- Visual component: include one original pipeline overview figure and a concise caption.
- Keep the source template byte-for-byte unchanged. Check final DOCX structure and rendered pages. Rendering tool availability must be diagnosed; do not claim visual approval if actual rendering cannot be performed.
