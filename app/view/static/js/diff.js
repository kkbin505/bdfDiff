/**
 * BdfDiff – client-side helpers
 * Applies syntax highlighting to unified-diff blocks rendered in HTML.
 */

document.addEventListener("DOMContentLoaded", () => {
  highlightDiffBlocks();
});

/**
 * Walk every <pre class="diff-block"> element and wrap each line with a
 * colour span based on the first character ('+', '-', '@').
 */
function highlightDiffBlocks() {
  document.querySelectorAll("pre.diff-block").forEach((block) => {
    const lines = block.textContent.split("\n");
    block.innerHTML = lines
      .map((line) => {
        if (line.startsWith("+++") || line.startsWith("---")) {
          return `<span class="line-hdr">${escHtml(line)}</span>`;
        } else if (line.startsWith("+")) {
          return `<span class="line-add">${escHtml(line)}</span>`;
        } else if (line.startsWith("-")) {
          return `<span class="line-del">${escHtml(line)}</span>`;
        } else if (line.startsWith("@@")) {
          return `<span class="line-hdr">${escHtml(line)}</span>`;
        }
        return escHtml(line);
      })
      .join("\n");
  });
}

function escHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
