// THE CREDITS COME FROM THE MANIFEST. One writer, shared by every tool
// that rewrites props.json, because a header written by hand is a licence
// claim nobody re-checks when the folder grows. fetch.mjs once said
// "Every model in this folder is from Poly Haven and is CC0 1.0" over
// twenty Quixel Megascans assets under the Fab Standard License;
// ingest.mjs said "two libraries" over a folder that had held three since
// the decals arrived. Both were hand-written sentences above correctly
// derived entries, which is the worse half to get wrong. A third copy was
// about to be written for split.mjs, which is the point at which a rule
// stops being a habit and becomes a module.

export function libraryOf(source) {
  const where = /polyhaven/.test(source) ? "Poly Haven"
    : /ambientcg/i.test(source) ? "ambientCG"
      : /fab\.com/.test(source) ? "Quixel Megascans, via Fab"
        : "other";
  return where;
}

export function noticeFor(manifest) {
  const libraries = new Map();
  for (const prop of manifest.props) {
    const line = `${libraryOf(prop.source || "")} -- ${prop.licence || "licence unstated"}`;
    libraries.set(line, (libraries.get(line) || 0) + 1);
  }
  return [
    "Models in this folder come from more than one library. Each is",
    "credited below; the licences they arrived under are:",
    ...[...libraries.entries()].sort()
      .map(([line, count]) => `  ${line}  (${count})`),
    "",
    "Poly Haven and ambientCG ask for no credit and this file is offered",
    "anyway. The Fab Standard License needs a free Epic account and",
    "permits use with any compatible tool, which the glTF export is.",
    "",
    // A variant is credited under its family's source: the split is ours,
    // the model is theirs.
    ...manifest.props.map((p) => `${p.key}\n  ${p.label}\n  ${p.source}`),
  ].join("\n") + "\n";
}
