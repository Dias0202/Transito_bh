import { FRONTS, methodLists, type Ctx } from "../i18n";

export function frontsText(c: Ctx) {
  const ol = document.querySelector<HTMLOListElement>("[data-fronts]")!;
  ol.innerHTML = FRONTS[c.lang]
    .map(
      (f, i) => `<li class="front">
        <span class="front__n">0${i + 1}</span>
        <h3>${f.title}</h3>
        <p>${f.body}</p>
        <span class="chip chip--${f.state}">${f.status}</span>
      </li>`,
    )
    .join("");
}

export function methodText(c: Ctx) {
  const lists = methodLists(c);
  document.querySelectorAll<HTMLUListElement>("[data-list]").forEach((ul) => {
    const key = ul.dataset.list === "method.sources" ? "sources" : "limits";
    ul.innerHTML = lists[key].map((s) => `<li>${s}</li>`).join("");
  });
}
