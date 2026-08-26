const registry = window.customElements;
const originalDefine = registry.define;
let defineOverridden = false;

try {
  registry.define = function(name, constructor, options) {
    if (name === "anthbot-map-card" && registry.get(name)) {
      return;
    }
    return originalDefine.call(registry, name, constructor, options);
  };
  defineOverridden = true;
  await import("./anthbot-map-card-core.js?v=2.4.1-test-hotfix1");
} finally {
  if (defineOverridden) {
    try {
      delete registry.define;
    } catch {
      registry.define = originalDefine;
    }
  }
}

window.customCards = window.customCards || [];
let anthbotMapCardSeen = false;
window.customCards = window.customCards.filter((card) => {
  if (card?.type !== "anthbot-map-card") return true;
  if (anthbotMapCardSeen) return false;
  anthbotMapCardSeen = true;
  return true;
});
