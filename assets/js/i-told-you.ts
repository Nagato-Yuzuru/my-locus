// Board interactivity for /i-told-you/: filter takes by verdict + paginate.
// Vanilla DOM, no framework. Transpiled by Hugo's js.Build (esbuild);
// type-checked separately via `deno check`.

(function () {
  const board = document.querySelector<HTMLElement>(".ity-board");
  if (!board) return;

  const per = parseInt(board.dataset.perpage || "10", 10);
  const chips = Array.from(board.querySelectorAll<HTMLButtonElement>(".ity-chip"));
  const cells = Array.from(board.querySelectorAll<HTMLElement>(".ity-cell"));
  const items = Array.from(board.querySelectorAll<HTMLElement>(".ity-item"));
  const pager = board.querySelector<HTMLElement>(".ity-pager");
  if (!pager) return;

  let filter = "all";
  let page = 1;

  const matches = (el: HTMLElement): boolean => filter === "all" || el.dataset.v === filter;

  function render(): void {
    cells.forEach((c) => { c.hidden = !matches(c); });

    const visible = items.filter(matches);
    const pages = Math.max(1, Math.ceil(visible.length / per));
    if (page > pages) page = pages;

    items.forEach((it) => { it.hidden = true; });
    visible.slice((page - 1) * per, page * per).forEach((it) => { it.hidden = false; });

    chips.forEach((ch) => { ch.setAttribute("aria-pressed", String(ch.dataset.filter === filter)); });

    pager!.innerHTML = "";
    if (pages <= 1) return;
    const add = (label: string, target: number, disabled: boolean, current: boolean): void => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = label;
      b.className = "ity-page" + (current ? " is-current" : "");
      if (disabled) b.disabled = true;
      else b.addEventListener("click", () => { page = target; render(); });
      pager!.appendChild(b);
    };
    add("‹", page - 1, page <= 1, false);
    for (let i = 1; i <= pages; i++) add(String(i), i, false, i === page);
    add("›", page + 1, page >= pages, false);
  }

  chips.forEach((ch) => {
    ch.addEventListener("click", () => { filter = ch.dataset.filter || "all"; page = 1; render(); });
  });

  render();
})();
