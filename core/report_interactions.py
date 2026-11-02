"""Offline table interactions; never fetch data or change the underlying report evidence."""

TABLE_INTERACTIONS = r'''
(() => {
  const english = document.documentElement.lang === "en";
  const collator = new Intl.Collator(english ? "en" : "zh", {numeric: true, sensitivity: "base"});
  const valueOf = (cell) => {
    if (!cell || cell.querySelector(".muted")) return "";
    return (cell.querySelector("[data-export]")?.dataset.export ?? cell.innerText).trim();
  };
  const numeric = (value) => /^[+-]?\d[\d,]*(?:\.\d+)?%?$/.test(value);
  document.querySelectorAll(".table-block table").forEach((table) => {
    if (!table.tHead || !table.tBodies[0]) return;
    const body = table.tBodies[0];
    const original = [...body.rows];
    const positions = new Map(original.map((row, index) => [row, index]));
    const headers = [...table.tHead.rows[0].cells];
    const buttons = [];
    let keys = [];
    const paintSort = () => {
      headers.forEach((header, index) => {
        const order = keys.findIndex((key) => key.column === index);
        const key = keys[order];
        header.setAttribute("aria-sort", order === 0 ? (key.direction === 1 ? "ascending" : "descending") : "none");
        buttons[index].textContent = buttons[index].dataset.label + (key ? ` ${key.direction === 1 ? "↑" : "↓"}${order + 1}` : " ↕");
      });
    };
    const sortRows = () => {
      const rows = [...original].sort((left, right) => {
        for (const key of keys) {
          const a = valueOf(left.cells[key.column]);
          const b = valueOf(right.cells[key.column]);
          if (!a || !b) {
            if (a !== b) return a ? -1 : 1;
            continue;
          }
          const order = numeric(a) && numeric(b)
            ? Number(a.replaceAll(",", "").replace("%", "")) - Number(b.replaceAll(",", "").replace("%", ""))
            : collator.compare(a, b);
          if (order) return key.direction * order;
        }
        return positions.get(left) - positions.get(right);
      });
      body.append(...rows);
      paintSort();
    };
    headers.forEach((header, column) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "sort-column";
      button.dataset.label = header.textContent.trim();
      button.title = english ? "Sort; Shift+click to add a column" : "排序；按 Shift 点击可增加排序列";
      button.addEventListener("click", (event) => {
        const prior = keys.find((key) => key.column === column);
        const key = {column, direction: prior ? -prior.direction : 1};
        if (event.shiftKey) {
          keys = prior ? keys.map((item) => item.column === column ? key : item) : [...keys, key];
        } else keys = [key];
        sortRows();
      });
      header.replaceChildren(button);
      buttons.push(button);
    });
    paintSort();
    const reset = document.querySelector(`[data-reset="${table.id}"]`);
    if (reset) reset.addEventListener("click", () => { keys = []; body.append(...original); paintSort(); });
  });
  document.querySelectorAll(".export-column").forEach((button) => {
    button.addEventListener("click", () => {
      const table = document.getElementById(button.dataset.target);
      const select = document.getElementById(button.dataset.select);
      if (!table || !select || !table.tBodies[0]) return;
      const seen = new Set();
      const values = [];
      for (const row of table.tBodies[0].rows) {
        if (row.hidden) continue;
        // A value occupies one line; retain the original value in the report and CSV.
        const value = valueOf(row.cells[Number(select.value)]).replace(/[\r\n]+/g, " ");
        if (value && !seen.has(value)) { seen.add(value); values.push(value); }
      }
      const url = URL.createObjectURL(new Blob([values.join("\n") + (values.length ? "\n" : "")], {type:"text/plain;charset=utf-8"}));
      const link = document.createElement("a");
      link.href = url;
      link.download = "fofamap-" + select.options[select.selectedIndex].dataset.field + ".txt";
      link.click();
      URL.revokeObjectURL(url);
    });
  });
})();
'''
