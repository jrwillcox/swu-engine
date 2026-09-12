import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";

// Components here persist UI preferences to localStorage — CardExplorer stores its
// grid/list view mode under "swu.explorerView", and explorer_list.test.tsx asserts
// that write. jsdom storage can outlive a single test, so without a reset the
// suite's behaviour depends on execution order: a later test would render in
// whichever mode an earlier one happened to leave behind.
//
// Clear storage before every test so each starts from the component's real
// defaults. A test that needs a stored value should set it explicitly.
beforeEach(() => {
  try {
    localStorage.clear();
    sessionStorage.clear();
  } catch {
    // Some environments block storage access; nothing to reset if so.
  }
});
