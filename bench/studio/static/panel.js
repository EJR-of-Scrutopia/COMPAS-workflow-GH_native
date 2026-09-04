// The panel's own machinery: everything that shapes controls and nothing
// that draws a scene. No three.js, no renderer, no state beyond what it is
// handed, so it can be loaded on its own by panel-proof.html and looked at
// without a GPU.
//
// studio.js imports these and passes in what they need. The split exists
// because software WebGL crashes the GPU process in the sandbox this is
// developed in, which meant the panel could not be screenshotted and a
// layout fault had to be found by eye on Param's machine instead of here.

// ---------- sliders become rows ----------
// Every range input in the panel is rebuilt in place as a single row: the
// name it already carried on the left, whatever value spans it already
// carried on the right, and the row itself as the track. The input is kept,
// stretched over the row and made invisible, so every handler, every id and
// every keyboard behaviour survives untouched: this is a change of
// appearance and nothing else, which is what Param asked for.
export function upgradeSliders(root) {
  const scope = root || document.getElementById("panel");
  if (!scope) return;
  for (const input of scope.querySelectorAll('input[type="range"]')) {
    const label = input.closest("label");
    if (!label || label.classList.contains("hidden")) continue;
    if (label.parentElement && label.parentElement.classList.contains("scrub")) continue;
    const row = document.createElement("div");
    row.className = "scrub";
    // Anything before the input is its name; anything after it is its
    // value, which is usually a span some handler writes into. Both are
    // MOVED rather than copied, so the ids and the handlers come with them.
    const name = document.createElement("span");
    name.className = "scrub-name";
    const value = document.createElement("span");
    value.className = "scrub-value";
    let seenInput = false;
    for (const node of Array.from(label.childNodes)) {
      if (node === input) { seenInput = true; continue; }
      (seenInput ? value : name).appendChild(node);
    }
    name.textContent = name.textContent.trim();
    const fill = document.createElement("span");
    fill.className = "fill";
    row.appendChild(input);
    row.appendChild(fill);
    row.appendChild(name);
    row.appendChild(value);
    label.replaceWith(row);
    // Carry the label's own id, if it had one: the panel hides and shows
    // whole rows by id (the HDRI scale row, the weather row).
    if (label.id) row.id = label.id;
    if (label.className) row.className = "scrub " + label.className;
    paintScrub(input);
    input.addEventListener("input", () => paintScrub(input));
    input.addEventListener("change", () => paintScrub(input));
  }
}

export function paintScrub(input) {
  const row = input.closest(".scrub");
  if (!row) return;
  const min = +input.min || 0;
  const max = input.max === "" ? 100 : +input.max;
  const span = max - min;
  const u = span > 0 ? (+input.value - min) / span : 0;
  row.style.setProperty("--fill", (u * 100).toFixed(2) + "%");
}

// A value written by a handler rather than by a drag still has to move the
// fill, and there are a dozen handlers that write one. Rather than chase
// them all, the rows repaint whenever the panel is touched at all.
export function repaintScrubs() {
  for (const input of document.querySelectorAll(".scrub input[type=\"range\"]")) {
    paintScrub(input);
  }
}

// ---------- a select becomes a segmented row ----------
// The select stays, hidden, and stays the source of truth: the segments
// write to it and dispatch its change event, so every handler downstream
// runs exactly as it did. Only what the eye sees changes.
export function buildSegmented(holderId, selectId) {
  const holder = document.getElementById(holderId);
  const select = document.getElementById(selectId);
  if (!holder || !select) return;
  holder.innerHTML = "";
  for (const option of select.options) {
    const segment = document.createElement("button");
    segment.textContent = option.textContent;
    segment.dataset.value = option.value;
    segment.addEventListener("click", () => {
      if (select.value === option.value) return;
      select.value = option.value;
      select.dispatchEvent(new Event("change"));
      paintSegmented(holderId, selectId);
    });
    holder.appendChild(segment);
  }
  paintSegmented(holderId, selectId);
}

export function paintSegmented(holderId, selectId) {
  const holder = document.getElementById(holderId);
  const select = document.getElementById(selectId);
  if (!holder || !select) return;
  for (const segment of holder.children) {
    segment.classList.toggle("active", segment.dataset.value === select.value);
  }
}

// ---------- groups fold, and say what they hold while folded ----------
// The Scene panel is five groups in a column, and Param's complaint about it
// was that one does not know where to begin. A heading that folds its own
// group turns that column into five lines, and a summary on the right means
// a folded group still answers the question you would have opened it to ask.
let groupSummaries = {};

export function setGroupSummaries(table) {
  groupSummaries = table;
}


export function buildGroups() {
  for (const heading of document.querySelectorAll(".row-heading")) {
    if (heading.dataset.grouped) continue;
    const title = heading.textContent.trim();
    heading.dataset.grouped = "1";
    heading.dataset.title = title;
    heading.textContent = title;
    const summary = document.createElement("span");
    summary.className = "summary";
    heading.appendChild(summary);
    // Everything up to the next heading belongs to this one.
    const body = document.createElement("div");
    body.className = "group-body";
    let node = heading.nextSibling;
    while (node && !(node.classList && node.classList.contains("row-heading"))) {
      const next = node.nextSibling;
      body.appendChild(node);
      node = next;
    }
    heading.after(body);
    heading.addEventListener("click", () => {
      const folded = body.classList.toggle("folded");
      heading.classList.toggle("folded", folded);
      paintGroupSummaries();
    });
  }
  paintGroupSummaries();
}

export function paintGroupSummaries() {
  for (const heading of document.querySelectorAll(".row-heading")) {
    const summary = heading.querySelector(".summary");
    const read = groupSummaries[heading.dataset.title];
    if (!summary || !read) continue;
    try {
      summary.textContent = heading.classList.contains("folded") ? read() : "";
    } catch (error) {
      summary.textContent = "";
    }
  }
}

