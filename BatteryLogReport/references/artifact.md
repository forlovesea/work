# Word template contract

Authoritative sources are the unmodified retained files `../app/src/main/assets/charge.docx` and `../app/src/main/assets/outage.docx`, copied from the user-specified documents. `../qa/charge-structure.json` and `../qa/outage-structure.json` record every original body element, including XML, inline images, text, and paragraph properties.

## Page system

Both templates: portrait 12240 × 15840 twips, one section, single column, column spacing 720, document grid linePitch 360, header/footer distance 720, gutter 0.

Charge margins: top 1080, right 1800, bottom 1008, left 1800 twips. Outage margins: top 1008, right 1080, bottom 936, left 1080 twips. Section XML is copied unchanged. No new headers or footers are added.

## Style authority

All paragraph styles, numbering, font table, theme and settings are copied byte-for-byte. For each replaced paragraph, retain its `w:pPr` and the first original run's `w:rPr`. Untouched paragraphs are cloned exactly. This retains the original font choices, role sizes, spacing, indents and alignment. Mixed run emphasis in rewritten variable prose is not retained; this is a known fidelity limitation pending visual review.

## Editable slots

Stable locators are zero-based direct child indexes of `word/document.xml / w:document/w:body`. The generated document repeats the source section content for each installation site, with a page break between sites.

Charge: indexes 0 and 2 are count/site/date metadata; 4 is the evidence-based conclusion; 6 is the metric table; 8 is source attribution; 9 is a DC-load evidence image; 11–12 are measurement interpretation; 13–19 are the per-unit heading, narrative, chart and attribution pattern. The original second-unit pattern 21–27 is replaced by repetitions of 13–19. Keep 1,3,5,7,10,17,19,31,32. Variable strings and all original images must be replaced, never carried forward as facts.

Outage: indexes 3,5–8,10,12,23–24,27,29–31,34–38,42–44,46–48,50–55 contain metadata, conclusions, state tables, evidence illustrations, timing, Unknown interpretation, alarm scope and suggested reply. Generate these from each unit's data. Preserve the title, topic headings, interpretation framework and procedural advice in 0–2,4,9,11,13–22,26,28,33,40–41,45,49,56–62, except small wording corrections in the implementation. Do not claim uploaded alarm analysis because alarm files are not accepted inputs.

## Tables and images

Clone existing table and cell properties. Use one or two system columns per table; for more than two systems repeat the table. Remove the empty trailing row in the outage template. Preserve total content widths (8640 and 10080 twips), divide columns evenly and repeat header rows. New illustrations replace all old sample images and use fresh relationship IDs and unique drawing IDs. Evidence images show up to the first 12 matching original rows, explicitly labeled; analysis uses all records.

Version 1.0.1 exception requested by the user: the outage section 2-3 Current/SOC evidence image includes up to 12 discharge samples plus up to 4 subsequent positive-current samples. Choose the first discharge cycle with subsequent charging (otherwise the first discharge). Preserve the first positive-current timestamp and select the remaining samples across the uninterrupted charging run, ending at the last positive record before zero, negative current, or a gap exceeding 10 minutes. Never manufacture charging samples. Add a source-styled paragraph explaining the observed transition, sustained positive samples and SOC increase when available. This allows up to 16 rows and a proportionately taller image. Other evidence image selection rules remain unchanged.

Charge chart width is fitted to 5486400 EMU, the template content width; the reference chart's 6400800 EMU extends beyond the charge text area. This is an intentional geometry correction. Outage images remain 6400800 EMU wide. Image heights follow the actual PNG aspect ratio.

## Package preservation

Editable package parts: `word/document.xml`, `word/_rels/document.xml.rels`, `word/media/*`. All other parts—including `customXml`, styles, numbering, theme, fontTable, document properties, settings, webSettings, content types and root relationships—must remain byte-identical. Regression verification checks every such part and every generated image relationship.

## Verification limits

Original in-document graphics and complete body XML were inspected. The packaged renderer failed because this Windows runtime has no bundled LibreOffice. A hidden Microsoft Word PDF export was attempted but did not respond and was interrupted. Page counts, final line breaks and pixel-level fidelity remain unresolved. No visual-fidelity pass is claimed; generated DOCX files under `qa` are test artifacts, not final deliverables. The delivered artifact is the signed Android APK. See `../VALIDATION.md` for tested behavior and limitations.
