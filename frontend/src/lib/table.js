// Hidden data table: the text alternative for canvas charts.

import { el } from "./dom.js";

export function dataTable(caption, headers, rows) {
  return el("table", { className: "sr-only" }, [
    el("caption", { text: caption }),
    el("thead", {}, el("tr", {}, headers.map((h) => el("th", { scope: "col", text: h })))),
    el(
      "tbody",
      {},
      rows.map(([head, ...cells]) => el("tr", {}, [el("th", { scope: "row", text: head }), ...cells.map((c) => el("td", { text: c }))])),
    ),
  ]);
}
